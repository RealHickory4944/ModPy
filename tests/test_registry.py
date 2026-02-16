import pytest

import modpy as mp


def test_builtin_generator_is_registered() -> None:
    assert "minecraft-fabric-1.21.11" in mp.list_generators()


def test_unknown_generator_raises() -> None:
    with pytest.raises(KeyError):
        mp.Mod(author="tester", generator="does-not-exist")
