"""Verify the qz band slice router (backend/routers/qz_slice.py).

Runs the router's own helpers (no HTTP) plus endpoint-level checks against a
minimal FastAPI app, all on synthetic data (no pyFAI dependency):

  1. band enumeration — qz=0.5 / interval=0.1 over oop in [-2, 2] yields the
     9 bands centred at -2 .. +2 step 0.5 (the +-2.0 bands still overlap);
  2. row selection + averaging — the centre-0.5 band keeps 21 rows
     (0.40..0.60 inclusive at step 0.01) and its curve equals a direct
     np.nanmean; the all-NaN column propagates as null/NaN;
  3. band-count guard — qz=0.001 would exceed MAX_BANDS -> HTTP 400;
  4. mask lower bound — pixels below the bound leave both the sum and the
     average; an all-masked column becomes NaN;
  5. endpoints — /upload (bare .npys AND the giwaxs_merge export ZIP),
     /attach, /run, /export-csv and /export-txt on the stored file-ids;
  6. error paths — unsupported types / missing merged map -> 400.

Run from PRE/:  python test/test_qz_slice.py
"""

import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np

# Backend package root (PRE/backend), resolved absolute; scratch files are
# confined to the backend's own upload/output dirs via utils.
BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from fastapi import HTTPException  # noqa: E402

from routers import qz_slice as Q  # noqa: E402

_FAILED = []


