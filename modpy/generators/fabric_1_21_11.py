"""Minecraft Fabric 1.21.11 generator."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
import shutil
from textwrap import dedent
from typing import Any

from ..elements import BaseElement
from .base import GeneratorBase


_RARITIES = {"common": "COMMON", "uncommon": "UNCOMMON", "rare": "RARE", "epic": "EPIC"}
_RECIPE_TYPES = {"shaped", "shapeless", "smelting", "blasting", "smoking", "campfire_cooking"}
_SPAWN_GROUPS = {
    "monster": "MONSTER",
    "creature": "CREATURE",
    "ambient": "AMBIENT",
    "water_creature": "WATER_CREATURE",
    "water_ambient": "WATER_AMBIENT",
    "underground_water_creature": "UNDERGROUND_WATER_CREATURE",
    "axolotls": "AXOLOTLS",
    "misc": "MISC",
}
_GRADLE_VERSION = "9.2.1"
_WORLDGEN_FEATURE_ALIASES = {
    # In 1.21.11 this placed-feature id is commonly mistaken for a configured-feature id.
    "minecraft:ore_diamond": "minecraft:ore_diamond_small",
}


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _camel(value: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", value) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) or "Generated"


def _java_const(value: str) -> str:
    constant = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper()
    return constant or "UNNAMED"


def _package_safe(value: str, fallback: str) -> str:
    fragment = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    return fragment or fallback


def _java_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _normalize_id_path(value: str | None, fallback: str) -> str:
    raw = (value or "").lower().strip()
    raw = raw.replace(" ", "_")
    normalized = re.sub(r"[^a-z0-9/._-]+", "_", raw)
    normalized = re.sub(r"_+", "_", normalized).strip("_./-")
    return normalized or fallback


def _normalize_command_literal(value: str | None, fallback: str) -> str:
    raw = (value or "").lower().strip().replace(" ", "_")
    normalized = re.sub(r"[^a-z0-9_]+", "", raw)
    return normalized or fallback


def _split_namespaced_id(value: str, default_namespace: str) -> tuple[str, str]:
    if ":" in value:
        namespace, path = value.split(":", 1)
        return _normalize_id_path(namespace, default_namespace), _normalize_id_path(path, "generated")
    return default_namespace, _normalize_id_path(value, "generated")


def _display_name(identifier: str) -> str:
    words = re.split(r"[_/.-]+", identifier)
    return " ".join(word.capitalize() for word in words if word) or "Generated"


def _copy_file_if_exists(source: str | None, target: Path) -> bool:
    if not source:
        return False
    source_path = Path(source)
    if not source_path.exists() or not source_path.is_file():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)
    return True


def _extract_package(source: str) -> str | None:
    match = re.search(r"^\s*package\s+([a-zA-Z_][\w.]*)\s*;", source, flags=re.MULTILINE)
    return match.group(1) if match else None


def _extract_class_name(source: str) -> str | None:
    match = re.search(r"\b(?:class|interface|enum)\s+([A-Za-z_]\w*)\b", source)
    return match.group(1) if match else None


def _is_literal_identifier(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9_.-]+:[a-z0-9/._-]+", value))


def _resolve_item_like_id(
    value: str,
    *,
    mod_id: str,
    generated_items: set[str],
    generated_blocks: set[str],
) -> str:
    if _is_literal_identifier(value):
        return value
    normalized = _normalize_id_path(value, "generated")
    if normalized in generated_items or normalized in generated_blocks:
        return f"{mod_id}:{normalized}"
    return f"minecraft:{normalized}"


def _commands_from_actions(actions: list[dict[str, Any]]) -> list[str]:
    commands: list[str] = []
    for action in actions:
        if action.get("type") == "console" and action.get("command"):
            commands.append(str(action["command"]))
    return commands


def _spawn_group_constant(value: str) -> str:
    return _SPAWN_GROUPS.get(value.lower().strip(), "CREATURE")


def _parse_color(value: int | str | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return max(0, min(value, 0xFFFFFF))
    text = str(value).strip().lower()
    if text.startswith("#"):
        text = text[1:]
    if text.startswith("0x"):
        text = text[2:]
    if not re.fullmatch(r"[0-9a-f]{1,6}", text):
        raise ValueError(f"Invalid RGB color value: {value!r}")
    return int(text, 16)


def _deep_json_copy(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload))


def _rgb_hex(value: int) -> str:
    return f"#{max(0, min(int(value), 0xFFFFFF)):06x}"


class FabricTab(BaseElement):
    KIND = "tab"
    EVENT_NAMES = ()

    def __init__(
        self,
        mod: Any,
        *,
        identifier: str | None = None,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        tab_id = _normalize_id_path(identifier or name, "tab")
        display_name = name or _display_name(tab_id)
        super().__init__(mod, name=tab_id, identifier=tab_id, display_name=display_name, icon=icon)


class FabricItem(BaseElement):
    KIND = "item"
    EVENT_NAMES = ("Drop", "Use")

    def __init__(
        self,
        mod: Any,
        *,
        identifier: str | None = None,
        name: str | None = None,
        texture: str | None = None,
        model: str | None = None,
        creative_tab: str | None = None,
        max_count: int = 64,
        durability: int | None = None,
        fireproof: bool = False,
        rarity: str = "common",
    ) -> None:
        item_id = _normalize_id_path(identifier or name, "item")
        display_name = name or _display_name(item_id)
        rarity_name = _RARITIES.get(rarity.lower(), "COMMON")
        super().__init__(
            mod,
            name=item_id,
            identifier=item_id,
            display_name=display_name,
            texture=texture,
            model=model,
            creative_tab=_normalize_id_path(creative_tab, "") if creative_tab else None,
            max_count=max(1, int(max_count)),
            durability=max(1, int(durability)) if durability is not None else None,
            fireproof=bool(fireproof),
            rarity=rarity_name,
        )


class FabricBlock(BaseElement):
    KIND = "block"
    EVENT_NAMES = ("Break", "Place")

    def __init__(
        self,
        mod: Any,
        *,
        identifier: str | None = None,
        name: str | None = None,
        texture: str | None = None,
        model: str | None = None,
        hardness: float = 1.5,
        resistance: float | None = None,
        luminance: int = 0,
        requires_tool: bool = False,
        creative_tab: str | None = None,
    ) -> None:
        block_id = _normalize_id_path(identifier or name, "block")
        display_name = name or _display_name(block_id)
        resistance_value = float(resistance) if resistance is not None else float(hardness)
        super().__init__(
            mod,
            name=block_id,
            identifier=block_id,
            display_name=display_name,
            texture=texture,
            model=model,
            hardness=float(hardness),
            resistance=resistance_value,
            luminance=max(0, int(luminance)),
            requires_tool=bool(requires_tool),
            creative_tab=_normalize_id_path(creative_tab, "") if creative_tab else None,
        )


class FabricRecipe(BaseElement):
    KIND = "recipe"
    EVENT_NAMES = ()

    def __init__(
        self,
        mod: Any,
        *,
        recipe_type: str,
        output: str,
        identifier: str | None = None,
        count: int = 1,
        pattern: list[str] | None = None,
        key: dict[str, str] | None = None,
        ingredients: list[str] | None = None,
        input_item: str | None = None,
        experience: float = 0.0,
        cooking_time: int = 200,
    ) -> None:
        kind = recipe_type.lower().strip()
        if kind not in _RECIPE_TYPES:
            supported = ", ".join(sorted(_RECIPE_TYPES))
            raise ValueError(f"Unsupported recipe_type '{recipe_type}'. Supported: {supported}")
        if kind == "shaped" and (not pattern or not key):
            raise ValueError("Shaped recipes require `pattern` and `key`.")
        if kind == "shapeless" and not ingredients:
            raise ValueError("Shapeless recipes require `ingredients`.")
        if kind in {"smelting", "blasting", "smoking", "campfire_cooking"} and not input_item:
            raise ValueError(f"{kind} recipes require `input_item`.")

        recipe_id = _normalize_id_path(identifier or f"{kind}_{output}", f"{kind}_recipe")
        super().__init__(
            mod,
            name=recipe_id,
            identifier=recipe_id,
            recipe_type=kind,
            output=output,
            count=max(1, int(count)),
            pattern=list(pattern or []),
            key=dict(key or {}),
            ingredients=list(ingredients or []),
            input_item=input_item,
            experience=float(experience),
            cooking_time=max(1, int(cooking_time)),
        )


class FabricTag(BaseElement):
    KIND = "tag"
    EVENT_NAMES = ()

    def __init__(
        self,
        mod: Any,
        *,
        registry: str,
        identifier: str,
        values: list[str],
        replace: bool = False,
    ) -> None:
        reg = registry.lower().strip()
        if reg not in {"item", "block"}:
            raise ValueError("Tag `registry` must be 'item' or 'block'.")
        ns, path = _split_namespaced_id(identifier, mod.mod_id)
        name = _normalize_id_path(f"{ns}_{path}", "tag")
        super().__init__(
            mod,
            name=name,
            registry=reg,
            namespace=ns,
            identifier=path,
            values=list(values),
            replace=bool(replace),
        )


class FabricJavaSource(BaseElement):
    KIND = "java_source"
    EVENT_NAMES = ()

    def __init__(
        self,
        mod: Any,
        *,
        class_name: str | None = None,
        source: str | None = None,
        source_file: str | None = None,
        package: str | None = None,
        entrypoint: str = "none",
        initialize: str | None = None,
        identifier: str | None = None,
    ) -> None:
        if bool(source) == bool(source_file):
            raise ValueError("Provide exactly one of `source` or `source_file`.")

        entrypoint_name = entrypoint.lower().strip()
        if entrypoint_name not in {"none", "main", "client", "server"}:
            raise ValueError("entrypoint must be one of: none, main, client, server.")

        resolved_class = class_name
        if source and not resolved_class:
            resolved_class = _extract_class_name(source)
        if source_file and not resolved_class:
            resolved_class = Path(source_file).stem
        resolved_class = resolved_class or "InjectedJavaSource"

        init_method = initialize
        if entrypoint_name != "none" and init_method is None:
            init_method = "init"

        source_id = _normalize_id_path(identifier or resolved_class, "java_source")
        super().__init__(
            mod,
            name=source_id,
            class_name=resolved_class,
            source=source,
            source_file=source_file,
            package=package,
            entrypoint=entrypoint_name,
            initialize=init_method,
        )


class FabricCommand(BaseElement):
    KIND = "command"
    EVENT_NAMES = ("Execute",)

    def __init__(
        self,
        mod: Any,
        *,
        literal: str | None = None,
        identifier: str | None = None,
        name: str | None = None,
        permission_level: int = 2,
        response: str | None = None,
    ) -> None:
        literal_name = _normalize_command_literal(literal or identifier or name, "modpy")
        command_id = _normalize_id_path(identifier or literal_name, literal_name)
        display_name = name or _display_name(command_id)
        super().__init__(
            mod,
            name=command_id,
            identifier=command_id,
            literal=literal_name,
            display_name=display_name,
            permission_level=max(0, int(permission_level)),
            response=response,
        )


class FabricEntity(BaseElement):
    KIND = "entity"
    EVENT_NAMES = ("Spawn", "Death")

    def __init__(
        self,
        mod: Any,
        *,
        identifier: str | None = None,
        name: str | None = None,
        spawn_group: str = "creature",
        width: float = 0.6,
        height: float = 1.95,
        max_health: float = 20.0,
        movement_speed: float = 0.25,
        attack_damage: float = 2.0,
        creative_tab: str | None = None,
        spawn_egg_primary: int | str | None = None,
        spawn_egg_secondary: int | str | None = None,
        tracking_range: int = 8,
        tracked_update_rate: int = 3,
        force_tracked_velocity_updates: bool = False,
    ) -> None:
        entity_id = _normalize_id_path(identifier or name, "entity")
        display_name = name or _display_name(entity_id)

        primary = _parse_color(spawn_egg_primary)
        secondary = _parse_color(spawn_egg_secondary)
        if primary is not None and secondary is None:
            secondary = primary
        if secondary is not None and primary is None:
            primary = secondary

        super().__init__(
            mod,
            name=entity_id,
            identifier=entity_id,
            display_name=display_name,
            spawn_group=_spawn_group_constant(spawn_group),
            width=max(0.1, float(width)),
            height=max(0.1, float(height)),
            max_health=max(1.0, float(max_health)),
            movement_speed=max(0.01, float(movement_speed)),
            attack_damage=max(0.0, float(attack_damage)),
            creative_tab=_normalize_id_path(creative_tab, "") if creative_tab else None,
            spawn_egg_primary=primary,
            spawn_egg_secondary=secondary,
            tracking_range=max(1, int(tracking_range)),
            tracked_update_rate=max(1, int(tracked_update_rate)),
            force_tracked_velocity_updates=bool(force_tracked_velocity_updates),
        )


class FabricBiome(BaseElement):
    KIND = "biome"
    EVENT_NAMES = ()

    def __init__(
        self,
        mod: Any,
        *,
        identifier: str | None = None,
        name: str | None = None,
        namespace: str | None = None,
        payload: dict[str, Any] | None = None,
        payload_file: str | None = None,
        temperature: float = 0.8,
        downfall: float = 0.4,
        has_precipitation: bool = True,
        sky_color: int = 7907327,
        fog_color: int = 12638463,
        water_color: int = 4159204,
        water_fog_color: int = 329011,
    ) -> None:
        if payload is not None and payload_file is not None:
            raise ValueError("Provide at most one of `payload` or `payload_file` for Biome.")

        biome_id = _normalize_id_path(identifier or name, "biome")
        display_name = name or _display_name(biome_id)
        biome_namespace = _normalize_id_path(namespace, mod.mod_id) if namespace else mod.mod_id

        super().__init__(
            mod,
            name=biome_id,
            identifier=biome_id,
            display_name=display_name,
            namespace=biome_namespace,
            payload=_deep_json_copy(payload) if payload is not None else None,
            payload_file=payload_file,
            temperature=float(temperature),
            downfall=float(downfall),
            has_precipitation=bool(has_precipitation),
            sky_color=max(0, int(sky_color)),
            fog_color=max(0, int(fog_color)),
            water_color=max(0, int(water_color)),
            water_fog_color=max(0, int(water_fog_color)),
        )


class FabricWorldgen(BaseElement):
    KIND = "worldgen"
    EVENT_NAMES = ()

    def __init__(
        self,
        mod: Any,
        *,
        worldgen_type: str,
        identifier: str,
        namespace: str | None = None,
        payload: dict[str, Any] | None = None,
        payload_file: str | None = None,
    ) -> None:
        if payload is not None and payload_file is not None:
            raise ValueError("Provide at most one of `payload` or `payload_file` for Worldgen.")

        wg_type = _normalize_id_path(worldgen_type, "placed_feature")
        wg_id = _normalize_id_path(identifier, "worldgen")
        wg_namespace = _normalize_id_path(namespace, mod.mod_id) if namespace else mod.mod_id

        super().__init__(
            mod,
            name=_normalize_id_path(f"{wg_type}_{wg_id}", "worldgen"),
            worldgen_type=wg_type,
            identifier=wg_id,
            namespace=wg_namespace,
            payload=_deep_json_copy(payload) if payload is not None else None,
            payload_file=payload_file,
        )


class Fabric12111Generator(GeneratorBase):
    key = "minecraft-fabric-1.21.11"
    element_types = {
        "Tab": FabricTab,
        "Item": FabricItem,
        "Block": FabricBlock,
        "Recipe": FabricRecipe,
        "Tag": FabricTag,
        "JavaSource": FabricJavaSource,
        "Command": FabricCommand,
        "Entity": FabricEntity,
        "Biome": FabricBiome,
        "Worldgen": FabricWorldgen,
    }

    minecraft_version = "1.21.11"
    yarn_mappings = "1.21.11+build.1"
    loom_version = "1.13.3"
    loader_version = "0.18.2"
    fabric_api_version = "0.139.4+1.21.11"

    def compile(self, mod: Any, output_dir: Path) -> Path:
        root = output_dir / f"{mod.mod_id}-fabric-{self.minecraft_version}"
        if root.exists():
            shutil.rmtree(root)

        package_mod_fragment = _package_safe(mod.mod_id, "generated")
        package_name = f"modpy.generated.{package_mod_fragment}"
        package_dir = root / "src" / "main" / "java" / Path(package_name.replace(".", "/"))
        resources_dir = root / "src" / "main" / "resources"
        assets_dir = resources_dir / "assets" / mod.mod_id
        data_dir = resources_dir / "data"
        manifest_dir = data_dir / mod.mod_id / "modpy"
        main_class = f"{_camel(mod.mod_id)}Mod"
        author_fragment = _package_safe(mod.author, "author")

        tabs = [element for element in mod.elements if isinstance(element, FabricTab)]
        items = [element for element in mod.elements if isinstance(element, FabricItem)]
        blocks = [element for element in mod.elements if isinstance(element, FabricBlock)]
        recipes = [element for element in mod.elements if isinstance(element, FabricRecipe)]
        tags = [element for element in mod.elements if isinstance(element, FabricTag)]
        java_sources = [element for element in mod.elements if isinstance(element, FabricJavaSource)]
        commands = [element for element in mod.elements if isinstance(element, FabricCommand)]
        entities = [element for element in mod.elements if isinstance(element, FabricEntity)]
        biomes = [element for element in mod.elements if isinstance(element, FabricBiome)]
        worldgens = [element for element in mod.elements if isinstance(element, FabricWorldgen)]

        startup_commands = _commands_from_actions(list(mod.startup_actions))

        injected_hooks = self._write_injected_java(root, package_name, java_sources)
        has_client = bool(injected_hooks["client"])
        has_server = bool(injected_hooks["server"])
        self._write_gradle_files(root, mod, author_fragment)
        self._write_fabric_metadata(resources_dir, mod, package_name, main_class, has_client, has_server)
        self._write_manifest(manifest_dir, mod)
        self._write_java_files(
            package_dir=package_dir,
            mod=mod,
            main_class=main_class,
            tabs=tabs,
            items=items,
            blocks=blocks,
            commands=commands,
            entities=entities,
            startup_commands=startup_commands,
            hooks=injected_hooks,
            write_client_entrypoint=has_client,
            write_server_entrypoint=has_server,
        )
        self._write_assets(assets_dir, mod.mod_id, tabs, items, blocks, entities)
        self._write_data_files(data_dir, mod.mod_id, items, blocks, recipes, tags, biomes, worldgens)
        self._write_readme(root, mod)
        return root

    def _write_gradle_files(self, root: Path, mod: Any, author_fragment: str) -> None:
        _write_text(
            root / "settings.gradle",
            dedent(
                f"""
                pluginManagement {{
                    repositories {{
                        maven {{ url = "https://maven.fabricmc.net/" }}
                        gradlePluginPortal()
                    }}
                }}

                rootProject.name = "{mod.mod_id}"
                """
            ),
        )

        _write_text(
            root / "gradle.properties",
            dedent(
                f"""
                org.gradle.jvmargs=-Xmx2G
                org.gradle.parallel=true
                org.gradle.configuration-cache=false

                minecraft_version={self.minecraft_version}
                yarn_mappings={self.yarn_mappings}
                loom_version={self.loom_version}
                loader_version={self.loader_version}
                fabric_version={self.fabric_api_version}
                mod_version={mod.version}
                maven_group=modpy.generated.{author_fragment}
                archives_base_name={mod.mod_id}
                """
            ),
        )

        _write_text(
            root / "build.gradle",
            dedent(
                f"""
                plugins {{
                    id 'fabric-loom' version '{self.loom_version}'
                    id 'maven-publish'
                }}

                loom {{
                    enableModProvidedJavadoc = false
                }}

                version = project.mod_version
                group = project.maven_group

                base {{
                    archivesName = project.archives_base_name
                }}

                repositories {{
                    mavenCentral()
                    maven {{ url "https://maven.fabricmc.net/" }}
                }}

                dependencies {{
                    minecraft "com.mojang:minecraft:${{project.minecraft_version}}"
                    mappings "net.fabricmc:yarn:${{project.yarn_mappings}}:v2"
                    modImplementation "net.fabricmc:fabric-loader:${{project.loader_version}}"
                    modImplementation "net.fabricmc.fabric-api:fabric-api:${{project.fabric_version}}"
                }}

                processResources {{
                    inputs.property "version", project.version
                    filesMatching("fabric.mod.json") {{
                        expand "version": project.version
                    }}
                }}

                tasks.withType(JavaCompile).configureEach {{
                    it.options.release = 21
                }}

                java {{
                    sourceCompatibility = JavaVersion.VERSION_21
                    targetCompatibility = JavaVersion.VERSION_21
                    withSourcesJar()
                }}
                """
            ),
        )

        self._write_gradle_wrapper_bootstrap(root)

    def _write_gradle_wrapper_bootstrap(self, root: Path) -> None:
        _write_text(
            root / "gradle" / "wrapper" / "gradle-wrapper.properties",
            dedent(
                f"""
                distributionBase=GRADLE_USER_HOME
                distributionPath=wrapper/dists
                distributionUrl=https\\://services.gradle.org/distributions/gradle-{_GRADLE_VERSION}-bin.zip
                networkTimeout=10000
                validateDistributionUrl=true
                zipStoreBase=GRADLE_USER_HOME
                zipStorePath=wrapper/dists
                """
            ),
        )

        gradlew_path = root / "gradlew"
        _write_text(
            gradlew_path,
            dedent(
                f"""
                #!/usr/bin/env sh
                set -eu

                APP_HOME="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
                WRAPPER_JAR="$APP_HOME/gradle/wrapper/gradle-wrapper.jar"

                if [ ! -f "$WRAPPER_JAR" ]; then
                    if ! command -v gradle >/dev/null 2>&1; then
                        echo "Gradle wrapper JAR missing and 'gradle' is not installed." >&2
                        echo "Install Gradle once, rerun ./gradlew build, and the wrapper will bootstrap." >&2
                        exit 1
                    fi

                    echo "Gradle wrapper JAR missing. Bootstrapping with installed Gradle..."
                    TMP_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t modpy-gradle-wrapper)"
                    trap 'rm -rf "$TMP_DIR"' EXIT INT TERM

                    cat > "$TMP_DIR/settings.gradle" <<'EOF'
