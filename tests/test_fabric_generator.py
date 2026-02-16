import json
from pathlib import Path

import modpy as mp
import pytest


def test_fabric_compile_generates_expanded_outputs(tmp_path: Path) -> None:
    item_texture = tmp_path / "ruby.png"
    item_texture.write_bytes(b"PNG")
    block_texture = tmp_path / "ruby_block.png"
    block_texture.write_bytes(b"PNG")

    external_hook = tmp_path / "ExternalHook.java"
    external_hook.write_text(
        "\n".join(
            [
                "public final class ExternalHook {",
                "    private ExternalHook() {}",
                "    public static void init() {}",
                "}",
            ]
        ),
        encoding="utf-8",
    )

    mod = mp.Mod(
        author="tester",
        generator="minecraft-fabric-1.21.11",
        mod_id="demo_mod",
        name="Demo Mod",
    )

    tab = mod.Tab(identifier="core", name="Core", icon="ruby")
    item = mod.Item(identifier="ruby", name="Ruby", texture=str(item_texture), creative_tab="core")
    block = mod.Block(
        identifier="ruby_block",
        name="Ruby Block",
        texture=str(block_texture),
        creative_tab="core",
        hardness=4.0,
        resistance=5.0,
        requires_tool=True,
    )
    recipe = mod.Recipe(
        recipe_type="shaped",
        identifier="ruby_block_from_ruby",
        output="ruby_block",
        pattern=["RRR", "RRR", "RRR"],
        key={"R": "ruby"},
    )
    tag = mod.Tag(registry="item", identifier="c:gems/ruby", values=["ruby"])
    command = mod.Command(literal="ruby", response="Ruby command executed", permission_level=2)
    entity = mod.Entity(
        identifier="ruby_guardian",
        name="Ruby Guardian",
        spawn_group="monster",
        max_health=40.0,
        movement_speed=0.3,
        attack_damage=7.0,
        spawn_egg_primary="#b90f3f",
        spawn_egg_secondary="#2c040f",
        creative_tab="core",
    )
    biome = mod.Biome(
        identifier="ruby_wastes",
        name="Ruby Wastes",
        temperature=2.0,
        downfall=0.0,
        has_precipitation=False,
    )
    worldgen = mod.Worldgen(
        worldgen_type="placed_feature",
        identifier="ruby_ore_patch",
        payload={"feature": "minecraft:ore_diamond", "placement": []},
    )
    inline_java = mod.JavaSource(
        class_name="InlineHook",
        entrypoint="main",
        initialize="init",
        source=(
            "public final class InlineHook {\n"
            "    private InlineHook() {}\n"
            "    public static void init() {}\n"
            "}"
        ),
    )
    file_java = mod.JavaSource(
        class_name="ExternalHook",
        source_file=str(external_hook),
        entrypoint="client",
        initialize="init",
    )

    @item.Event.Drop
    def on_drop() -> None:
        mod.sendConsole("say dropped ruby")

    @block.Event.Break
    def on_break() -> None:
        mod.sendConsole("say broke ruby block")

    @command.Event.Execute
    def on_command() -> None:
        mod.sendConsole("say ruby command triggered")

    @entity.Event.Spawn
    def on_spawn() -> None:
        mod.sendConsole("say ruby guardian spawned")

    mod.sendConsole("say startup")

    mod.add(tab)
    mod.add(item)
    mod.add(block)
    mod.add(recipe)
    mod.add(tag)
    mod.add(command)
    mod.add(entity)
    mod.add(biome)
    mod.add(worldgen)
    mod.add(inline_java)
    mod.add(file_java)
    output_root = mod.compile(tmp_path)

    assert (output_root / "gradlew").exists()
    assert (output_root / "gradlew.bat").exists()
    assert (output_root / "gradle/wrapper/gradle-wrapper.properties").exists()
    assert (output_root / "src/main/resources/fabric.mod.json").exists()
    assert (output_root / "src/main/resources/assets/demo_mod/models/item/ruby.json").exists()
    assert (output_root / "src/main/resources/assets/demo_mod/models/block/ruby_block.json").exists()
    assert (output_root / "src/main/resources/assets/demo_mod/blockstates/ruby_block.json").exists()
    assert (
        output_root / "src/main/resources/assets/demo_mod/models/item/ruby_guardian_spawn_egg.json"
    ).exists()
    assert (output_root / "src/main/resources/assets/demo_mod/textures/item/ruby.png").exists()
    assert (output_root / "src/main/resources/assets/demo_mod/textures/block/ruby_block.png").exists()
    assert (output_root / "src/main/resources/assets/demo_mod/lang/en_us.json").exists()
    assert (output_root / "src/main/resources/data/demo_mod/recipes/ruby_block_from_ruby.json").exists()
    assert (output_root / "src/main/resources/data/c/tags/items/gems/ruby.json").exists()
    assert (output_root / "src/main/resources/data/demo_mod/loot_tables/blocks/ruby_block.json").exists()
    assert (output_root / "src/main/resources/data/demo_mod/worldgen/biome/ruby_wastes.json").exists()
    assert (
        output_root / "src/main/resources/data/demo_mod/worldgen/placed_feature/ruby_ore_patch.json"
    ).exists()
    assert (output_root / "src/main/java/modpy/generated/demo_mod/InlineHook.java").exists()
    assert (output_root / "src/main/java/modpy/generated/demo_mod/ExternalHook.java").exists()
    assert (output_root / "src/main/java/modpy/generated/demo_mod/GeneratedCommands.java").exists()
    assert (output_root / "src/main/java/modpy/generated/demo_mod/GeneratedEntities.java").exists()
    assert (output_root / "src/main/java/modpy/generated/demo_mod/RubyGuardianEntity.java").exists()
    assert (output_root / "src/main/java/modpy/generated/demo_mod/DemoModModClient.java").exists()

    manifest_path = output_root / "src/main/resources/data/demo_mod/modpy/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fabric_meta = json.loads(
        (output_root / "src/main/resources/fabric.mod.json").read_text(encoding="utf-8")
    )
    lang_data = json.loads(
        (output_root / "src/main/resources/assets/demo_mod/lang/en_us.json").read_text(encoding="utf-8")
    )
    biome_data = json.loads(
        (
            output_root
            / "src/main/resources/data/demo_mod/worldgen/biome/ruby_wastes.json"
        ).read_text(encoding="utf-8")
    )
    worldgen_data = json.loads(
        (
            output_root
            / "src/main/resources/data/demo_mod/worldgen/placed_feature/ruby_ore_patch.json"
        ).read_text(encoding="utf-8")
    )
    commands_java = (output_root / "src/main/java/modpy/generated/demo_mod/GeneratedCommands.java").read_text(
        encoding="utf-8"
    )
    gradlew_text = (output_root / "gradlew").read_text(encoding="utf-8")
    gradle_properties_text = (output_root / "gradle.properties").read_text(encoding="utf-8")
    build_gradle_text = (output_root / "build.gradle").read_text(encoding="utf-8")
    wrapper_properties_text = (
        output_root / "gradle/wrapper/gradle-wrapper.properties"
    ).read_text(encoding="utf-8")

    assert manifest["generator"] == "minecraft-fabric-1.21.11"
    assert manifest["startup_actions"][0]["command"] == "say startup"
    assert any(element["kind"] == "command" for element in manifest["elements"])
    assert any(element["kind"] == "entity" for element in manifest["elements"])
    assert any(element["kind"] == "biome" for element in manifest["elements"])
    assert any(element["kind"] == "worldgen" for element in manifest["elements"])
    assert any(element["kind"] == "java_source" for element in manifest["elements"])
    assert item.to_dict()["events"]["Drop"][0][0]["command"] == "say dropped ruby"
    assert command.to_dict()["events"]["Execute"][0][0]["command"] == "say ruby command triggered"
    assert entity.to_dict()["events"]["Spawn"][0][0]["command"] == "say ruby guardian spawned"
    assert "CommandManager.literal(\"ruby\")" in commands_java
    assert lang_data["entity.demo_mod.ruby_guardian"] == "Ruby Guardian"
    assert "bootstrap" in gradlew_text.lower()
    assert "modpy-wrapper-bootstrap" in gradlew_text
    assert 'cd "$TMP_DIR"' in gradlew_text
    assert 'cd "$APP_HOME" && gradle wrapper' not in gradlew_text
    assert "loom_version=1.13.3" in gradle_properties_text
    assert "id 'fabric-loom' version '1.13.3'" in build_gradle_text
    assert "enableModProvidedJavadoc = false" in build_gradle_text
    assert "gradle-9.2.1-bin.zip" in wrapper_properties_text
    assert fabric_meta["entrypoints"]["client"][0].endswith("DemoModModClient")
    assert "spawners" in biome_data and "spawn_costs" in biome_data
    assert "features" in biome_data and "carvers" in biome_data
    assert "spawn_settings" not in biome_data and "generation_settings" not in biome_data
    assert worldgen_data["feature"] == "minecraft:ore_diamond_small"


def test_java_source_requires_single_source_input() -> None:
    mod = mp.Mod(author="tester", generator="minecraft-fabric-1.21.11", mod_id="demo_mod")

    with pytest.raises(ValueError):
        mod.JavaSource(class_name="Broken")

    with pytest.raises(ValueError):
        mod.JavaSource(
            class_name="Broken",
            source="public final class Broken {}",
            source_file="Broken.java",
        )
