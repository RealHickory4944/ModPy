import modpy as mp

mod = mp.Mod(
    author="Theobobble",
    generator="minecraft-fabric-1.21.11",
    mod_id="examplemod",
    name="Example Mod",
)

tab = mod.Tab(
    identifier="tab",
    name="Tab",
    icon="ruby",
)

item = mod.Item(
    identifier="ruby",
    name="Ruby",
    texture="path/to/texture.png",
    model="path/to/model.json",
    creative_tab="tab",
    rarity="rare",
)

@item.Event.Drop
def on_drop():
    mod.sendConsole("say Item Dropped!")

block = mod.Block(
    identifier="ruby_block",
    name="Ruby Block",
    texture="path/to/ruby_block.png",
    creative_tab="tab",
    hardness=5.0,
    resistance=6.0,
    requires_tool=True,
)

@block.Event.Break
def on_break():
    mod.sendConsole("say Ruby block broken!")

recipe = mod.Recipe(
    recipe_type="shaped",
    identifier="ruby_block_from_ruby",
    output="ruby_block",
    pattern=[
        "RRR",
        "RRR",
        "RRR",
    ],
    key={"R": "ruby"},
)

tag = mod.Tag(
    registry="item",
    identifier="c:gems/ruby",
    values=["ruby"],
)

command = mod.Command(
    literal="ruby",
    response="Ruby command executed",
    permission_level=2,
)

@command.Event.Execute
def on_command():
    mod.sendConsole("say Ruby command triggered!")

entity = mod.Entity(
    identifier="ruby_guardian",
    name="Ruby Guardian",
    spawn_group="monster",
    max_health=40.0,
    movement_speed=0.3,
    attack_damage=7.0,
    spawn_egg_primary="#b90f3f",
    spawn_egg_secondary="#2c040f",
    creative_tab="tab",
)

@entity.Event.Spawn
def on_entity_spawn():
    mod.sendConsole("say Ruby Guardian spawned!")

biome = mod.Biome(
    identifier="ruby_wastes",
    name="Ruby Wastes",
    temperature=2.0,
    downfall=0.0,
    has_precipitation=False,
    sky_color=0xB90F3F,
    fog_color=0x6E0825,
    water_color=0x5E1127,
    water_fog_color=0x39060F,
)

worldgen = mod.Worldgen(
    worldgen_type="placed_feature",
    identifier="ruby_ore_patch",
    payload={
        "feature": "minecraft:ore_diamond_small",
        "placement": [],
    },
)

extra_java = mod.JavaSource(
    class_name="ExtraModHooks",
    entrypoint="main",
    initialize="init",
    source="""
public final class ExtraModHooks {
    private ExtraModHooks() {}

    public static void init() {
        ExamplemodMod.LOGGER.info("Extra Java hook initialized");
    }
}
""",
)

mod.sendConsole("say Example mod startup loaded")

mod.add(tab)
mod.add(item)
mod.add(block)
mod.add(recipe)
mod.add(tag)
mod.add(command)
mod.add(entity)
mod.add(biome)
mod.add(worldgen)
mod.add(extra_java)

mod.compile()
