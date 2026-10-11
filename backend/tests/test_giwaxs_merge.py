"""GIWAXS fiber-integration merge — end-to-end HTTP tests.

Run from PRE/backend:  python -m pytest tests/test_giwaxs_merge.py -v
(or directly:          python tests/test_giwaxs_merge.py)

Synthetic truth: a Pilatus-like detector with a bright spot near the beam
center plus Poisson background; two "exposures" whose detector orientations
differ (rot1/rot2 overrides), merged back onto one shared (qip, qoop) grid.
"""

from __future__ import annotations

import io
import json
import os
import sys
import zipfile

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

client = TestClient(app)


def _synthetic_image(seed: int = 0, shape=(300, 300)) -> bytes:
    rng = np.random.default_rng(seed)
    img = rng.poisson(40, size=shape).astype(np.float64)
    img[130:170, 130:170] += 800.0
    buf = io.BytesIO()
    np.save(buf, img)
    return buf.getvalue()


def _synthetic_poni() -> str:
    """A minimal but valid PONI file for a square 172 µm pixel detector."""
    return (
        "# Synthetic calibration (tests)\n"
        "Distance: 0.15\n"
        "Poni1: 0.0258\n"
        "Poni2: 0.0258\n"
        "Rot1: 0.0\n"
        "Rot2: 0.0\n"
        "Rot3: 0.0\n"
        "Wavelength: 1.55e-10\n"
        "Detector: Detector\n"
        "PixelSize1: 0.000172\n"
        "PixelSize2: 0.000172\n"
    )


def _upload() -> dict:
    files = [
        ("files", ("img_a.npy", io.BytesIO(_synthetic_image(0)), "application/octet-stream")),
        ("files", ("img_b.npy", io.BytesIO(_synthetic_image(1)), "application/octet-stream")),
        ("files", ("calib.poni", io.BytesIO(_synthetic_poni().encode()), "text/plain")),
    ]
    res = client.post("/api/giwaxs-merge/upload", files=files)
    assert res.status_code == 200, res.text
    files_out = {f["originalName"]: f["fileId"] for f in res.json()["files"]}
    assert set(files_out) == {"img_a.npy", "img_b.npy", "calib.poni"}
    return files_out


def test_parse_poni():
    fids = _upload()
    res = client.post("/api/giwaxs-merge/parse-poni", json={"fileId": fids["calib.poni"]})
    assert res.status_code == 200, res.text
    body = res.json()
    assert abs(body["wavelength"] - 0.155) < 1e-6
    assert abs(body["dist"] - 0.15) < 1e-9
    assert body["rot1Deg"] == 0.0 and body["rot2Deg"] == 0.0
    assert body["beamCenterX"] > 0 and body["beamCenterY"] > 0


def test_run_merge_and_semantics():
    fids = _upload()
    req = {
        "images": [
            {"imageFileId": fids["img_a.npy"], "name": "img_a", "rot1Deg": None, "rot2Deg": None},
            {"imageFileId": fids["img_b.npy"], "name": "img_b", "rot1Deg": 3.5, "rot2Deg": -1.2},
        ],
        "poniFileId": fids["calib.poni"],
        "sampleOrientation": 1,
        "incidentAngleDeg": 0.2,
        "tiltAngleDeg": 0.0,
        "unitIp": "qip_nm^-1",
        "unitOop": "qoop_nm^-1",
        "autoRange": True,
        "nptIp": 96,
        "nptOop": 96,
        "method": "csr",
        "polarizationFactor": 0.99,
        "correctSolidAngle": True,
        "mergeMethod": "mean",
        "maskLowerBound": None,
    }
    res = client.post("/api/giwaxs-merge/run", json=req)
    assert res.status_code == 200, res.text
    body = res.json()

    # rot semantics: img_a inherits PONI (0), img_b uses its overrides
    rots = {it["name"]: it["rotApplied"] for it in body["images"]}
    assert rots["img_a"][0] == 0.0 and rots["img_a"][1] == 0.0
    assert abs(rots["img_b"][0] - 3.5) < 1e-9 and abs(rots["img_b"][1] + 1.2) < 1e-9
    assert all(it["ok"] for it in body["images"])
    assert all(it["coverage"] > 0.5 for it in body["images"])

    # preview grid: rows = out-of-plane, cols = in-plane; strict JSON (null for NaN)
    assert len(body["preview"]) <= 96 and len(body["preview"][0]) <= 96
    assert body["minIntensity"] is not None and body["maxIntensity"] is not None
    assert body["info"]["mergedImageCount"] == 2
    assert body["info"]["mergeMethod"] == "mean"
    assert body["info"]["xAxisUnit"] == "qip_nm^-1"
    assert len(body["info"]["images"]) == 2

    # merge methods differ in output
    for method in ("median", "weighted", "sequential"):
        req["mergeMethod"] = method
        r2 = client.post("/api/giwaxs-merge/run", json=req)
        assert r2.status_code == 200, r2.text
        assert r2.json()["info"]["mergeMethod"] == method

    # explicit ranges fix the axes
    req["autoRange"] = False
    req["ipRange"] = [-10.0, 10.0]
    req["oopRange"] = [-5.0, 5.0]
    req["mergeMethod"] = "mean"
    r3 = client.post("/api/giwaxs-merge/run", json=req)
    assert r3.status_code == 200, r3.text
    b3 = r3.json()
    # pyFAI adds half-bin margins, so the realized axes sit just inside the request
    assert -10.0 <= b3["ipRange"][0] and b3["ipRange"][1] <= 10.0
    assert -5.0 <= b3["oopRange"][0] and b3["oopRange"][1] <= 5.0
    assert b3["ipRange"][1] - b3["ipRange"][0] > 19.0
    assert b3["oopRange"][1] - b3["oopRange"][0] > 9.0
    assert min(b3["ipAxis"]) >= -10.0 and max(b3["ipAxis"]) <= 10.0
    return b3