def check(label, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {label}" + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        _FAILED.append(label)


# ---------------------------------------------------------------------------
# Fixtures — synthetic GIWAXS merge output (rows = oop, cols = ip)
# ---------------------------------------------------------------------------

OOP = np.linspace(-2.0, 2.0, 401)                       # step 0.01
IP = np.linspace(-3.0, 3.0, 301)
I_MAP = (np.exp(-((OOP[:, None] - 0.5) / 0.05) ** 2) + 0.1) * np.ones((1, len(IP)))
I_MAP[:, 150] = np.nan                                  # all-NaN column


def _npy_bytes(arr):
    buf = io.BytesIO()
    np.save(buf, np.asarray(arr))
    return buf.getvalue()


def _expected_curve(lo=0.4, hi=0.6, col=None):
    """Direct reference: nanmean over the oop rows inside [lo, hi]."""
    rows = np.where((OOP >= lo - 1e-9) & (OOP <= hi + 1e-9))[0]
    block = I_MAP[rows, :]
    if col is not None:
        return np.nanmean(block[:, col]), rows
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return np.nanmean(block, axis=0), rows


# ---------------------------------------------------------------------------
# 1+2. Band enumeration, row selection and averaging (pure helper)
# ---------------------------------------------------------------------------
def test_compute_bands():
    bands = Q._compute_bands(I_MAP, IP, OOP, 0.5, 0.1)
    check("bands: 9 bands centred at -2..2 step 0.5",
          len(bands) == 9
          and np.allclose([b.center for b in bands], np.arange(-4, 5) * 0.5),
          f"got {len(bands)} bands, centers={[b.center for b in bands]}")
    check("bands: ascending centre order",
          all(bands[i].center < bands[i + 1].center for i in range(len(bands) - 1)))

    b05 = next(b for b in bands if abs(b.center - 0.5) < 1e-12)
    check("bands: centre-0.5 range is [0.4, 0.6]",
          abs(b05.qzLo - 0.4) < 1e-12 and abs(b05.qzHi - 0.6) < 1e-12,
          f"got [{b05.qzLo}, {b05.qzHi}]")
    check("bands: centre-0.5 keeps 21 rows (0.40..0.60 inclusive)", b05.nRows == 21,
          f"got nRows={b05.nRows}")

    want, rows = _expected_curve()
    got = np.array([np.nan if v is None else v for v in b05.intensity])
    check("bands: centre-0.5 curve equals direct nanmean (finite cols)",
          np.allclose(got[np.isfinite(got)], want[np.isfinite(want)], rtol=1e-12, atol=1e-12))
    check("bands: all-NaN column propagates as null", b05.intensity[150] is None)
    check("bands: intensity length == full ip axis", len(b05.intensity) == len(IP))
    check("bands: validFraction in (0, 1] and matches the NaN column",
          0.0 < b05.validFraction < 1.0
          and abs(b05.validFraction - np.isfinite(I_MAP[rows, :]).mean()) < 1e-12,
          f"got {b05.validFraction}")

    # Edge bands at +-2.0: only half inside the data range (11 rows each).
    b_lo = next(b for b in bands if abs(b.center + 2.0) < 1e-12)
    b_hi = next(b for b in bands if abs(b.center - 2.0) < 1e-12)
    check("bands: +-2.0 edge bands keep 11 rows each",
          b_lo.nRows == 11 and b_hi.nRows == 11,
          f"got {b_lo.nRows}/{b_hi.nRows}")

    try:
        Q._compute_bands(I_MAP, IP, OOP, 0.001, 0.05)
        check("bands: qz too small raises 400 (band cap)", False)
    except HTTPException as e:
        check("bands: qz too small raises 400 (band cap)",
              e.status_code == 400 and "max 512" in str(e.detail), str(e.detail))


# ---------------------------------------------------------------------------
# 3. Mask lower bound (helper level)
# ---------------------------------------------------------------------------
def test_mask_lower_bound():
    # Background is 0.1 everywhere; a 0.2 bound must drop those pixels from
    # BOTH the sum and the average (they count as no data).
    masked = I_MAP.copy()
    masked[:, 5] = 0.05                     # a column that is entirely below
    bands = Q._compute_bands(masked, IP, OOP, 0.5, 0.1, mask_lower_bound=0.2)
    b05 = next(b for b in bands if abs(b.center - 0.5) < 1e-12)
    rows = np.where((OOP >= 0.4 - 1e-9) & (OOP <= 0.6 + 1e-9))[0]
    block = masked[rows, :]
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        want = np.nanmean(np.where(np.isfinite(block) & (block >= 0.2), block, np.nan), axis=0)
    got = np.array([np.nan if v is None else v for v in b05.intensity])
    check("mask: curve averages only pixels >= bound",
          np.allclose(got[np.isfinite(got)], want[np.isfinite(want)], rtol=1e-12, atol=1e-12))
    check("mask: all-masked column becomes null", b05.intensity[5] is None)
    check("mask: validFraction counts only valid+above-bound pixels",
          abs(b05.validFraction - (np.isfinite(block) & (block >= 0.2)).mean()) < 1e-12,
          f"got {b05.validFraction}")
    check("mask: NaN pixels stay excluded too (col 150 still null)",
          b05.intensity[150] is None)


# ---------------------------------------------------------------------------
# 3-6. Endpoint-level tests (independent app, only this router mounted)
# ---------------------------------------------------------------------------

def _make_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(Q.router, prefix="/api/qz-slice")
    return TestClient(app)


def test_endpoints(client):
    # -- /upload with three bare .npy files --------------------------------
    r = client.post("/api/qz-slice/upload", files=[
        ("files", ("demo_giwaxs.npy", _npy_bytes(I_MAP), "application/octet-stream")),
        ("files", ("ip_array.npy", _npy_bytes(IP), "application/octet-stream")),
        ("files", ("oop_array.npy", _npy_bytes(OOP), "application/octet-stream")),
    ])
    check("upload: 200", r.status_code == 200, f"status={r.status_code} body={r.text[:300]}")
    info = r.json()
    check("upload: grid dims", info["nIp"] == 301 and info["nOop"] == 401)
    check("upload: oopRange == [-2, 2]",
          np.allclose(info["oopRange"], [-2.0, 2.0]), str(info["oopRange"]))
    check("upload: ipRange == [-3, 3]", np.allclose(info["ipRange"], [-3.0, 3.0]))
    check("upload: default units", info["unitIp"] == "qip_A^-1"
          and info["unitOop"] == "qoop_A^-1")
    check("upload: preview dims match preview axes (<= 224 per side)",
          len(info["preview"]) == len(info["oopAxis"]) <= 224
          and len(info["preview"][0]) == len(info["ipAxis"]) <= 224,
          f"preview={len(info['preview'])}x{len(info['preview'][0])}")
    check("upload: NaN preview cell is null",
          all(row[75] is None for row in info["preview"]))   # col 75 of strided IP
    check("upload: finite intensity stats",
          abs(info["minIntensity"] - 0.1) < 1e-9 and abs(info["maxIntensity"] - 1.1) < 1e-6)
    check("upload: sourceName = first uploaded file",
          info["sourceName"] == "demo_giwaxs.npy", info["sourceName"])

    fids = (info["mergedFileId"], info["ipAxisFileId"], info["oopAxisFileId"])

    # -- /run ---------------------------------------------------------------
    r = client.post("/api/qz-slice/run", json={
        "mergedFileId": fids[0], "ipAxisFileId": fids[1], "oopAxisFileId": fids[2],
        "qz": 0.5, "interval": 0.1,
    })
    check("run: 200", r.status_code == 200, f"status={r.status_code} body={r.text[:300]}")
    run = r.json()
    check("run: 9 bands, full qx axis", len(run["bands"]) == 9 and len(run["qx"]) == 301)
    b05 = next(b for b in run["bands"] if abs(b["center"] - 0.5) < 1e-12)
    want, _ = _expected_curve()
    got = np.array([np.nan if v is None else v for v in b05["intensity"]])
    check("run: centre-0.5 band matches direct nanmean", b05["nRows"] == 21
          and np.allclose(got[np.isfinite(got)], want[np.isfinite(want)], rtol=1e-12))

    # -- /attach ------------------------------------------------------------
    r = client.post("/api/qz-slice/attach", json={
        "mergedFileId": fids[0], "ipAxisFileId": fids[1], "oopAxisFileId": fids[2],
        "sourceName": "demo",
    })
    check("attach: 200 + same oopRange", r.status_code == 200
          and np.allclose(r.json()["oopRange"], [-2.0, 2.0]),
          f"status={r.status_code} body={r.text[:300]}")
    r = client.post("/api/qz-slice/attach", json={
        "mergedFileId": "deadbeef0000", "ipAxisFileId": fids[1], "oopAxisFileId": fids[2]})
    check("attach: unknown fileId -> 404", r.status_code == 404, f"status={r.status_code}")

    # -- /export-csv ----------------------------------------------------------
    r = client.post("/api/qz-slice/export-csv", json={
        "mergedFileId": fids[0], "ipAxisFileId": fids[1], "oopAxisFileId": fids[2],
        "qz": 0.5, "interval": 0.1, "baseName": "demo", "sourceName": "demo_giwaxs.npy",
    })
    check("export-csv: 200 + text/csv", r.status_code == 200
          and r.headers["content-type"].startswith("text/csv"),
          f"status={r.status_code} type={r.headers.get('content-type')}")
    check("export-csv: attachment filename",
          'demo_qz_slice.csv' in r.headers.get("content-disposition", ""))
    text = r.content.decode("utf-8")
    lines = text.strip().split("\n")
    check("export-csv: first comment names the module",
          lines[0].startswith("#") and "qz band slice" in lines[0], lines[0])
    data_lines = [ln for ln in lines if not ln.startswith("#")][1:]  # drop header
    check("export-csv: 301 data rows x 10 columns",
          len(data_lines) == 301 and all(len(ln.split(",")) == 10 for ln in data_lines[:5]),
          f"rows={len(data_lines)} cols={len(data_lines[0].split(','))}")
    check("export-csv: NaN cell exported as empty field",
          data_lines[150].split(",")[1 + 4] == "",  # band idx 4 == centre 0.5
          data_lines[150])

    # -- /run + exports with a mask lower bound ------------------------------
    r = client.post("/api/qz-slice/run", json={
        "mergedFileId": fids[0], "ipAxisFileId": fids[1], "oopAxisFileId": fids[2],
        "qz": 0.5, "interval": 0.1, "maskLowerBound": 0.2,
    })
    check("run masked: 200", r.status_code == 200, f"status={r.status_code}")
    mb05 = next(b for b in r.json()["bands"] if abs(b["center"] - 0.5) < 1e-12)
    rows = np.where((OOP >= 0.4 - 1e-9) & (OOP <= 0.6 + 1e-9))[0]
    block = I_MAP[rows, :]
    want = np.nanmean(np.where(np.isfinite(block) & (block >= 0.2), block, np.nan), axis=0)
    got = np.array([np.nan if v is None else v for v in mb05["intensity"]])
    check("run masked: band averages only pixels >= bound",
          np.allclose(got[np.isfinite(got)], want[np.isfinite(want)], rtol=1e-12))

    # -- /export-txt ----------------------------------------------------------
    r = client.post("/api/qz-slice/export-txt", json={
        "mergedFileId": fids[0], "ipAxisFileId": fids[1], "oopAxisFileId": fids[2],
        "qz": 0.5, "interval": 0.1, "baseName": "demo", "sourceName": "demo_giwaxs.npy",
    })
    check("export-txt: 200 + text/plain", r.status_code == 200
          and r.headers["content-type"].startswith("text/plain"),
          f"status={r.status_code} type={r.headers.get('content-type')}")
    check("export-txt: attachment filename",
          'demo_qz_slice.txt' in r.headers.get("content-disposition", ""))
    text = r.content.decode("utf-8")
    lines = text.strip().split("\n")
    header = next(ln for ln in lines if not ln.startswith("#"))
    check("export-txt: column header starts with qip", header.split()[0] == "qip", header)
    data_lines = [ln for ln in lines if not ln.startswith("#")][1:]
    check("export-txt: 301 whitespace-column data rows",
          len(data_lines) == 301 and all(len(ln.split()) == 10 for ln in data_lines[:5]),
          f"rows={len(data_lines)} cols={len(data_lines[0].split())}")
    check("export-txt: NaN cell written as 'nan'",
          data_lines[150].split()[1 + 4] == "nan", data_lines[150])
    r = client.post("/api/qz-slice/export-txt", json={
        "mergedFileId": fids[0], "ipAxisFileId": fids[1], "oopAxisFileId": fids[2],
        "qz": 0.5, "interval": 0.1, "maskLowerBound": 0.2, "baseName": "demo",
    })
    check("export-txt: mask bound recorded in header comment",
          any("mask lower bound: 0.2" in ln for ln in r.content.decode("utf-8").split("\n")))

    # -- /upload with a giwaxs_merge-style ZIP --------------------------------
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("demo_giwaxs.npy", _npy_bytes(I_MAP))
        zf.writestr("ip_array.npy", _npy_bytes(IP))
        zf.writestr("oop_array.npy", _npy_bytes(OOP))
        zf.writestr("processing_info.json", json.dumps({
            "module": "PolymCrystRefine GIWAXS fiber-integration merge",
            "xAxisUnit": "qip_nm^-1", "yAxisUnit": "qoop_nm^-1",
        }))
    r = client.post("/api/qz-slice/upload",
                    files=[("files", ("demo_giwaxs_merge.zip", buf.getvalue(), "application/zip"))])
    check("upload zip: 200", r.status_code == 200, f"status={r.status_code} body={r.text[:300]}")
    zinfo = r.json()
    check("upload zip: units picked from processing_info.json",
          zinfo["unitIp"] == "qip_nm^-1" and zinfo["unitOop"] == "qoop_nm^-1")
    check("upload zip: same grid", zinfo["nIp"] == 301 and zinfo["nOop"] == 401)

    # -- error paths -----------------------------------------------------------
    r = client.post("/api/qz-slice/upload", files=[
        ("files", ("only_ip.npy", _npy_bytes(IP), "application/octet-stream")),
    ])
    check("upload: 1-D npy alone -> 400", r.status_code == 400, f"status={r.status_code}")
    r = client.post("/api/qz-slice/upload", files=[
        ("files", ("notes.txt", b"hello", "text/plain")),
    ])
    check("upload: unsupported type -> 400", r.status_code == 400, f"status={r.status_code}")
    r = client.post("/api/qz-slice/run", json={
        "mergedFileId": fids[0], "ipAxisFileId": fids[1], "oopAxisFileId": fids[2],
        "qz": 0.001, "interval": 0.05,
    })
    check("run: band cap -> 400", r.status_code == 400 and "max 512" in r.text,
          f"status={r.status_code}")


if __name__ == "__main__":
    test_compute_bands()
    test_mask_lower_bound()

    try:
        client = _make_client()
    except Exception as exc:  # httpx missing etc. -> endpoints skipped
        client = None
        print(f"[SKIP] endpoint tests (TestClient unavailable: {exc})")

    if client is not None:
        test_endpoints(client)

    print()
    if _FAILED:
        print(f"{len(_FAILED)} FAILED: " + ", ".join(_FAILED))
        sys.exit(1)
    print("All qz-slice checks passed.")
