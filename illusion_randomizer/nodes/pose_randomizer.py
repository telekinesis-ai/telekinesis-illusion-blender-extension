"""Pose randomizer node - maps to ObjectPoseRandomizer.

pose_sampling_function is a Python callable in the illusion API, not a plain
data structure, so this node only supports the two concrete strategies
BinPickingWorker actually builds closures for (random box sampling, grid
placement) rather than arbitrary pose-sampling code - spec_io.py constructs
the matching closure from these fields, mirroring
workers/bin_picking_worker.py's _add_randomizers().

Which objects get posed is not picked here: the worker builds this randomizer
from the Asset nodes with role 'part', and a second one from the distractors,
so the node shows those targets read-only."""

import bpy

from ._base import IllusionRandomizerNodeBase
from ..live import on_tunable_change
from ..names import asset_instance_capacity, asset_names_for_role

STRATEGY_ITEMS = (
    ("random", "Random", "Uniform box sampling, optionally constrained to a surface"),
    ("grid", "Grid", "Grid placement on the container's top face"),
)


class IllusionPoseRandomizerNode(IllusionRandomizerNodeBase, bpy.types.Node):
    bl_idname = "IllusionPoseRandomizerNode"
    bl_label = "Pose Randomizer"
    bl_icon = "ORIENTATION_GIMBAL"
    node_color = (0.20, 0.36, 0.26)

    strategy: bpy.props.EnumProperty(
        name="Strategy",
        description="How to place target objects each scene",
        items=STRATEGY_ITEMS,
        default="random",
        update=on_tunable_change,
    )
    sample_on_surface: bpy.props.StringProperty(
        name="Sample On Surface",
        description=(
            "Object Name of a container to drop parts onto (random strategy only). Leave "
            "blank to auto-detect the visible container instead"
        ),
        update=on_tunable_change,
    )

    # random strategy params
    min_height: bpy.props.FloatProperty(
        name="Min Height",
        description="Minimum drop height above the surface before physics settling (random strategy)",
        default=0.0,
        update=on_tunable_change,
    )
    max_height: bpy.props.FloatProperty(
        name="Max Height",
        description="Maximum drop height above the surface before physics settling (random strategy)",
        default=0.0,
        update=on_tunable_change,
    )
    face_sample_range_min: bpy.props.FloatProperty(
        name="Face Sample Range Min",
        description="Lower bound (0-1) of the container's top face used for sampling XY drop position",
        default=0.25,
        min=0.0,
        max=1.0,
        update=on_tunable_change,
    )
    face_sample_range_max: bpy.props.FloatProperty(
        name="Face Sample Range Max",
        description="Upper bound (0-1) of the container's top face used for sampling XY drop position",
        default=0.75,
        min=0.0,
        max=1.0,
        update=on_tunable_change,
    )

    # grid strategy params
    grid_rows: bpy.props.IntProperty(
        name="Rows",
        description="Number of grid rows on the container's top face",
        default=5,
        min=1,
        update=on_tunable_change,
    )
    grid_cols: bpy.props.IntProperty(
        name="Cols",
        description="Number of grid columns on the container's top face",
        default=5,
        min=1,
        update=on_tunable_change,
    )
    grid_layers: bpy.props.IntProperty(
        name="Layers",
        description="Number of stacked grid layers (vertically offset by Layer Spacing)",
        default=1,
        min=1,
        update=on_tunable_change,
    )
    grid_layer_spacing: bpy.props.FloatProperty(
        name="Layer Spacing",
        description="Vertical gap between stacked grid layers",
        default=0.03,
        update=on_tunable_change,
    )
    grid_shuffle: bpy.props.BoolProperty(
        name="Shuffle",
        description="Randomize which grid cell each instance is assigned to",
        default=True,
        update=on_tunable_change,
    )
    grid_xy_jitter: bpy.props.FloatProperty(
        name="XY Jitter",
        description="Random XY offset added to each grid cell's center position",
        default=0.0,
        min=0.0,
        update=on_tunable_change,
    )
    grid_z_rotation_range_min: bpy.props.FloatProperty(
        name="Z Rotation Min (deg)",
        description="Minimum random rotation around Z applied per instance",
        default=0.0,
        update=on_tunable_change,
    )
    grid_z_rotation_range_max: bpy.props.FloatProperty(
        name="Z Rotation Max (deg)",
        description="Maximum random rotation around Z applied per instance",
        default=0.0,
        update=on_tunable_change,
    )

    def _visible_part_ceiling(self) -> int:
        """Most parts that can be visible in one scene.

        The part Instance Count Randomizer's Max Total, capped by the copies the
        Asset nodes provide - the same clamp ObjectInstanceRandomizer applies at
        randomize time."""
        capacity = asset_instance_capacity(self.id_data, "part")
        for node in self.id_data.nodes:
            if (
                node.bl_idname == "IllusionInstanceRandomizerNode"
                and node.role == "part"
            ):
                return min(node.max_num_total_objects, capacity)
        return capacity

    def draw_buttons(self, context, layout):
        self.draw_role_targets(layout, role="part")
        # BinPickingWorker gives the distractors their own pose randomizer,
        # always with the random sampler - so they follow these settings under
        # the random strategy but are never placed on the grid.
        distractors = asset_names_for_role(self.id_data, "distractor")
        if distractors:
            box = layout.box()
            if self.strategy == "grid":
                box.label(text="Distractors (placed randomly, not on the grid)")
            else:
                box.label(text="Distractors (placed with these settings)")
            col = box.column(align=True)
            for name in distractors:
                col.label(text=name, icon="MESH_DATA")
        layout.prop(self, "strategy")
        if self.strategy == "random":
            layout.prop(self, "sample_on_surface")
            row = layout.row(align=True)
            row.prop(self, "min_height")
            row.prop(self, "max_height")
            row = layout.row(align=True)
            row.prop(self, "face_sample_range_min")
            row.prop(self, "face_sample_range_max")
        else:
            row = layout.row(align=True)
            row.prop(self, "grid_rows")
            row.prop(self, "grid_cols")
            row.prop(self, "grid_layers")
            # The sampler hands out cell centres in order and starts over once
            # it runs out, so parts beyond the last cell land on top of earlier
            # ones - nothing downstream errors, hence the warning here.
            cells = self.grid_rows * self.grid_cols * self.grid_layers
            parts = self._visible_part_ceiling()
            if parts > cells:
                layout.label(
                    text=f"{cells} cells for up to {parts} parts - cells get reused",
                    icon="ERROR",
                )
            else:
                layout.label(text=f"{cells} cells")
            layout.prop(self, "grid_layer_spacing")
            layout.prop(self, "grid_shuffle")
            layout.prop(self, "grid_xy_jitter")
            row = layout.row(align=True)
            row.prop(self, "grid_z_rotation_range_min")
            row.prop(self, "grid_z_rotation_range_max")

    def to_spec_dict(self) -> dict:
        spec = {
            "strategy": self.strategy,
        }
        if self.strategy == "random":
            spec["sample_on_surface"] = self.sample_on_surface or None
            spec["params"] = {
                "min_height": self.min_height,
                "max_height": self.max_height,
                "face_sample_range": [
                    self.face_sample_range_min,
                    self.face_sample_range_max,
                ],
            }
        else:
            spec["grid"] = {
                "rows": self.grid_rows,
                "cols": self.grid_cols,
                "layers": self.grid_layers,
                "layer_spacing": self.grid_layer_spacing,
                "shuffle": self.grid_shuffle,
                "xy_jitter": self.grid_xy_jitter,
                "z_rotation_range": [
                    self.grid_z_rotation_range_min,
                    self.grid_z_rotation_range_max,
                ],
            }
        return spec


CLASSES = (IllusionPoseRandomizerNode,)
