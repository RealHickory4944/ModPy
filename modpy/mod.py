"""Top-level Mod model."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .generators.registry import get_generator


class Mod:
    def __init__(
        self,
        *,
        author: str,
        generator: str,
        mod_id: str = "examplemod",
        name: str = "Example Mod",
        version: str = "0.1.0",
    ) -> None:
        self.author = author
        self.mod_id = mod_id
        self.name = name
        self.version = version
        self.generator = generator

        self.elements: list[Any] = []
        self.startup_actions: list[dict[str, Any]] = []
        self._action_capture_stack: list[list[dict[str, Any]]] = []

        self._generator = get_generator(generator)

    def __getattr__(self, name: str) -> Callable[..., Any]:
        element_type = self._generator.element_types.get(name)
        if element_type is None:
            raise AttributeError(name)

        def factory(*args: Any, **kwargs: Any) -> Any:
            return element_type(self, *args, **kwargs)

        return factory

    def _run_action_capture(self, func: Callable[..., Any]) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        self._action_capture_stack.append(actions)
        try:
            func()
        finally:
            self._action_capture_stack.pop()
        return actions

    def sendConsole(self, command: str) -> None:
        action = {"type": "console", "command": str(command)}
        if self._action_capture_stack:
            self._action_capture_stack[-1].append(action)
        else:
            self.startup_actions.append(action)

    def add(self, element: Any) -> Any:
        self.elements.append(element)
        return element

    def to_manifest(self) -> dict[str, Any]:
        return {
            "author": self.author,
            "generator": self.generator,
            "mod_id": self.mod_id,
            "name": self.name,
            "version": self.version,
            "startup_actions": list(self.startup_actions),
            "elements": [element.to_dict() for element in self.elements],
        }

    def compile(self, output_dir: str | Path = "build") -> Path:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        return self._generator.compile(self, output)
