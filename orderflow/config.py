"""Runtime configuration. Everything comes from environment variables, never from code."""

import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///orderflow.db")
DATA_DIR = Path(os.getenv("DATA_DIR", "data/raw"))
REPORT_DIR = Path(os.getenv("REPORT_DIR", "reports"))
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_PREFIX = os.getenv("S3_PREFIX", "orderflow")
