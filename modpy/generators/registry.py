"""Generator registry."""

from __future__ import annotations

from .base import GeneratorBase


_GENERATORS: dict[str, GeneratorBase] = {}


def register_generator(generator: GeneratorBase, *, replace: bool = False) -> None:
    key = generator.key
    if not key:
        raise ValueError("Generator key must be a non-empty string")
    if key in _GENERATORS and not replace:
        raise KeyError(f"Generator '{key}' is already registered")
    _GENERATORS[key] = generator


def get_generator(key: str) -> GeneratorBase:
    try:
        return _GENERATORS[key]
    except KeyError as exc:
        raise KeyError(key) from exc


def list_generators() -> list[str]:
    return sorted(_GENERATORS)