rootProject.name = "modpy-wrapper-bootstrap"
EOF
                    cat > "$TMP_DIR/build.gradle" <<'EOF'
tasks.register("noop")
EOF

                    (
                        cd "$TMP_DIR"
                        gradle -q wrapper --gradle-version {_GRADLE_VERSION} --no-daemon
                    )

                    if [ ! -f "$TMP_DIR/gradle/wrapper/gradle-wrapper.jar" ]; then
                        echo "Failed to generate gradle-wrapper.jar during bootstrap." >&2
                        exit 1
                    fi

                    mkdir -p "$APP_HOME/gradle/wrapper"
                    cp "$TMP_DIR/gradle/wrapper/gradle-wrapper.jar" "$WRAPPER_JAR"
                    trap - EXIT INT TERM
                    rm -rf "$TMP_DIR"
                fi

                if [ ! -f "$WRAPPER_JAR" ]; then
                    echo "Gradle wrapper JAR is still missing after bootstrap." >&2
                    exit 1
                fi

                exec java -Xmx64m -Xms64m -classpath "$WRAPPER_JAR" org.gradle.wrapper.GradleWrapperMain "$@"
                """
            ),
        )
        gradlew_path.chmod(0o755)

        _write_text(
            root / "gradlew.bat",
            dedent(
                f"""
                @ECHO OFF
                SETLOCAL
                SET APP_HOME=%~dp0
                SET WRAPPER_JAR=%APP_HOME%gradle\\wrapper\\gradle-wrapper.jar

                IF EXIST "%WRAPPER_JAR%" GOTO run

                where gradle >NUL 2>NUL
                IF ERRORLEVEL 1 (
                    ECHO Gradle wrapper JAR missing and Gradle is not installed.
                    ECHO Install Gradle once, rerun gradlew.bat build, and the wrapper will bootstrap.
                    EXIT /B 1
                )

                ECHO Gradle wrapper JAR missing. Bootstrapping with installed Gradle...
                SET TMP_DIR=%TEMP%\\modpy_gradle_wrapper_%RANDOM%%RANDOM%
                IF EXIST "%TMP_DIR%" RMDIR /S /Q "%TMP_DIR%"
                MKDIR "%TMP_DIR%"
                (
                    ECHO rootProject.name = "modpy-wrapper-bootstrap"
                ) > "%TMP_DIR%\\settings.gradle"
                (
                    ECHO tasks.register("noop")
                ) > "%TMP_DIR%\\build.gradle"

                PUSHD "%TMP_DIR%"
                gradle -q wrapper --gradle-version {_GRADLE_VERSION} --no-daemon
                SET WRAP_ERR=%ERRORLEVEL%
                POPD
                IF NOT "%WRAP_ERR%"=="0" EXIT /B %WRAP_ERR%

                IF NOT EXIST "%TMP_DIR%\\gradle\\wrapper\\gradle-wrapper.jar" (
                    ECHO Failed to generate gradle-wrapper.jar during bootstrap.
                    RMDIR /S /Q "%TMP_DIR%"
                    EXIT /B 1
                )

                IF NOT EXIST "%APP_HOME%gradle\\wrapper" MKDIR "%APP_HOME%gradle\\wrapper"
                COPY /Y "%TMP_DIR%\\gradle\\wrapper\\gradle-wrapper.jar" "%WRAPPER_JAR%" >NUL
                RMDIR /S /Q "%TMP_DIR%"

                IF NOT EXIST "%WRAPPER_JAR%" (
                    ECHO Gradle wrapper JAR is still missing after bootstrap.
                    EXIT /B 1
                )

                :run
                java -Xmx64m -Xms64m -classpath "%WRAPPER_JAR%" org.gradle.wrapper.GradleWrapperMain %*
                ENDLOCAL
                """
            ),
        )

    def _write_fabric_metadata(
        self,
        resources_dir: Path,
        mod: Any,
        package_name: str,
        main_class: str,
        has_client: bool,
        has_server: bool,
    ) -> None:
        entrypoints: dict[str, list[str]] = {"main": [f"{package_name}.{main_class}"]}
        if has_client:
            entrypoints["client"] = [f"{package_name}.{main_class}Client"]
        if has_server:
            entrypoints["server"] = [f"{package_name}.{main_class}Server"]

        payload = {
            "schemaVersion": 1,
            "id": mod.mod_id,
            "version": "${version}",
            "name": mod.name,
            "description": "Generated by ModPy",
            "authors": [mod.author],
            "license": "MIT",
            "environment": "*",
            "entrypoints": entrypoints,
            "depends": {
                "fabricloader": f">={self.loader_version}",
                "minecraft": f"~{self.minecraft_version}",
                "fabric-api": "*",
            },
        }
        _write_json(resources_dir / "fabric.mod.json", payload)

    def _write_manifest(self, manifest_dir: Path, mod: Any) -> None:
        manifest = mod.to_manifest()
        manifest["generator_details"] = {
            "minecraft_version": self.minecraft_version,
            "loader_version": self.loader_version,
            "fabric_api_version": self.fabric_api_version,
        }
        _write_json(manifest_dir / "manifest.json", manifest)

    def _write_java_files(
        self,
        *,
        package_dir: Path,
        mod: Any,
        main_class: str,
        tabs: list[FabricTab],
        items: list[FabricItem],
        blocks: list[FabricBlock],
        commands: list[FabricCommand],
        entities: list[FabricEntity],
        startup_commands: list[str],
        hooks: dict[str, list[tuple[str, str]]],
        write_client_entrypoint: bool,
        write_server_entrypoint: bool,
    ) -> None:
        package_name = package_dir.as_posix().split("/src/main/java/")[-1].replace("/", ".")

        item_consts = {item.name: _java_const(item.name) for item in items}
        block_consts = {block.name: _java_const(block.name) for block in blocks}
        tab_consts = {tab.name: _java_const(tab.name) for tab in tabs}
        entity_consts = {entity.name: _java_const(entity.name) for entity in entities}
        entity_classes = {entity.name: f"{_camel(entity.name)}Entity" for entity in entities}

        entity_spawn_eggs = self._write_entities(
            package_dir=package_dir,
            package_name=package_name,
            main_class=main_class,
            entities=entities,
            entity_consts=entity_consts,
            entity_classes=entity_classes,
        )
        self._write_main_mod(package_dir, package_name, main_class, mod, write_client_entrypoint, write_server_entrypoint)
        self._write_items(package_dir, package_name, main_class, items, item_consts)
        self._write_blocks(package_dir, package_name, main_class, blocks, block_consts)
        self._write_commands(package_dir, package_name, main_class, commands)
        self._write_item_groups(
            package_dir=package_dir,
            package_name=package_name,
            main_class=main_class,
            mod_id=mod.mod_id,
            tabs=tabs,
            items=items,
            blocks=blocks,
            entities=entities,
            item_consts=item_consts,
            block_consts=block_consts,
            tab_consts=tab_consts,
            entity_spawn_egg_consts=entity_spawn_eggs,
        )
        self._write_events(
            package_dir=package_dir,
            package_name=package_name,
            main_class=main_class,
            items=items,
            blocks=blocks,
            entities=entities,
            item_consts=item_consts,
            block_consts=block_consts,
            entity_consts=entity_consts,
            startup_commands=startup_commands,
        )
        self._write_injected_hook_class(package_dir, package_name, "GeneratedInjectedMain", hooks["main"])
        self._write_injected_hook_class(package_dir, package_name, "GeneratedInjectedClient", hooks["client"])
        self._write_injected_hook_class(package_dir, package_name, "GeneratedInjectedServer", hooks["server"])

    def _write_main_mod(
        self,
        package_dir: Path,
        package_name: str,
        main_class: str,
        mod: Any,
        write_client_entrypoint: bool,
        write_server_entrypoint: bool,
    ) -> None:
        _write_text(
            package_dir / f"{main_class}.java",
            dedent(
                f"""
                package {package_name};

                import net.fabricmc.api.ModInitializer;
                import org.slf4j.Logger;
                import org.slf4j.LoggerFactory;

                public final class {main_class} implements ModInitializer {{
                    public static final String MOD_ID = "{mod.mod_id}";
                    public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);

                    @Override
                    public void onInitialize() {{
                        LOGGER.info("Initializing {mod.name}");
                        GeneratedItems.register();
                        GeneratedBlocks.register();
                        GeneratedEntities.register();
                        GeneratedCommands.register();
                        GeneratedItemGroups.register();
                        GeneratedItemGroups.registerEntries();
                        GeneratedEvents.register();
                        GeneratedInjectedMain.register();
                    }}
                }}
                """
            ),
        )

        if write_client_entrypoint:
            _write_text(
                package_dir / f"{main_class}Client.java",
                dedent(
                    f"""
                    package {package_name};

                    import net.fabricmc.api.ClientModInitializer;

                    public final class {main_class}Client implements ClientModInitializer {{
                        @Override
                        public void onInitializeClient() {{
                            GeneratedInjectedClient.register();
                        }}
                    }}
                    """
                ),
            )

        if write_server_entrypoint:
            _write_text(
                package_dir / f"{main_class}Server.java",
                dedent(
                    f"""
                    package {package_name};

                    import net.fabricmc.api.DedicatedServerModInitializer;

                    public final class {main_class}Server implements DedicatedServerModInitializer {{
                        @Override
                        public void onInitializeServer() {{
                            GeneratedInjectedServer.register();
                        }}
                    }}
                    """
                ),
            )

    def _write_item_groups(
        self,
        *,
        package_dir: Path,
        package_name: str,
        main_class: str,
        mod_id: str,
        tabs: list[FabricTab],
        items: list[FabricItem],
        blocks: list[FabricBlock],
        entities: list[FabricEntity],
        item_consts: dict[str, str],
        block_consts: dict[str, str],
        tab_consts: dict[str, str],
        entity_spawn_egg_consts: dict[str, str],
    ) -> None:
        item_ids = {item.name for item in items}
        block_ids = {block.name for block in blocks}
        entity_ids = {entity.name for entity in entities}

        tab_entries: dict[str, list[str]] = defaultdict(list)
        default_tab = tabs[0].name if len(tabs) == 1 else None

        for item in items:
            tab_id = item.properties.get("creative_tab") or default_tab
            if tab_id and tab_id in tab_consts:
                tab_entries[tab_id].append(f"GeneratedItems.{item_consts[item.name]}")

        for block in blocks:
            tab_id = block.properties.get("creative_tab") or default_tab
            if tab_id and tab_id in tab_consts:
                tab_entries[tab_id].append(f"GeneratedBlocks.{block_consts[block.name]}_ITEM")

        for entity in entities:
            egg_const = entity_spawn_egg_consts.get(entity.name)
            if not egg_const:
                continue
            tab_id = entity.properties.get("creative_tab") or default_tab
            if tab_id and tab_id in tab_consts:
                tab_entries[tab_id].append(f"GeneratedEntities.{egg_const}")

        tab_fields: list[str] = []
        entry_registration_lines: list[str] = []
        for tab in tabs:
            tab_const = tab_consts[tab.name]
            tab_key_const = f"{tab_const}_KEY"
            icon = str(tab.properties.get("icon") or "")
            icon_expr = self._item_group_icon_expression(
                icon=icon,
                mod_id=mod_id,
                item_ids=item_ids,
                block_ids=block_ids,
                entity_ids=entity_ids,
                item_consts=item_consts,
                block_consts=block_consts,
                entity_spawn_egg_consts=entity_spawn_egg_consts,
            )
            tab_fields.append(
                "    public static final RegistryKey<ItemGroup> "
                f"{tab_key_const} = RegistryKey.of(RegistryKeys.ITEM_GROUP, "
                f'Identifier.of({main_class}.MOD_ID, "{tab.name}"));'
            )
            tab_fields.append(
                "    public static final ItemGroup "
                f"{tab_const} = Registry.register("
                "Registries.ITEM_GROUP, "
                f"{tab_key_const}, "
                "FabricItemGroup.builder()"
                f'.displayName(Text.translatable("itemGroup.{mod_id}.{tab.name}"))'
                f".icon(() -> {icon_expr})"
                ".build()"
                ");"
            )

            lines = tab_entries.get(tab.name, [])
            if not lines:
                continue
            entry_block = "\n".join(f"            entries.add({line});" for line in lines)
            entry_registration_lines.append(
                f"        ItemGroupEvents.modifyEntriesEvent({tab_key_const}).register(entries -> {{\n"
                f"{entry_block}\n"
                "        });"
            )

        tab_fields_code = "\n".join(tab_fields) if tab_fields else "    // No generated creative tabs."
        entry_reg_code = (
            "\n".join(entry_registration_lines)
            if entry_registration_lines
            else "        // No tab entries assigned."
        )

        _write_text(
            package_dir / "GeneratedItemGroups.java",
            dedent(
                f"""
                package {package_name};

                import net.fabricmc.fabric.api.itemgroup.v1.FabricItemGroup;
                import net.fabricmc.fabric.api.itemgroup.v1.ItemGroupEvents;
                import net.minecraft.item.ItemGroup;
                import net.minecraft.item.ItemStack;
                import net.minecraft.item.Items;
                import net.minecraft.registry.RegistryKey;
                import net.minecraft.registry.RegistryKeys;
                import net.minecraft.registry.Registries;
                import net.minecraft.registry.Registry;
                import net.minecraft.text.Text;
                import net.minecraft.util.Identifier;

                public final class GeneratedItemGroups {{
                    private GeneratedItemGroups() {{}}

                {tab_fields_code}

                    public static void register() {{
                        {main_class}.LOGGER.info("Registered {len(tabs)} generated creative tab(s)");
                    }}

                    public static void registerEntries() {{
                {entry_reg_code}
                    }}
                }}
                """
            ),
        )

    def _item_group_icon_expression(
        self,
        *,
        icon: str,
        mod_id: str,
        item_ids: set[str],
        block_ids: set[str],
        entity_ids: set[str],
        item_consts: dict[str, str],
        block_consts: dict[str, str],
        entity_spawn_egg_consts: dict[str, str],
    ) -> str:
        if icon:
            normalized = _normalize_id_path(icon, "")
            if normalized in item_ids:
                return f"new ItemStack(GeneratedItems.{item_consts[normalized]})"
            if normalized in block_ids:
                return f"new ItemStack(GeneratedBlocks.{block_consts[normalized]}_ITEM)"
            if normalized in entity_ids and normalized in entity_spawn_egg_consts:
                return f"new ItemStack(GeneratedEntities.{entity_spawn_egg_consts[normalized]})"

            if _is_literal_identifier(icon):
                namespace, path = _split_namespaced_id(icon, mod_id)
                return (
                    "new ItemStack(Registries.ITEM.get("
                    f'Identifier.of("{namespace}", "{path}")'
                    "))"
                )

            icon_as_id = _normalize_id_path(icon, "")
            if icon_as_id in item_ids:
                return f"new ItemStack(GeneratedItems.{item_consts[icon_as_id]})"
            if icon_as_id in block_ids:
                return f"new ItemStack(GeneratedBlocks.{block_consts[icon_as_id]}_ITEM)"
            if icon_as_id in entity_ids and icon_as_id in entity_spawn_egg_consts:
                return f"new ItemStack(GeneratedEntities.{entity_spawn_egg_consts[icon_as_id]})"

        if item_ids:
            first_item = sorted(item_ids)[0]
            return f"new ItemStack(GeneratedItems.{item_consts[first_item]})"
        if block_ids:
            first_block = sorted(block_ids)[0]
            return f"new ItemStack(GeneratedBlocks.{block_consts[first_block]}_ITEM)"
        if entity_spawn_egg_consts:
            first_entity = sorted(entity_spawn_egg_consts.keys())[0]
            return f"new ItemStack(GeneratedEntities.{entity_spawn_egg_consts[first_entity]})"
        return "new ItemStack(Items.STONE)"

    def _write_items(
        self,
        package_dir: Path,
        package_name: str,
        main_class: str,
        items: list[FabricItem],
        item_consts: dict[str, str],
    ) -> None:
        item_lines: list[str] = []
        for item in items:
            const = item_consts[item.name]
            key_const = f"{const}_KEY"
            settings = ["new Item.Settings()"]
            settings.append(f".registryKey({key_const})")
            if item.properties.get("durability") is not None:
                settings.append(f".maxDamage({int(item.properties['durability'])})")
            else:
                settings.append(f".maxCount({int(item.properties.get('max_count', 64))})")

            if item.properties.get("fireproof"):
                settings.append(".fireproof()")

            rarity = str(item.properties.get("rarity", "COMMON")).lower()
            settings.append(f".rarity(Rarity.{_RARITIES.get(rarity, 'COMMON')})")

            item_lines.append(
                "    public static final RegistryKey<Item> "
                f"{key_const} = RegistryKey.of(RegistryKeys.ITEM, "
                f'Identifier.of({main_class}.MOD_ID, "{item.name}"));'
            )
            item_lines.append(
                "    public static final Item "
                f"{const} = Registry.register("
                "Registries.ITEM, "
                f"{key_const}, "
                f"new Item({''.join(settings)})"
                ");"
            )

        item_fields = "\n".join(item_lines) if item_lines else "    // No generated items."

        _write_text(
            package_dir / "GeneratedItems.java",
            dedent(
                f"""
                package {package_name};

                import net.minecraft.item.Item;
                import net.minecraft.util.Rarity;
                import net.minecraft.registry.RegistryKey;
                import net.minecraft.registry.RegistryKeys;
                import net.minecraft.registry.Registries;
                import net.minecraft.registry.Registry;
                import net.minecraft.util.Identifier;

                public final class GeneratedItems {{
                    private GeneratedItems() {{}}

                {item_fields}

                    public static void register() {{
                        {main_class}.LOGGER.info("Registered {len(items)} generated item(s)");
                    }}
                }}
                """
            ),
        )

    def _write_blocks(
        self,
        package_dir: Path,
        package_name: str,
        main_class: str,
        blocks: list[FabricBlock],
        block_consts: dict[str, str],
    ) -> None:
        lines: list[str] = []
        for block in blocks:
            const = block_consts[block.name]
            block_key_const = f"{const}_KEY"
            block_item_key_const = f"{const}_ITEM_KEY"
            settings = (
                "AbstractBlock.Settings.create()"
                f".registryKey({block_key_const})"
                f".strength({float(block.properties.get('hardness', 1.5)):.2f}f, "
                f"{float(block.properties.get('resistance', 1.5)):.2f}f)"
            )
            if int(block.properties.get("luminance", 0)) > 0:
                settings += f".luminance(state -> {int(block.properties['luminance'])})"
            if block.properties.get("requires_tool"):
                settings += ".requiresTool()"

            lines.append(
                "    public static final RegistryKey<Block> "
                f"{block_key_const} = RegistryKey.of(RegistryKeys.BLOCK, "
                f'Identifier.of({main_class}.MOD_ID, "{block.name}"));'
            )
            lines.append(
                "    public static final Block "
                f"{const} = Registry.register("
                "Registries.BLOCK, "
                f"{block_key_const}, "
                f"new Block({settings})"
                ");"
            )
            lines.append(
                "    public static final RegistryKey<Item> "
                f"{block_item_key_const} = RegistryKey.of(RegistryKeys.ITEM, "
                f'Identifier.of({main_class}.MOD_ID, "{block.name}"));'
            )
            lines.append(
                "    public static final Item "
                f"{const}_ITEM = Registry.register("
                "Registries.ITEM, "
                f"{block_item_key_const}, "
                f"new BlockItem({const}, new Item.Settings().registryKey({block_item_key_const}))"
                ");"
            )

        block_fields = "\n".join(lines) if lines else "    // No generated blocks."

        _write_text(
            package_dir / "GeneratedBlocks.java",
            dedent(
                f"""
                package {package_name};

                import net.minecraft.block.AbstractBlock;
                import net.minecraft.block.Block;
                import net.minecraft.item.BlockItem;
                import net.minecraft.item.Item;
                import net.minecraft.registry.RegistryKey;
                import net.minecraft.registry.RegistryKeys;
                import net.minecraft.registry.Registries;
                import net.minecraft.registry.Registry;
                import net.minecraft.util.Identifier;

                public final class GeneratedBlocks {{
                    private GeneratedBlocks() {{}}

                {block_fields}

                    public static void register() {{
                        {main_class}.LOGGER.info("Registered {len(blocks)} generated block(s)");
                    }}
                }}
                """
            ),
        )

    def _write_entities(
        self,
        *,
        package_dir: Path,
        package_name: str,
        main_class: str,
        entities: list[FabricEntity],
        entity_consts: dict[str, str],
        entity_classes: dict[str, str],
    ) -> dict[str, str]:
        lines: list[str] = []
        register_lines: list[str] = []
        spawn_egg_consts: dict[str, str] = {}

        for entity in entities:
            const = entity_consts[entity.name]
            class_name = entity_classes[entity.name]
            key_const = f"{const}_KEY"
            spawn_group = str(entity.properties.get("spawn_group", "CREATURE"))
            width = float(entity.properties.get("width", 0.6))
            height = float(entity.properties.get("height", 1.95))
            tracking_range = int(entity.properties.get("tracking_range", 8))
            update_rate = int(entity.properties.get("tracked_update_rate", 3))
            force_velocity = bool(entity.properties.get("force_tracked_velocity_updates", False))

            builder = (
                "FabricEntityTypeBuilder.create("
                f"SpawnGroup.{spawn_group}, {class_name}::new)"
                f".dimensions(EntityDimensions.fixed({width:.2f}f, {height:.2f}f))"
                f".trackRangeBlocks({tracking_range})"
                f".trackedUpdateRate({update_rate})"
            )
            if force_velocity:
                builder += ".forceTrackedVelocityUpdates(true)"
            builder += f".build({key_const})"

            lines.append(
                "    public static final RegistryKey<EntityType<?>> "
                f"{key_const} = RegistryKey.of(RegistryKeys.ENTITY_TYPE, "
                f'Identifier.of({main_class}.MOD_ID, "{entity.name}"));'
            )
            lines.append(
                "    public static final EntityType<"
                f"{class_name}> {const} = Registry.register("
                "Registries.ENTITY_TYPE, "
                f"{key_const}, "
                f"{builder}"
                ");"
            )

            primary = entity.properties.get("spawn_egg_primary")
            secondary = entity.properties.get("spawn_egg_secondary")
            if primary is not None and secondary is not None:
                egg_const = f"{const}_SPAWN_EGG"
                egg_key_const = f"{egg_const}_KEY"
                spawn_egg_consts[entity.name] = egg_const
                lines.append(
                    "    public static final RegistryKey<Item> "
                    f"{egg_key_const} = RegistryKey.of(RegistryKeys.ITEM, "
                    f'Identifier.of({main_class}.MOD_ID, "{entity.name}_spawn_egg"));'
                )
                lines.append(
                    "    public static final Item "
                    f"{egg_const} = Registry.register("
                    "Registries.ITEM, "
                    f"{egg_key_const}, "
                    f"new SpawnEggItem(new Item.Settings().registryKey({egg_key_const}).spawnEgg({const}))"
                    ");"
                )

            register_lines.append(
                f"        FabricDefaultAttributeRegistry.register({const}, {class_name}.createAttributes());"
            )

            _write_text(
                package_dir / f"{class_name}.java",
                dedent(
                    f"""
                    package {package_name};

                    import net.minecraft.entity.EntityType;
                    import net.minecraft.entity.attribute.DefaultAttributeContainer;
                    import net.minecraft.entity.attribute.EntityAttributes;
                    import net.minecraft.entity.mob.MobEntity;
                    import net.minecraft.entity.mob.PathAwareEntity;
                    import net.minecraft.world.World;

                    public final class {class_name} extends PathAwareEntity {{
                        public {class_name}(EntityType<? extends PathAwareEntity> entityType, World world) {{
                            super(entityType, world);
                        }}

                        public static DefaultAttributeContainer.Builder createAttributes() {{
                            return MobEntity.createMobAttributes()
                                .add(EntityAttributes.MAX_HEALTH, {float(entity.properties.get('max_health', 20.0)):.2f}D)
                                .add(EntityAttributes.MOVEMENT_SPEED, {float(entity.properties.get('movement_speed', 0.25)):.4f}D)
                                .add(EntityAttributes.ATTACK_DAMAGE, {float(entity.properties.get('attack_damage', 2.0)):.2f}D);
                        }}
                    }}
                    """
                ),
            )

        lines_code = "\n".join(lines) if lines else "    // No generated entities."
        register_code = (
            "\n".join(register_lines)
            if register_lines
            else "        // No entity attributes to register."
        )

        _write_text(
            package_dir / "GeneratedEntities.java",
            dedent(
                f"""
                package {package_name};

                import net.fabricmc.fabric.api.object.builder.v1.entity.FabricDefaultAttributeRegistry;
                import net.fabricmc.fabric.api.object.builder.v1.entity.FabricEntityTypeBuilder;
                import net.minecraft.entity.EntityDimensions;
                import net.minecraft.entity.EntityType;
                import net.minecraft.entity.SpawnGroup;
                import net.minecraft.item.Item;
                import net.minecraft.item.SpawnEggItem;
                import net.minecraft.registry.RegistryKey;
                import net.minecraft.registry.RegistryKeys;
                import net.minecraft.registry.Registries;
                import net.minecraft.registry.Registry;
                import net.minecraft.util.Identifier;

                public final class GeneratedEntities {{
                    private GeneratedEntities() {{}}

                {lines_code}

                    public static void register() {{
                {register_code}
                        {main_class}.LOGGER.info("Registered {len(entities)} generated entity type(s)");
                    }}
                }}
                """
            ),
        )

        return spawn_egg_consts

    def _write_commands(
        self,
        package_dir: Path,
        package_name: str,
        main_class: str,
        commands: list[FabricCommand],
    ) -> None:
        lines: list[str] = []

        for command in commands:
            literal = str(command.properties.get("literal", command.name))
            permission = int(command.properties.get("permission_level", 2))
            response = command.properties.get("response")
            if permission <= 0:
                permission_check = "ALWAYS_PASS_CHECK"
            elif permission == 1:
                permission_check = "GAMEMASTERS_CHECK"
            elif permission == 2:
                permission_check = "MODERATORS_CHECK"
            elif permission == 3:
                permission_check = "GAMEMASTERS_CHECK"
            elif permission == 4:
                permission_check = "ADMINS_CHECK"
            else:
                permission_check = "OWNERS_CHECK"

            execute_commands: list[str] = []
            for handler in command.events.get("Execute", []):
                execute_commands.extend(_commands_from_actions(handler))

            body_lines: list[str] = []
            if execute_commands:
                body_lines.append(
                    f"                    executeCommands(source, {', '.join(_java_string(c) for c in execute_commands)});"
                )
            if isinstance(response, str) and response.strip():
                body_lines.append(
                    f"                    source.sendFeedback(() -> Text.literal({_java_string(response)}), false);"
                )
            body_lines.append("                    return 1;")
            body = "\n".join(body_lines)

            lines.append(
                "        CommandRegistrationCallback.EVENT.register((dispatcher, registryAccess, environment) ->\n"
                f'            dispatcher.register(CommandManager.literal("{literal}")\n'
                "                .requires(CommandManager.requirePermissionLevel("
                f"CommandManager.{permission_check}))\n"
                "                .executes(context -> {\n"
                "                    ServerCommandSource source = context.getSource();\n"
                f"{body}\n"
                "                })\n"
                "            )\n"
                "        );"
            )

        lines_code = "\n".join(lines) if lines else "        // No generated commands."

        _write_text(
            package_dir / "GeneratedCommands.java",
            dedent(
                f"""
                package {package_name};

                import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
                import net.minecraft.server.command.CommandManager;
                import net.minecraft.server.command.ServerCommandSource;
                import net.minecraft.text.Text;

                public final class GeneratedCommands {{
                    private GeneratedCommands() {{}}

                    private static void executeCommands(ServerCommandSource source, String... commands) {{
                        if (source == null || source.getServer() == null || commands == null) {{
                            return;
                        }}
                        for (String command : commands) {{
                            if (command == null || command.isBlank()) {{
                                continue;
                            }}
                            source.getServer().getCommandManager().parseAndExecute(source, command);
                        }}
                    }}

                    public static void register() {{
                {lines_code}
                        {main_class}.LOGGER.info("Registered {len(commands)} generated command(s)");
                    }}
                }}
                """
            ),
        )

    def _write_events(
        self,
        *,
        package_dir: Path,
        package_name: str,
        main_class: str,
        items: list[FabricItem],
        blocks: list[FabricBlock],
        entities: list[FabricEntity],
        item_consts: dict[str, str],
        block_consts: dict[str, str],
        entity_consts: dict[str, str],
        startup_commands: list[str],
    ) -> None:
        event_lines: list[str] = []
        generated_handler_count = 0

        for item in items:
            drop_handlers = item.events.get("Drop", [])
            for handler in drop_handlers:
                commands = _commands_from_actions(handler)
                if not commands:
                    continue
                command_args = ", ".join(_java_string(command) for command in commands)
                generated_handler_count += 1
                event_lines.append(
                    "        ServerEntityEvents.ENTITY_LOAD.register((entity, world) -> {\n"
                    "            if (!(entity instanceof ItemEntity itemEntity)) {\n"
                    "                return;\n"
                    "            }\n"
                    f"            if (itemEntity.getStack().isOf(GeneratedItems.{item_consts[item.name]})) {{\n"
                    f"                executeCommands(world.getServer(), {command_args});\n"
                    "            }\n"
                    "        });"
                )

            use_handlers = item.events.get("Use", [])
            for handler in use_handlers:
                commands = _commands_from_actions(handler)
                if not commands:
                    continue
                command_args = ", ".join(_java_string(command) for command in commands)
                generated_handler_count += 1
                event_lines.append(
                    "        UseItemCallback.EVENT.register((player, world, hand) -> {\n"
                    "            ItemStack stack = player.getStackInHand(hand);\n"
                    f"            if (stack.isOf(GeneratedItems.{item_consts[item.name]})) {{\n"
                    f"                executeCommands(world.getServer(), {command_args});\n"
                    "            }\n"
                    "            return ActionResult.PASS;\n"
                    "        });"
                )

        for block in blocks:
            break_handlers = block.events.get("Break", [])
            for handler in break_handlers:
                commands = _commands_from_actions(handler)
                if not commands:
                    continue
                command_args = ", ".join(_java_string(command) for command in commands)
                generated_handler_count += 1
                event_lines.append(
                    "        PlayerBlockBreakEvents.AFTER.register((world, player, pos, state, blockEntity) -> {\n"
                    f"            if (state.isOf(GeneratedBlocks.{block_consts[block.name]})) {{\n"
                    f"                executeCommands(world.getServer(), {command_args});\n"
                    "            }\n"
                    "        });"
                )

            place_handlers = block.events.get("Place", [])
            for handler in place_handlers:
                commands = _commands_from_actions(handler)
                if not commands:
                    continue
                command_args = ", ".join(_java_string(command) for command in commands)
                generated_handler_count += 1
                event_lines.append(
                    "        UseBlockCallback.EVENT.register((player, world, hand, hitResult) -> {\n"
                    "            ItemStack stack = player.getStackInHand(hand);\n"
                    f"            if (stack.isOf(GeneratedBlocks.{block_consts[block.name]}_ITEM)) {{\n"
                    f"                executeCommands(world.getServer(), {command_args});\n"
                    "            }\n"
                    "            return ActionResult.PASS;\n"
                    "        });"
                )

        for entity in entities:
            spawn_handlers = entity.events.get("Spawn", [])
            for handler in spawn_handlers:
                commands = _commands_from_actions(handler)
                if not commands:
                    continue
                command_args = ", ".join(_java_string(command) for command in commands)
                generated_handler_count += 1
                event_lines.append(
                    "        ServerEntityEvents.ENTITY_LOAD.register((entityInstance, world) -> {\n"
                    f"            if (entityInstance.getType().equals(GeneratedEntities.{entity_consts[entity.name]})) {{\n"
                    f"                executeCommands(world.getServer(), {command_args});\n"
                    "            }\n"
                    "        });"
                )

            death_handlers = entity.events.get("Death", [])
            for handler in death_handlers:
                commands = _commands_from_actions(handler)
                if not commands:
                    continue
                command_args = ", ".join(_java_string(command) for command in commands)
                generated_handler_count += 1
                event_lines.append(
                    "        ServerLivingEntityEvents.AFTER_DEATH.register((entityInstance, damageSource) -> {\n"
                    f"            if (entityInstance.getType().equals(GeneratedEntities.{entity_consts[entity.name]})) {{\n"
                    f"                executeCommands(entityInstance.getServer(), {command_args});\n"
                    "            }\n"
                    "        });"
                )

        startup_block = ""
        if startup_commands:
            startup_block = (
                "        ServerLifecycleEvents.SERVER_STARTED.register(server -> {\n"
                f"            executeCommands(server, {', '.join(_java_string(c) for c in startup_commands)});\n"
                "        });\n"
            )

        event_code = "\n".join(event_lines) if event_lines else "        // No generated element events."

        _write_text(
            package_dir / "GeneratedEvents.java",
            dedent(
                f"""
                package {package_name};

                import net.fabricmc.fabric.api.entity.event.v1.ServerLivingEntityEvents;
                import net.fabricmc.fabric.api.event.lifecycle.v1.ServerEntityEvents;
                import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
                import net.fabricmc.fabric.api.event.player.PlayerBlockBreakEvents;
                import net.fabricmc.fabric.api.event.player.UseBlockCallback;
                import net.fabricmc.fabric.api.event.player.UseItemCallback;
                import net.minecraft.entity.ItemEntity;
                import net.minecraft.item.ItemStack;
                import net.minecraft.server.MinecraftServer;
                import net.minecraft.util.ActionResult;

                public final class GeneratedEvents {{
                    private GeneratedEvents() {{}}

                    private static void executeCommands(MinecraftServer server, String... commands) {{
                        if (server == null || commands == null) {{
                            return;
                        }}
                        for (String command : commands) {{
                            if (command == null || command.isBlank()) {{
                                continue;
                            }}
                            server.getCommandManager().parseAndExecute(server.getCommandSource(), command);
                        }}
                    }}

                    public static void register() {{
                {startup_block}{event_code}
                        {main_class}.LOGGER.info("Loaded {generated_handler_count} generated event handler(s)");
                    }}
                }}
                """
            ),
        )

    def _write_injected_java(
        self,
        root: Path,
        default_package: str,
        java_sources: list[FabricJavaSource],
    ) -> dict[str, list[tuple[str, str]]]:
        hooks: dict[str, list[tuple[str, str]]] = {"main": [], "client": [], "server": []}
        if not java_sources:
            return hooks

        for source in java_sources:
            props = source.properties
            source_text = props.get("source")
            source_file = props.get("source_file")

            if source_file:
                source_path = Path(source_file)
                if not source_path.exists() or not source_path.is_file():
                    raise FileNotFoundError(f"Java source file does not exist: {source_file}")
                source_text = source_path.read_text(encoding="utf-8")

            if not isinstance(source_text, str):
                raise ValueError(f"JavaSource '{source.name}' did not resolve to source text.")

            package_name = props.get("package") or _extract_package(source_text) or default_package
            class_name = props.get("class_name") or _extract_class_name(source_text) or "InjectedClass"

            final_source = source_text
            if _extract_package(source_text) is None:
                final_source = f"package {package_name};\n\n{source_text}"

            destination = (
                root / "src" / "main" / "java" / Path(str(package_name).replace(".", "/")) / f"{class_name}.java"
            )
            _write_text(destination, final_source)

            entrypoint = str(props.get("entrypoint", "none"))
            init_method = props.get("initialize")
            if entrypoint in hooks and init_method:
                fqcn = f"{package_name}.{class_name}"
                hooks[entrypoint].append((fqcn, str(init_method)))

        return hooks

    def _write_injected_hook_class(
        self,
        package_dir: Path,
        package_name: str,
        class_name: str,
        hooks: list[tuple[str, str]],
    ) -> None:
        if hooks:
            imports = "\n".join(f"import {fqcn};" for fqcn, _ in hooks)
            calls = "\n".join(f"        {fqcn.split('.')[-1]}.{method}();" for fqcn, method in hooks)
        else:
            imports = ""
            calls = "        // No generated JavaSource hooks."

        _write_text(
            package_dir / f"{class_name}.java",
            dedent(
                f"""
                package {package_name};
                {imports}

                public final class {class_name} {{
                    private {class_name}() {{}}

                    public static void register() {{
                {calls}
                    }}
                }}
                """
            ),
        )

    def _write_assets(
        self,
        assets_dir: Path,
        mod_id: str,
        tabs: list[FabricTab],
        items: list[FabricItem],
        blocks: list[FabricBlock],
        entities: list[FabricEntity],
    ) -> None:
        missing_assets: list[str] = []
        lang_entries: dict[str, str] = {}

        for tab in tabs:
            lang_entries[f"itemGroup.{mod_id}.{tab.name}"] = str(tab.properties.get("display_name", tab.name))

        for item in items:
            lang_entries[f"item.{mod_id}.{item.name}"] = str(item.properties.get("display_name", item.name))

            model_path = assets_dir / "models" / "item" / f"{item.name}.json"
            if not _copy_file_if_exists(item.properties.get("model"), model_path):
                _write_json(
                    model_path,
                    {
                        "parent": "minecraft:item/generated",
                        "textures": {"layer0": f"{mod_id}:item/{item.name}"},
                    },
                )

            texture_path = assets_dir / "textures" / "item" / f"{item.name}.png"
            if not _copy_file_if_exists(item.properties.get("texture"), texture_path):
                missing_assets.append(str(item.properties.get("texture")))
                _write_text(
                    texture_path.with_suffix(".missing.txt"),
                    f"Missing texture source: {item.properties.get('texture')}",
                )

        for block in blocks:
            lang_entries[f"block.{mod_id}.{block.name}"] = str(block.properties.get("display_name", block.name))

            blockstate_path = assets_dir / "blockstates" / f"{block.name}.json"
            _write_json(
                blockstate_path,
                {"variants": {"": {"model": f"{mod_id}:block/{block.name}"}}},
            )

            model_path = assets_dir / "models" / "block" / f"{block.name}.json"
            if not _copy_file_if_exists(block.properties.get("model"), model_path):
                _write_json(
                    model_path,
                    {
                        "parent": "minecraft:block/cube_all",
                        "textures": {"all": f"{mod_id}:block/{block.name}"},
                    },
                )

            _write_json(
                assets_dir / "models" / "item" / f"{block.name}.json",
                {"parent": f"{mod_id}:block/{block.name}"},
            )

            texture_path = assets_dir / "textures" / "block" / f"{block.name}.png"
            if not _copy_file_if_exists(block.properties.get("texture"), texture_path):
                missing_assets.append(str(block.properties.get("texture")))
                _write_text(
                    texture_path.with_suffix(".missing.txt"),
                    f"Missing texture source: {block.properties.get('texture')}",
                )

        for entity in entities:
            lang_entries[f"entity.{mod_id}.{entity.name}"] = str(
                entity.properties.get("display_name", entity.name)
            )
            if entity.properties.get("spawn_egg_primary") is not None:
                lang_entries[f"item.{mod_id}.{entity.name}_spawn_egg"] = (
                    f"{entity.properties.get('display_name', entity.name)} Spawn Egg"
                )
                _write_json(
                    assets_dir / "models" / "item" / f"{entity.name}_spawn_egg.json",
                    {"parent": "minecraft:item/template_spawn_egg"},
                )

        _write_json(assets_dir / "lang" / "en_us.json", lang_entries)

        if missing_assets:
            _write_json(
                assets_dir / "modpy_missing_assets.json",
                {"missing": [asset for asset in missing_assets if asset and asset != "None"]},
            )

    def _write_data_files(
        self,
        data_dir: Path,
        mod_id: str,
        items: list[FabricItem],
        blocks: list[FabricBlock],
        recipes: list[FabricRecipe],
        tags: list[FabricTag],
        biomes: list[FabricBiome],
        worldgens: list[FabricWorldgen],
    ) -> None:
        self._write_recipes(data_dir, mod_id, items, blocks, recipes)
        self._write_tags(data_dir, mod_id, items, blocks, tags)
        self._write_block_loot_tables(data_dir, mod_id, blocks)
        self._write_biomes(data_dir, biomes)
        self._write_worldgen_entries(data_dir, worldgens)

    def _write_recipes(
        self,
        data_dir: Path,
        mod_id: str,
        items: list[FabricItem],
        blocks: list[FabricBlock],
        recipes: list[FabricRecipe],
    ) -> None:
        generated_items = {item.name for item in items}
        generated_blocks = {block.name for block in blocks}

        for recipe in recipes:
            props = recipe.properties
            recipe_type = props["recipe_type"]
            output = _resolve_item_like_id(
                str(props["output"]),
                mod_id=mod_id,
                generated_items=generated_items,
                generated_blocks=generated_blocks,
            )
            namespace, path = _split_namespaced_id(str(props["identifier"]), mod_id)

            if recipe_type == "shaped":
                key_payload: dict[str, dict[str, str]] = {}
                for symbol, item_ref in dict(props["key"]).items():
                    key_payload[str(symbol)] = {
                        "item": _resolve_item_like_id(
                            str(item_ref),
                            mod_id=mod_id,
                            generated_items=generated_items,
                            generated_blocks=generated_blocks,
                        )
                    }
                payload: dict[str, Any] = {
                    "type": "minecraft:crafting_shaped",
                    "pattern": list(props["pattern"]),
                    "key": key_payload,
                    "result": {"item": output, "count": int(props["count"])},
                }
            elif recipe_type == "shapeless":
                payload = {
                    "type": "minecraft:crafting_shapeless",
                    "ingredients": [
                        {
                            "item": _resolve_item_like_id(
                                str(ingredient),
                                mod_id=mod_id,
                                generated_items=generated_items,
                                generated_blocks=generated_blocks,
                            )
                        }
                        for ingredient in list(props["ingredients"])
                    ],
                    "result": {"item": output, "count": int(props["count"])},
                }
            else:
                payload = {
                    "type": f"minecraft:{recipe_type}",
                    "ingredient": {
                        "item": _resolve_item_like_id(
                            str(props["input_item"]),
                            mod_id=mod_id,
                            generated_items=generated_items,
                            generated_blocks=generated_blocks,
                        )
                    },
                    "result": output,
                    "experience": float(props["experience"]),
                    "cookingtime": int(props["cooking_time"]),
                }

            _write_json(data_dir / namespace / "recipes" / f"{path}.json", payload)

    def _write_tags(
        self,
        data_dir: Path,
        mod_id: str,
        items: list[FabricItem],
        blocks: list[FabricBlock],
        tags: list[FabricTag],
    ) -> None:
        generated_items = {item.name for item in items}
        generated_blocks = {block.name for block in blocks}

        for tag in tags:
            props = tag.properties
            values = [
                _resolve_item_like_id(
                    str(value),
                    mod_id=mod_id,
                    generated_items=generated_items,
                    generated_blocks=generated_blocks,
                )
                for value in list(props["values"])
            ]

            registry_folder = "items" if props["registry"] == "item" else "blocks"
            payload = {"replace": bool(props["replace"]), "values": values}
            _write_json(
                data_dir / str(props["namespace"]) / "tags" / registry_folder / f"{props['identifier']}.json",
                payload,
            )

    def _write_block_loot_tables(
        self,
        data_dir: Path,
        mod_id: str,
        blocks: list[FabricBlock],
    ) -> None:
        for block in blocks:
            payload = {
                "type": "minecraft:block",
                "pools": [
                    {
                        "rolls": 1.0,
                        "entries": [{"type": "minecraft:item", "name": f"{mod_id}:{block.name}"}],
                        "conditions": [{"condition": "minecraft:survives_explosion"}],
                    }
                ],
            }
            _write_json(data_dir / mod_id / "loot_tables" / "blocks" / f"{block.name}.json", payload)
            # Keep compatibility with older path shape some users already consumed.
            _write_json(data_dir / mod_id / "loot_table" / "blocks" / f"{block.name}.json", payload)

    def _resolve_json_payload(
        self,
        *,
        payload: dict[str, Any] | None,
        payload_file: str | None,
        label: str,
    ) -> dict[str, Any]:
        if payload_file:
            source_path = Path(payload_file)
            if not source_path.exists() or not source_path.is_file():
                raise FileNotFoundError(f"{label} payload_file does not exist: {payload_file}")
            loaded = json.loads(source_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError(f"{label} payload_file must decode to a JSON object.")
            return loaded
        if payload is None:
            return {}
        return _deep_json_copy(payload)

    def _write_biomes(self, data_dir: Path, biomes: list[FabricBiome]) -> None:
        for biome in biomes:
            props = biome.properties
            payload = self._resolve_json_payload(
                payload=props.get("payload"),
                payload_file=props.get("payload_file"),
                label=f"Biome '{biome.name}'",
            )
            if not payload:
                payload = {
                    "has_precipitation": bool(props["has_precipitation"]),
                    "temperature": float(props["temperature"]),
                    "downfall": float(props["downfall"]),
                    "attributes": {
                        "minecraft:visual/sky_color": _rgb_hex(int(props["sky_color"])),
                        "minecraft:visual/fog_color": _rgb_hex(int(props["fog_color"])),
                        "minecraft:visual/water_fog_color": _rgb_hex(int(props["water_fog_color"])),
                    },
                    "effects": {
                        "water_color": _rgb_hex(int(props["water_color"])),
                    },
                    "carvers": [
                        "minecraft:cave",
                        "minecraft:cave_extra_underground",
                        "minecraft:canyon",
                    ],
                    "features": [],
                    "spawners": {
                        "ambient": [],
                        "axolotls": [],
                        "creature": [],
                        "misc": [],
                        "monster": [],
                        "underground_water_creature": [],
                        "water_ambient": [],
                        "water_creature": [],
                    },
                    "spawn_costs": {},
                }
            _write_json(
                data_dir / str(props["namespace"]) / "worldgen" / "biome" / f"{props['identifier']}.json",
                payload,
            )

    def _write_worldgen_entries(self, data_dir: Path, worldgens: list[FabricWorldgen]) -> None:
        for entry in worldgens:
            props = entry.properties
            payload = self._resolve_json_payload(
                payload=props.get("payload"),
                payload_file=props.get("payload_file"),
                label=f"Worldgen '{entry.name}'",
            )
            if str(props["worldgen_type"]) == "placed_feature":
                feature_id = payload.get("feature")
                if isinstance(feature_id, str):
                    payload["feature"] = _WORLDGEN_FEATURE_ALIASES.get(feature_id, feature_id)
            _write_json(
                data_dir
                / str(props["namespace"])
                / "worldgen"
                / Path(str(props["worldgen_type"]))
                / f"{props['identifier']}.json",
                payload,
            )

    def _write_readme(self, root: Path, mod: Any) -> None:
        _write_text(
            root / "README.md",
            dedent(
                f"""
                # {mod.name}

                Generated by ModPy using `{self.key}`.

                ## Build

                - Primary command:
                  `./gradlew build`
                - If `gradle-wrapper.jar` is missing, the generated wrapper script
                  bootstraps it automatically using a locally installed `gradle`.

                ## Notes

                - Generated manifest:
                  `src/main/resources/data/{mod.mod_id}/modpy/manifest.json`
                - Insert custom Java with `mod.JavaSource(...)` for advanced Fabric APIs.
                - High-level DSL includes `Command`, `Entity`, `Biome`, and `Worldgen`.
                """
            ),
        )
