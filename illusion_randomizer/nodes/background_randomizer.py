"""Background randomizer node - maps to BackgroundRandomizer."""

import bpy

from ._base import IllusionRandomizerNodeBase
from ..live import on_tunable_change
from ..names import parse_names
from .. import assets


class IllusionBackgroundRandomizerNode(IllusionRandomizerNodeBase, bpy.types.Node):
    bl_idname = "IllusionBackgroundRandomizerNode"
    bl_label = "Background Randomizer"
    bl_icon = "WORLD"
    node_color = (0.20, 0.36, 0.26)

    categories: bpy.props.StringProperty(
        name="Categories",
        description=(
            "Comma-separated HDRI categories the scene background is picked from, e.g. "
            "'indoor/industrial, outdoor/day' - matched against the sub-directories of "
            "<asset directory>/hdris"
        ),
        update=on_tunable_change,
    )

    def draw_buttons(self, context, layout):
        # Which categories exist depends on the asset tree in use, so they're
        # scanned rather than hardcoded - picking one the tree doesn't ship
        # would leave BackgroundRandomizer with an empty catalog.
        asset_dir = assets.effective_asset_dir(context, self.id_data)
        available = assets.subdir_names(asset_dir, "hdris", depth=2)
        if available:
            self.draw_checkbox_list(
                layout,
                "categories",
                available,
                "Categories",
                orphan_message="Not found in <asset directory>/hdris:",
            )
        else:
            layout.prop(self, "categories")
            layout.label(text="Set an Asset Directory to pick from disk", icon="INFO")

        if not parse_names(self.categories):
            layout.label(text="No categories - this randomizer is skipped", icon="INFO")

    def to_spec_dict(self) -> dict:
        return {"categories": parse_names(self.categories)}


CLASSES = (IllusionBackgroundRandomizerNode,)
