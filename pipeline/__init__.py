"""
disaster-intel pipeline package.
Sets up logging once — every module that imports from pipeline gets the same logger.
"""

import logging
from pipeline.config import LOG_DIR

# Create logs directory if it doesn't exist
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Logger setup ──────────────────────────────────────────────
# This runs once when the package is first imported.
# Every file then does: logger = logging.getLogger(__name__)
# and automatically gets this same configuration.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "pipeline.log", mode="a"),
    ],
)
