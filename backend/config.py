"""
Global configuration for the PolymCrystRefine data-processing backend.
"""

import os
import tempfile

# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------
UPLOAD_DIR: str = os.path.join(tempfile.gettempdir(), "polymcrystrefine_uploads")
OUTPUT_DIR: str = os.path.join(tempfile.gettempdir(), "polymcrystrefine_outputs")

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------
MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500 MB

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
# Dedicated port for the PRE / PolymCrystRefine data-processing backend.
# Must stay OUTSIDE PolymCrystIndex's port-scan window (18700–18719); the
# Electron BackendManager additionally falls back to 18731+ on collisions.
PRE_PORT: int = int(os.environ.get("PRE_PORT", "18730"))
