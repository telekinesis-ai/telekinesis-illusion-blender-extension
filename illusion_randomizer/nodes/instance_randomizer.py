"""Instance-count randomizer node - maps to ObjectInstanceRandomizer.

BinPickingWorker._add_randomizers() builds exactly one ObjectInstanceRandomizer
per supercategory (instance_randomizer_objects / _containers / _distractors),
each targeting that role's objects. So this node is scoped by Role rather than
by a free-text target list, and the targets it hits are derived from the Asset
nodes carrying that role.
"""

import bpy

from ._base import IllusionRandomizerNodeBase
from ..live import on_tunable_change
from .asset import ROLE_ITEMS


class IllusionInstanceRandomizerNode(IllusionRandomizerNodeBase, bpy.types.Node):
    bl_idname = "IllusionInstanceRandomizerNode"
    bl_label = "Instance Count Randomizer"
    bl_icon = "DUPLICATE"
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
    min_num_total_objects: bpy.props.IntProperty(
        name="Min Total",
        description="Fewest instances (summed across all objects of this role) visible in a given scene",
        default=1,
        min=0,
        update=on_tunable_change,
    )
    max_num_total_objects: bpy.props.IntProperty(
        name="Max Total",
        description="Most instances (summed across all objects of this role) visible in a given scene",
        default=1,
        min=0,
        update=on_tunable_change,
    )

    def draw_buttons(self, context, layout):
        layout.prop(self, "role")
        self.draw_role_targets(layout)
        row = layout.row(align=True)
        row.prop(self, "min_num_total_objects")
        row.prop(self, "max_num_total_objects")
        # ObjectInstanceRandomizer raises on min > max; catching it here points
        # at the node instead of failing deep inside a preview run.
        if self.min_num_total_objects > self.max_num_total_objects:
            layout.label(text="Min Total exceeds Max Total", icon="ERROR")

    def to_spec_dict(self) -> dict:
        return {
            "min": self.min_num_total_objects,
            "max": self.max_num_total_objects,
        }


CLASSES = (IllusionInstanceRandomizerNode,)
