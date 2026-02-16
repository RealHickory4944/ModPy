from pathlib import Path

import pytest

import modpy as mp
from modpy.elements import BaseElement
from modpy.generators.base import GeneratorBase


class Spell(BaseElement):
    KIND = "spell"
    EVENT_NAMES = ("Cast",)

    def __init__(self, mod: mp.Mod, *, mana_cost: int = 1, name: str | None = None) -> None:
        super().__init__(mod, name=name, mana_cost=mana_cost)


class NoItemGenerator(GeneratorBase):
    key = "demo-no-item-1.0"
    element_types = {"Spell": Spell}

    def compile(self, mod: mp.Mod, output_dir: Path) -> Path:
        out_file = Path(output_dir) / "demo-no-item-1.0.txt"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(mod.name, encoding="utf-8")
        return out_file


def test_generators_expose_own_classes(tmp_path: Path) -> None:
    mp.register_generator(NoItemGenerator(), replace=True)
    mod = mp.Mod(author="author", generator="demo-no-item-1.0", name="Arcana")

    assert callable(mod.Spell)
    with pytest.raises(AttributeError):
        _ = mod.Item

    spell = mod.Spell(name="fireball", mana_cost=10)

    @spell.Event.Cast
    def on_cast() -> None:
        mod.sendConsole("cast fireball")

    mod.add(spell)
    compiled_path = mod.compile(tmp_path)
    assert compiled_path.exists()
