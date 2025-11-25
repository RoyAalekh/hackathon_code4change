from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any, Dict, Literal

from .config_models import GenerateConfig, SimulateConfig, WorkflowConfig


def _read_config(path: Path) -> Dict[str, Any]:
    suf = path.suffix.lower()
    if suf == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if suf == ".toml":
        return tomllib.loads(path.read_text(encoding="utf-8"))
    raise ValueError(f"Unsupported config format: {path.suffix}. Use .toml or .json")


def load_generate_config(path: Path) -> GenerateConfig:
    data = _read_config(path)
    return GenerateConfig(**data)


def load_simulate_config(path: Path) -> SimulateConfig:
    data = _read_config(path)
    return SimulateConfig(**data)


def load_workflow_config(path: Path) -> WorkflowConfig:
    data = _read_config(path)
    return WorkflowConfig(**data)