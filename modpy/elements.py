"""Element model primitives."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable


class _ElementEventNamespace:
    def __init__(self, element: "BaseElement") -> None:
        self._element = element

    def __getattr__(self, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        if name not in self._element.EVENT_NAMES:
            raise AttributeError(f"{self._element.__class__.__name__} has no event '{name}'")

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            actions = self._element.mod._run_action_capture(func)
            self._element.events[name].append(actions)
            return func

        return decorator


class BaseElement:
    """Base class for generator-specific element definitions."""

    KIND = "element"
    EVENT_NAMES: tuple[str, ...] = ()

    def __init__(self, mod: Any, *, name: str | None = None, **properties: Any) -> None:
        self.mod = mod
        self.name = name or self.KIND
        self.properties = dict(properties)
        self.events: dict[str, list[list[dict[str, Any]]]] = defaultdict(list)
        self.Event = _ElementEventNamespace(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.KIND,
            "name": self.name,
            "properties": self.properties,
            "events": dict(self.events),
        }
