from pathlib import Path
import os

def project_root() -> Path:
    env_root = os.getenv("FINSENSE_PROJECT_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[2]

ROOT = project_root()
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
CONFIGS = ROOT / "configs"
