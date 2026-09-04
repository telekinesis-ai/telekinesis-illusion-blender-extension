"""Operator backing the multi-select target pickers.

Blender's dynamic-items EnumProperty (and especially ENUM_FLAG with dynamic
items) is fragile - flag values are positional, so adding/renaming an Asset
node would silently remap existing selections. And syncing a
CollectionProperty of toggles would mean mutating data from a draw callback,
which Blender forbids. A per-name toggle operator avoids both: the stored
value stays a plain comma-separated string, and each click is an explicit,
undoable edit.
"""

import bpy

from .names import join_names, parse_names


class ILLUSION_OT_toggle_target(bpy.types.Operator):
    bl_idname = "illusion.randomizer_toggle_target"
    bl_label = "Toggle Target Object"
    bl_description = "Add or remove this asset from the node's target objects"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    tree_name: bpy.props.StringProperty()
    node_name: bpy.props.StringProperty()
    prop_name: bpy.props.StringProperty()
    value: bpy.props.StringProperty()

    def execute(self, context):
        tree = bpy.data.node_groups.get(self.tree_name)
        if tree is None:
            self.report({"ERROR"}, f"Node tree {self.tree_name!r} not found")
            return {"CANCELLED"}
        node = tree.nodes.get(self.node_name)
        if node is None:
            self.report({"ERROR"}, f"Node {self.node_name!r} not found")
            return {"CANCELLED"}

        names = parse_names(getattr(node, self.prop_name))
        if self.value in names:
            names.remove(self.value)
        else:
            names.append(self.value)
        # Assigning through the RNA property fires its update= callback, so a
        # live-preview re-randomize is triggered just like a manual edit.
        setattr(node, self.prop_name, join_names(names))
        return {"FINISHED"}


CLASSES = (ILLUSION_OT_toggle_target,)
