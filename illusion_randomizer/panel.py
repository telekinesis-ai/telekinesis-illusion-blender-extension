"""Sidebar panel for the Illusion Randomizer node editor - worker type selector
plus the Load Assets / Preview Scene / Change Scene / Upload buttons."""

import bpy

from . import assets, refs, stages
from .node_tree import IllusionRandomizerTree


class ILLUSION_PT_randomizer_tools(bpy.types.Panel):
    bl_idname = "ILLUSION_PT_randomizer_tools"
    bl_label = "Illusion Randomizer"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Illusion"

    @classmethod
    def poll(cls, context):
        return (
            context.space_data.tree_type == IllusionRandomizerTree.bl_idname
            and refs.edit_tree(context) is not None
        )

    def draw(self, context):
        layout = self.layout
        # Re-checked despite poll(): a freed reference is truthy and only
        # raises when touched, and draw() runs on every redraw - so without
        # this, one stale pointer becomes a stream of console errors instead
        # of a single failed click.
        tree = refs.edit_tree(context)
        if tree is None:
            return

        layout.prop(tree, "worker_type")

        layout.separator()
        layout.operator("illusion.randomizer_load_yaml", icon="FILEBROWSER")
        layout.operator("illusion.randomizer_arrange_nodes", icon="GRAPH")
        layout.separator()
        # Surfaced here rather than only on failure: Load Assets is the first
        # expensive thing a user clicks, and an unset/incomplete asset
        # directory is the one prerequisite it can't recover from.
        asset_problem = assets.validate_asset_dir(
            assets.effective_asset_dir(context, tree)
        )
        if asset_problem:
            box = layout.box()
            box.label(text=asset_problem, icon="ERROR")
            box.label(text="Set it on the Worker / Output node or in Preferences")
        layout.operator("illusion.randomizer_load_assets", icon="IMPORT")
        # Preview Scene keeps the composition and only re-rolls poses/camera;
        # Change Scene re-rolls everything. Change Scene comes second because
        # it's the one you reach for less often once a scene is composed.
        row = layout.row(align=True)
        row.operator("illusion.randomizer_preview_scene", icon="FILE_REFRESH")
        change = row.row(align=True)
        # Highlighted when an edit is waiting on it, so a setting Preview Scene
        # can't show doesn't just look broken.
        pending = stages.pending_labels()
        change.alert = bool(pending)
        change.operator("illusion.randomizer_change_scene", icon="SHADERFX")
        if pending:
            layout.label(
                text=f"{' and '.join(pending)} need Change Scene",
                icon="INFO",
            )

        # Placed right under the buttons: the reason to reach for it is almost
        # always "the scene doesn't match what I set", which is what you'd
        # notice immediately after clicking one of them.
        layout.prop(tree, "log_level")

        box = layout.box()
        box.prop(tree, "live_preview")
        sub = box.column()
        sub.enabled = tree.live_preview
        sub.prop(tree, "live_include_physics")
        if tree.live_preview and not tree.live_include_physics:
            sub.label(text="Shows pre-settle poses", icon="INFO")

        layout.separator()
        row = layout.row(align=True)
        row.operator(
            "illusion.randomizer_look_through_camera",
            text="Camera View",
            icon="CAMERA_DATA",
        )
        row.operator(
            "illusion.randomizer_exit_camera_view",
            text="Free View",
            icon="ORIENTATION_GIMBAL",
        )
        layout.operator(
            "illusion.randomizer_toggle_viz",
            text="Hide Sampling Volumes" if tree.show_viz else "Show Sampling Volumes",
            icon="MESH_CUBE",
            depress=tree.show_viz,
        )
        if tree.show_viz:
            from .viz import VIZ_BUILDERS

            sel = [n for n in tree.nodes if n.select and n.bl_idname in VIZ_BUILDERS]
            shown = ", ".join(n.bl_label for n in sel) if sel else "all nodes"
            layout.label(text=f"Showing: {shown}", icon="RESTRICT_SELECT_OFF")
        scene = context.scene
        if scene.frame_end > scene.frame_start:
            layout.prop(scene, "frame_current", text="View")
        layout.label(text="Viewport shading: Rendered", icon="SHADING_RENDERED")

        layout.separator()
        layout.operator("illusion.randomizer_save_yaml", icon="EXPORT")


CLASSES = (ILLUSION_PT_randomizer_tools,)
