"""The custom node tree type for editing telekinesis.illusion randomizer specs."""

import bpy

from .log import on_log_level_change


WORKER_TYPE_ITEMS = (
    ("bin_picking", "Bin Picking", "Maps 1:1 to BinPickingWorker's YAML schema"),
)

LOG_LEVEL_ITEMS = (
    ("OFF", "Off", "No logging from the illusion package"),
    ("WARNING", "Warnings", "Only problems - failed placements, missing assets"),
    (
        "INFO",
        "Info",
        "Per-object placement detail: collision retries, objects hidden because they "
        "could not be placed, chosen HDRIs and materials",
    ),
    ("DEBUG", "Debug", "Everything, including BlenderProc internals - very noisy"),
)


def _number_of_views(tree) -> int:
    for node in tree.nodes:
        if node.bl_idname == "IllusionCameraRandomizerNode":
            return node.number_of_views
    return 1


def _get_view_index(self):
    scene = bpy.context.scene
    view = scene.frame_current - scene.frame_start + 1
    return min(max(view, 1), _number_of_views(self))


def _set_view_index(self, value):
    scene = bpy.context.scene
    view = min(max(value, 1), _number_of_views(self))
    scene.frame_current = scene.frame_start + view - 1


class IllusionRandomizerTree(bpy.types.NodeTree):
    bl_idname = "IllusionRandomizerTree"
    bl_label = "Illusion Randomizer Tree"
    bl_icon = "NODETREE"

    worker_type: bpy.props.EnumProperty(
        name="Worker",
        description="Which telekinesis.illusion worker/spec schema this tree targets",
        items=WORKER_TYPE_ITEMS,
        default="bin_picking",
    )
    spec_directory: bpy.props.StringProperty(
        name="Spec Directory",
        description=(
            "Directory the spec was last loaded from or saved to. Not shown in the UI - "
            "it is the anchor a relative Asset Directory is resolved against, matching "
            "how BinPickingWorker resolves metadata.asset_directory against the spec file"
        ),
        subtype="DIR_PATH",
    )
    live_preview: bpy.props.BoolProperty(
        name="Live Preview",
        description=(
            "Automatically re-randomize the loaded scene whenever a randomizer field "
            "changes, instead of clicking Preview. Asset changes (model path, per-asset "
            "instance counts) still need Load Assets, since they re-import models"
        ),
        default=False,
    )
    show_viz: bpy.props.BoolProperty(
        name="Show Sampling Volumes",
        description=(
            "Draw wireframe overlays for the camera sampling volume, point of interest, "
            "each sampled camera view, and the part drop region"
        ),
        default=False,
    )
    view_index: bpy.props.IntProperty(
        name="View",
        description=(
            "Which sampled camera view to show. One camera pose is keyframed per "
            "view, and the range is capped at the Camera Pose Randomizer's Number "
            "Of Views"
        ),
        min=1,
        get=_get_view_index,
        set=_set_view_index,
    )
    live_include_physics: bpy.props.BoolProperty(
        name="Include Physics In Live",
        description=(
            "Also run physics settling on each live update. Accurate but slow - with this "
            "off, live updates show pre-settle drop poses, so click Preview for a "
            "true-to-output result"
        ),
        default=False,
    )
    log_level: bpy.props.EnumProperty(
        name="Log Level",
        description=(
            "How much of the illusion randomizers' own logging to print. INFO shows why "
            "each object ended up where it did - collision retries, objects given up on "
            "and hidden - which is usually how you find out why a scene doesn't match "
            "the node graph. Open Window > Toggle System Console to read it"
        ),
        items=LOG_LEVEL_ITEMS,
        default="WARNING",
        update=on_log_level_change,
    )


CLASSES = (IllusionRandomizerTree,)
