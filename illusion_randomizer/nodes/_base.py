"""Shared base mixin for every node kind in the Illusion Randomizer tree."""

from ..names import asset_names, asset_names_for_role, parse_names
from ..node_tree import IllusionRandomizerTree


class IllusionRandomizerNodeBase:
    # Blender truncates a field's label before its value, so these nodes need
    # to be a lot wider than the stock default to stay readable. Still
    # drag-resizable per node between min/max.
    bl_width_default = 400
    bl_width_min = 240
    bl_width_max = 900

    # Header tint, set per subclass so kinds are distinguishable at a glance
    # when zoomed out. Applied in init() rather than draw() (draw callbacks
    # must not mutate data).
    node_color = (0.35, 0.35, 0.35)

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == IllusionRandomizerTree.bl_idname

    def init(self, context):
        self.inputs.new("IllusionFlowSocket", "In")
        self.outputs.new("IllusionFlowSocket", "Out")
        self.use_custom_color = True
        self.color = self.node_color

    def draw_target_selector(
        self, layout, prop_name="target_objects", label="Target Objects"
    ):
        """Draws the node's target-object list as toggles over the Asset nodes
        present in this tree, instead of a free-text field. See targets.py for
        why this is an operator per name rather than a multi-select enum."""
        self.draw_checkbox_list(
            layout,
            prop_name,
            asset_names(self.id_data),
            label,
            empty_message="Add & name an Asset node first",
            orphan_message="Not matching any Asset:",
        )

    def draw_role_targets(self, layout, label="Target Objects"):
        """Draws the target objects this node applies to, derived read-only
        from the Asset nodes carrying self.role.

        The role-scoped randomizers (Instance/Material) exist once per
        supercategory because that's how BinPickingWorker._add_randomizers()
        builds them - their targets follow from the Asset roles rather than
        being picked per node, so this is a display, not an editor."""
        names = asset_names_for_role(self.id_data, self.role)
        box = layout.box()
        box.label(text=label)
        if not names:
            box.label(text=f"No Asset node with role '{self.role}'", icon="ERROR")
            return
        col = box.column(align=True)
        for name in names:
            col.label(text=name, icon="MESH_DATA")

    def draw_checkbox_list(
        self,
        layout,
        prop_name,
        available,
        label,
        empty_message=None,
        orphan_message="Not recognised:",
    ):
        """Draws a comma-separated string property as a checkbox per entry of
        `available`. See targets.py for why the value stays a plain string
        toggled by an operator rather than a dynamic ENUM_FLAG."""
        selected = set(parse_names(getattr(self, prop_name)))

        box = layout.box()
        box.label(text=label)
        if not available and empty_message:
            box.label(text=empty_message, icon="ERROR")
        col = box.column(align=True)
        for name in available:
            is_on = name in selected
            op = col.operator(
                "illusion.randomizer_toggle_target",
                text=name,
                depress=is_on,
                icon="CHECKBOX_HLT" if is_on else "CHECKBOX_DEHLT",
            )
            op.tree_name = self.id_data.name
            op.node_name = self.name
            op.prop_name = prop_name
            op.value = name

        # Stored values with no entry in `available` (e.g. an Asset node was
        # renamed or deleted, or a material folder went away) would otherwise
        # be invisible here while still being exported, so surface them.
        orphans = sorted(selected.difference(available))
        if orphans:
            warn = box.column(align=True)
            warn.label(text=orphan_message, icon="ERROR")
            for name in orphans:
                row = warn.row()
                row.label(text=name)
                op = row.operator(
                    "illusion.randomizer_toggle_target",
                    text="",
                    icon="X",
                )
                op.tree_name = self.id_data.name
                op.node_name = self.name
                op.prop_name = prop_name
                op.value = name

    def to_spec_dict(self) -> dict:
        """Return this node's fields as a plain dict, matching the shape
        spec_io.py needs to slot into the YAML spec / RandomizerNode
        constructor kwargs for this node kind."""
        raise NotImplementedError