def test_render_png():
    body = test_run_merge_and_semantics()
    res = client.post("/api/giwaxs-merge/render-png", json={
        "resultFileId": body["mergedFileId"],
        "ipAxisFileId": body["ipAxisFileId"],
        "oopAxisFileId": body["oopAxisFileId"],
        "unitIp": body["unitIp"],
        "unitOop": body["unitOop"],
        "cmap": "viridis",
        "useLog": True,
        "climMode": "auto",
        "title": "merged GIWAXS",
        "baseName": "test_giwaxs",
    })
    assert res.status_code == 200, res.text[:300]
    assert res.headers["content-type"] == "image/png"
    assert res.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(res.content) > 10_000


def test_export_zip():
    body = test_run_merge_and_semantics()
    res = client.post("/api/giwaxs-merge/export", json={
        "mergedFileId": body["mergedFileId"],
        "ipAxisFileId": body["ipAxisFileId"],
        "oopAxisFileId": body["oopAxisFileId"],
        "info": body["info"],
        "baseName": "test_merge",
        "includePng": True,
        "png": {"cmap": "turbo", "useLog": False},
        "unitIp": body["unitIp"],
        "unitOop": body["unitOop"],
    })
    assert res.status_code == 200, res.text[:300]
    zf = zipfile.ZipFile(io.BytesIO(res.content))
    names = set(zf.namelist())
    assert {"test_merge_giwaxs.npy", "ip_array.npy", "oop_array.npy",
            "processing_info.json", "test_merge_giwaxs.png"} <= names
    merged = np.load(io.BytesIO(zf.read("test_merge_giwaxs.npy")))
    assert merged.shape == (96, 96)
    info = json.loads(zf.read("processing_info.json").decode("utf-8"))
    assert info["mergedImageCount"] == 2
    assert any(it.get("rot1Deg") == 3.5 for it in info["images"])
    assert zf.read("test_merge_giwaxs.png")[:8] == b"\x89PNG\r\n\x1a\n"


def test_bad_inputs():
    fids = _upload()
    # unsupported unit
    res = client.post("/api/giwaxs-merge/run", json={
        "images": [{"imageFileId": fids["img_a.npy"]}],
        "poniFileId": fids["calib.poni"],
        "unitIp": "bogus_unit",
    })
    assert res.status_code == 400
    # unsupported method
    res = client.post("/api/giwaxs-merge/run", json={
        "images": [{"imageFileId": fids["img_a.npy"]}],
        "poniFileId": fids["calib.poni"],
        "method": "quantum",
    })
    assert res.status_code == 400
    # missing poni
    res = client.post("/api/giwaxs-merge/run", json={
        "images": [{"imageFileId": fids["img_a.npy"]}],
        "poniFileId": "doesnotexist.npy",
    })
    assert res.status_code == 400


if __name__ == "__main__":
    test_parse_poni()
    print("PASS test_parse_poni")
    test_run_merge_and_semantics()
    print("PASS test_run_merge_and_semantics")
    test_render_png()
    print("PASS test_render_png")
    test_export_zip()
    print("PASS test_export_zip")
    test_bad_inputs()
    print("PASS test_bad_inputs")
    print("ALL PASS")
