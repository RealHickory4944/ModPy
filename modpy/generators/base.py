"""Base classes for generators."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class GeneratorBase:
    key = ""
    element_types: dict[str, type[Any]] = {}

    def compile(self, mod: Any, output_dir: Path) -> Path:  # pragma: no cover - interface
        raise NotImplementedError
