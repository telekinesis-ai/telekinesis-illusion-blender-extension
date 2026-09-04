"""Illusion Randomizer Tree - a Blender extension for building and tuning
telekinesis.illusion randomizer specs as a node graph.

The tree is a *view* of the worker's randomizer DAG, not a definition of it:
topology is fixed in BinPickingWorker._add_randomizers(), and the spec supplies
only the tunable parameters. See spec_io.py for what that means for
serialization, and preview.py for how the preview runs illusion in-process
inside a live Blender session.
"""

import bpy

from . import log
from . import node_tree
from . import sockets
from . import nodes
from . import preferences
from . import live
from . import targets
from . import layout as node_layout
from . import viz
from . import preview
from . import upload
from . import panel

# Add-menu entries, grouped the way BinPickingWorker thinks about them.
# Blender 4.0 replaced nodeitems_utils.register_node_categories() with plain
# menus appended to NODE_MT_add, which is what this uses - the old API is
# deprecated and its categories no longer show up for custom trees.
NODE_MENUS = (
    ("NODE_MT_illusion_assets", "Assets", ("IllusionAssetNode",)),
    (
        "NODE_MT_illusion_randomizers",
        "Randomizers",
        (
            "IllusionInstanceRandomizerNode",
            "IllusionPoseRandomizerNode",
            "IllusionMaterialRandomizerNode",
            "IllusionBackgroundRandomizerNode",
            "IllusionCameraRandomizerNode",
            "IllusionPhysicsNode",
        ),
    ),
    ("NODE_MT_illusion_output", "Output", ("IllusionWorkerOutputNode",)),
)


def _add_node_type(layout, bl_idname):
    """Draw one 'add this node' entry.

    Prefers bl_ui.node_add_menu.add_node_type so the entry behaves exactly
    like a built-in one (label from bl_label, drag-to-place via
    use_transform); falls back to the raw operator if that helper moves."""
    try:
        from bl_ui import node_add_menu

        node_add_menu.add_node_type(layout, bl_idname)
    except (ImportError, AttributeError):
        op = layout.operator("node.add_node", text=bl_idname)
        op.type = bl_idname
        op.use_transform = True


def _make_menu(bl_idname, label, node_idnames):
    def draw(self, context):
        for node_idname in node_idnames:
            _add_node_type(self.layout, node_idname)

    return type(
        bl_idname,
        (bpy.types.Menu,),
        {
            "bl_idname": bl_idname,
            "bl_label": label,
            "draw": draw,
        },
    )


MENU_CLASSES = tuple(_make_menu(*entry) for entry in NODE_MENUS)


def _draw_add_menu(self, context):
    """Appended to NODE_MT_add, which is shared by every node editor - so
    only draw when the open tree is actually ours."""
    space = context.space_data
    if space is None or space.tree_type != node_tree.IllusionRandomizerTree.bl_idname:
        return
    layout = self.layout
    layout.separator()
    for menu_cls in MENU_CLASSES:
        layout.menu(menu_cls.bl_idname)


CLASSES = (
    node_tree.CLASSES
    + sockets.CLASSES
    + nodes.CLASSES
    + preferences.CLASSES
    + targets.CLASSES
    + node_layout.CLASSES
    + viz.CLASSES
    + preview.CLASSES
    + upload.CLASSES
    + panel.CLASSES
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    for cls in MENU_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.NODE_MT_add.append(_draw_add_menu)


def unregister():
    # Leave no live-preview timer pointing at soon-to-be-unregistered code.
    for timer_fn in (live._flush, viz._watch):
        if bpy.app.timers.is_registered(timer_fn):
            bpy.app.timers.unregister(timer_fn)
    # Our loguru sink outlives the add-on otherwise, since loguru's handler
    # registry is global to the Python session.
    log.configure("OFF")
    bpy.types.NODE_MT_add.remove(_draw_add_menu)
    for cls in reversed(MENU_CLASSES):
        bpy.utils.unregister_class(cls)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
