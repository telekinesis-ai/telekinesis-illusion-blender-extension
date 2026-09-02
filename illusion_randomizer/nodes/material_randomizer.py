"""Material randomizer node - maps to MaterialRandomizer.

BinPickingWorker._add_randomizers() builds exactly one MaterialRandomizer per
supercategory (material_randomizer_parts / _crate / _distractors), each
targeting that role's objects. So this node is scoped by Role rather than by a
free-text target list, and the targets it hits are derived from the Asset
nodes carrying that role.
"""

import bpy

from ._base import IllusionRandomizerNodeBase
from ..live import on_tunable_change
from ..names import parse_names
from .. import assets
from .asset import ROLE_ITEMS


class IllusionMaterialRandomizerNode(IllusionRandomizerNodeBase, bpy.types.Node):
    bl_idname = "IllusionMaterialRandomizerNode"
    bl_label = "Material Randomizer"
    bl_icon = "MATERIAL"
    node_color = (0.20, 0.36, 0.26)

    role: bpy.props.EnumProperty(
        name="Role",
        description=(
            "Which supercategory's objects this randomizer applies to - matches the "
            "Role set on the Asset nodes (YAML 'supercategory')"
        ),
        items=ROLE_ITEMS,
        default="part",
        update=on_tunable_change,
    )
    types: bpy.props.StringProperty(
        name="Material Types",
        description=(
            "Comma-separated material category tags to pick from, e.g. 'metal, plastic' - "
            "matched against the sub-directories of <asset directory>/materials. Leave "
            "empty to skip material randomization for this role"
        ),
        update=on_tunable_change,
    )

    def draw_buttons(self, context, layout):
        layout.prop(self, "role")
        self.draw_role_targets(layout)

        asset_dir = assets.effective_asset_dir(context, self.id_data)
        available = assets.subdir_names(asset_dir, "materials")
        if available:
            self.draw_checkbox_list(
                layout,
                "types",
                available,
                "Material Types",
                orphan_message="Not found in <asset directory>/materials:",
            )
        else:
            # No asset directory configured, or it has no materials/ - fall
            # back to free text rather than showing an empty, unusable box.
            layout.prop(self, "types")
            layout.label(text="Set an Asset Directory to pick from disk", icon="INFO")

        if not parse_names(self.types):
            layout.label(text="No types - this randomizer is skipped", icon="INFO")

    def to_spec_dict(self) -> dict:
        return {"types": parse_names(self.types)}


CLASSES = (IllusionMaterialRandomizerNode,)
