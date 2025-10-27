from dataclasses import dataclass, field
from pathlib import Path
import yaml
from .paths import CONFIGS

@dataclass
class ParseConfig:
    assume_timezone: str = "US/Eastern"
    detect_qa_markers: bool = True
    speaker_line_regex: str = r'^(Operator|Q&A|Question-and-Answer Session|[A-Z][A-Z .,&()/-]{2,}):\s*'

@dataclass
class OutputConfig:
    parquet_path: str = "data/processed/transcripts.parquet"

@dataclass
class AppConfig:
    project_name: str = "FinSense"
    default_source: str = "manual_drop"
    parse: ParseConfig = field(default_factory=ParseConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

def load_config(path: Path | None = None) -> AppConfig:
    cfg_path = path or (CONFIGS / "finsense.yaml")
    with open(cfg_path, "r") as f:
        raw = yaml.safe_load(f) or {}
    parse = raw.get("parse", {})
    output = raw.get("output", {})
    return AppConfig(
        project_name=raw.get("project_name", "FinSense"),
        default_source=raw.get("default_source", "manual_drop"),
        parse=ParseConfig(**parse),
        output=OutputConfig(**output),
    )
