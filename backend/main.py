"""
PolymCrystRefine Backend — FastAPI application entry point.

Serves the data-processing APIs of PolymCrystRefine: WAXS processing, 2D
intensity integration, XRD simulation, image analysis and data viewer, and
optionally the production-built frontend from ``../frontend/dist``.
"""

import os
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import UPLOAD_DIR, OUTPUT_DIR, PRE_PORT
from routers import waxs_pipeline, xrd_simulator, image_analysis, viewer, integration, input_generator, lmp_extractor, cif_hydrogen, cp2k_input, symmetry, deviation_report, giwaxs_merge, qz_slice


# ---------------------------------------------------------------------------
# Lifespan — create / clean temp dirs
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create temp directories on startup, remove them on shutdown."""
    for d in (UPLOAD_DIR, OUTPUT_DIR):
        os.makedirs(d, exist_ok=True)
    yield
    # NOTE: intentionally do NOT remove the temp dirs on shutdown.
    # Multiple backend instances (a dev server and the packaged exe, or
    # repeated restarts) share these exact paths; rmtree here would delete
    # files a concurrent/next instance is about to use and break uploads
    # with FileNotFoundError -> HTTP 500. _save_upload/_save_output also
    # recreate the dir defensively on every write.


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="PolymCrystRefine Backend",
    description="PolymCrystRefine — Data Processing Module backend services",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow everything during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API routers
# ---------------------------------------------------------------------------
app.include_router(integration.router, prefix="/api/integration", tags=["2D Integration"])
app.include_router(waxs_pipeline.router, prefix="/api/waxs", tags=["WAXS Pipeline"])
app.include_router(xrd_simulator.router, prefix="/api/xrd", tags=["XRD Simulator"])
app.include_router(image_analysis.router, prefix="/api/analysis", tags=["Image Analysis"])
app.include_router(viewer.router, prefix="/api/viewer", tags=["Data Viewer"])
app.include_router(input_generator.router, prefix="/api/input-generator", tags=["Input Generator"])
app.include_router(lmp_extractor.router, prefix="/api/lmp-extractor", tags=["LMP Extractor"])
app.include_router(cif_hydrogen.router, prefix="/api/cifh", tags=["CIF Hydrogenation"])
app.include_router(cp2k_input.router, prefix="/api/cp2k", tags=["CP2K FIBER_DIFFRACTION"])
app.include_router(symmetry.router, prefix="/api/symmetry", tags=["Space Group Detection"])
app.include_router(deviation_report.router, prefix="/api/deviation", tags=["Structure Deviation Report"])
app.include_router(giwaxs_merge.router, prefix="/api/giwaxs-merge", tags=["GIWAXS Fiber Merge"])
app.include_router(qz_slice.router, prefix="/api/qz-slice", tags=["Qz Band Slice"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
@app.get("/api/health")
async def health():
    """Simple liveness + identity probe.

    The ``app`` field lets ``BackendManager._waitForHealth`` confirm it is
    talking to THIS backend and not another application (e.g. PolymCrystIndex)
    that happens to be answering on the same port — which previously masked a
    port collision and turned every /api/integration POST into a 405.

    Aliased at ``/api/health`` because the frontend api client (`getHealth`)
    talks to the ``/api`` base path.
    """
    return {"status": "ok", "app": "polymcrystrefine-pre", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# Serve frontend static files (production build)
# ---------------------------------------------------------------------------
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")


# ---------------------------------------------------------------------------
# Direct execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        # Local-only by default: the backend writes files and shells out to
        # local programs, so it must never be reachable from the network
        # unless the user explicitly forwards it.
        host=os.environ.get("PRE_HOST", "127.0.0.1"),
        port=PRE_PORT,
        reload=True,
    )
