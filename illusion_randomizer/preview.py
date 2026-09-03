"""Load Assets / Preview operators - the in-process preview path.

No blenderproc-debug subprocess is needed: bproc.init() turns out to be plain
bpy calls (scene reset, render settings) rather than subprocess bootstrapping,
so it runs inside a live Blender session. That is what makes live tuning
possible, and it means the preview exercises the same code path a production
generation run does.

IMPORTANT: bproc.init()'s cleanup (Initializer.remove_all_data) does not
scope to a single scene - it wipes every object/mesh/material/etc across the
ENTIRE .blend file, and deletes every Scene datablock except one literally
named "Scene" (hardcoded in BlenderProc, see
BlenderProc/blenderproc/python/utility/Initializer.py). There is no way to
sandbox this to a dedicated scene - BlenderProc assumes it owns the whole
file. So: run this extension in a dedicated/empty .blend file, never one
with other work you care about. `Load Assets` targets (creating if needed)
the scene named "Scene" specifically, since that's the only name BlenderProc
won't delete out from under it.

Both randomize buttons re-run the already-loaded Context - cheap (re-sampling
only, no disk I/O), so repeated clicks update the same scene quickly instead
of reloading models each time. They differ in how much of the randomizer DAG
they run:

  `Change Scene`  - the full DAG, exactly what a real generation run does:
                    new instances, new materials, new background, new poses,
                    new camera.
  `Preview Scene` - only the pose and camera stages, via the worker's
                    randomize_geometry(). Materials, background and the set of
                    visible instances (including the bin) stay put, so the user
                    can iterate on layout and framing against a stable scene.

With the tree's `live_preview` enabled, live.py drives the `Preview Scene`
path automatically (debounced) whenever a randomizer field changes.

State is kept as module-level globals rather than IDProperties on the tree,
since it holds live Python objects (Context, Randomizer) that can't be
serialized into the .blend file - closing/reopening Blender or switching
trees requires clicking `Load Assets` again.
"""

import random
import tempfile
from pathlib import Path

import bpy
import yaml

from . import assets, log, refs, spec_io, stages

# The one scene name bproc.init()'s cleanup preserves - see module docstring.
PREVIEW_SCENE_NAME = "Scene"

# The two randomize modes - see the module docstring for what each re-samples.
MODE_CHANGE_SCENE = "CHANGE_SCENE"
MODE_PREVIEW_SCENE = "PREVIEW_SCENE"

# `composition` is the list of object names that were visible after the last
# Change Scene, i.e. the scene composition that Preview Scene must preserve.
# None means no scene has been composed yet.
_state = {"worker": None, "scene_name": None, "tree_name": None, "composition": None}


def _get_or_create_preview_scene():
    scene = bpy.data.scenes.get(PREVIEW_SCENE_NAME)
    if scene is None:
        scene = bpy.data.scenes.new(PREVIEW_SCENE_NAME)
    return scene


def _find_node(tree, bl_idname):
    for node in tree.nodes:
        if node.bl_idname == bl_idname:
            return node
    return None


def _tag_redraw():
    """Object transforms normally trigger a redraw on their own, but tag
    explicitly so live updates are visible even when the mouse is parked over
    the node editor rather than the 3D viewport."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in {"VIEW_3D", "NODE_EDITOR"}:
                area.tag_redraw()


def _spec_with_asset_dir(context, tree) -> dict:
    """tree_to_spec() with metadata.asset_directory filled in, absolute.

    BinPickingWorker resolves a relative asset_directory against the spec
    file's own directory, and both callers hand it a spec that isn't where the
    user's spec lives (a temp file, or no file at all) - so the path has to be
    absolute by the time it gets there. assets.effective_asset_dir() does that
    resolution against the directory the tree was loaded from or saved to.

    Raises ValueError, like tree_to_spec, when no usable asset directory is
    configured - so callers keep a single error path."""
    spec = spec_io.tree_to_spec(tree)

    asset_dir = assets.effective_asset_dir(context, tree)
    if not asset_dir:
        raise ValueError(
            "No Asset Directory set - set one on the Worker / Output Settings node, "
            "or in the add-on Preferences"
        )
    problem = assets.validate_asset_dir(asset_dir)
    if problem:
        raise ValueError(problem)

    spec["metadata"]["asset_directory"] = asset_dir
    return spec


def _sync_worker_from_tree(tree, worker) -> list:
    """Push the tree's current values into the already-loaded worker.

    Load Assets bakes the spec into the Context and Randomizer, and rebuilding
    the worker on every slider drag would be far too slow - so the tunables
    are re-applied in place instead. All the mapping lives in
    BinPickingWorker.apply_spec_updates() rather than here, so the node graph
    and a real generation run can't drift apart.

    Returns descriptions of anything that needs a full Load Assets; empty when
    everything took effect. Degrades to a no-op against an older illusion
    checkout that predates apply_spec_updates()."""
    if not hasattr(worker, "apply_spec_updates"):
        return []
    return worker.apply_spec_updates(_spec_with_asset_dir(bpy.context, tree))


def _log_effective_pose_config(worker) -> None:
    """Print the pose-sampling config the worker actually ended up with.

    The node fields travel a long way before they reach a sampler - node ->
    spec dict -> apply_spec_updates() -> _parse_tunable_cfg() - and a field that
    lands in the wrong place in the spec silently falls back to the worker's
    defaults instead of erroring. Printing what the worker holds turns "my
    change did nothing" into a one-glance check of whether the value arrived at
    all, which narrows it down to either the plumbing or the sampling itself.

    Reads private attributes on purpose: there is no public accessor, and this
    is diagnostics, so every lookup is guarded."""
    strategy = getattr(worker, "_pose_sampling_strategy", None)
    if strategy is None:
        return

    if strategy == "grid":
        grid_cfg = getattr(worker, "_grid_cfg", {})
        log.info(f"pose sampling: grid {grid_cfg}")
    else:
        params = getattr(worker, "_pose_sampling_params", {})
        surface = getattr(worker, "_sample_on_surface", None)
        log.info(f"pose sampling: random on_surface={surface} {params}")


def _clear_scene(ctx) -> None:
    """Mirrors SyntheticDataGenerator.generate()'s per-scene reset: hide and
    un-simulate whatever was visible, so the instance randomizers start from an
    empty scene. Without this, instance visibility accumulates across runs."""
    visible_object_names = ctx.get_visible_object_names()
    objects = ctx.get_objects()
    if visible_object_names:
        for object_name in visible_object_names:
            objects[object_name].hide(True)
            objects[object_name].disable_rigid_body()
        ctx.set_visible_object_names([])


def _restore_composition(ctx, composition: list) -> None:
    """Re-show the objects that made up the last composed scene.

    Preview Scene doesn't run the instance randomizers, so it must not clear
    the scene - but it can't leave visibility untouched either:
    ObjectPoseRandomizer permanently hides any object it fails to place without
    collision, and drops it from the visible list. Restoring the recorded
    composition first keeps the bin from thinning out over repeated clicks."""
    objects = ctx.get_objects()
    restored = []
    for object_name in composition:
        obj = objects.get(object_name)
        if obj is None:
            # The object went away with a Load Assets in between - skip it
            # rather than fail the whole preview.
            continue
        # Only the ones a failed placement hid need bringing back; the pose
        # randomizer always hides and un-simulates together, so is_hidden() is
        # an accurate stand-in for "lost its rigid body too".
        if obj.is_hidden():
            obj.hide(False)
            obj.enable_rigid_body()
        restored.append(object_name)
    ctx.set_visible_object_names(restored)


def _randomize_stages(worker, ctx, mode: str) -> list:
    """Run the randomizer nodes this mode is responsible for.

    Which stages count as "geometry" is the worker's business, not the UI's -
    so Preview Scene goes through randomize_geometry() rather than passing a
    stage set from here. Returns warnings for the operator to report.

    Degrades to a full randomize against an older illusion checkout that
    predates stage filtering, same as _sync_worker_from_tree()."""
    if mode == MODE_CHANGE_SCENE:
        worker.get_randomizer().randomize(ctx)
        return []

    if not hasattr(worker, "randomize_geometry"):
        worker.get_randomizer().randomize(ctx)
        return [
            (
                "Installed telekinesis_illusion predates stage filtering - "
                "Preview Scene changed the whole scene. Rebuild and reinstall "
                "the wheel."
            )
        ]

    worker.randomize_geometry(ctx)
    return []


def run_randomize(tree, include_physics: bool, mode: str = MODE_CHANGE_SCENE) -> list:
    """Re-randomize the already-loaded Context.

    `mode` selects how much is re-sampled - see the module docstring. Returns
    warnings worth showing the user; raises RuntimeError if assets haven't been
    loaded yet, or if Preview Scene is asked to run before any scene exists."""
    worker = _state.get("worker")
    if worker is None:
        raise RuntimeError("No assets loaded - click Load Assets first")

    composition = _state.get("composition")
    if mode == MODE_PREVIEW_SCENE and not composition:
        raise RuntimeError("No scene to preview - click Change Scene first")

    import blenderproc as bproc

    ctx = worker.get_context()

    # Reported to the user, not just logged: these are edits that silently did
    # nothing (instance counts and anything else baked in at import), and
    # log.info only reaches the system console, which is closed by default on
    # Windows.
    warnings = []
    if tree is not None:
        warnings.extend(_sync_worker_from_tree(tree, worker))
        _log_effective_pose_config(worker)

    if mode == MODE_CHANGE_SCENE:
        _clear_scene(ctx)
    else:
        _restore_composition(ctx, composition)

    warnings.extend(_randomize_stages(worker, ctx, mode))

    if mode == MODE_CHANGE_SCENE:
        # Snapshot what the instance randomizers just composed, so the next
        # Preview Scene knows what to keep. Copied, since the Context hands
        # back its own live list.
        _state["composition"] = list(ctx.get_visible_object_names())
        stages.clear_pending()
    else:
        # Tell the user which of their edits this mode deliberately didn't
        # apply, rather than letting the setting look broken.
        pending = stages.pending_labels()
        if pending:
            warnings.append(
                f"Preview Scene keeps {' and '.join(pending)} - "
                f"click Change Scene to apply those"
            )

    # Camera poses are keyframed one per view, so clamp the playback range to
    # the sampled views - otherwise the timeline runs to Blender's default 250
    # and most frames just repeat the last pose.
    cam_node = (
        _find_node(tree, "IllusionCameraRandomizerNode") if tree is not None else None
    )
    if cam_node is not None:
        scene = bpy.data.scenes.get(_state.get("scene_name") or "")
        if scene is not None:
            scene.frame_start = 0
            scene.frame_end = max(cam_node.number_of_views - 1, 0)

    physics_node = _find_node(tree, "IllusionPhysicsNode") if tree is not None else None
    if include_physics and physics_node is not None and physics_node.active:
        p = physics_node.to_spec_dict()
        tree_name = tree.name
        bproc.object.simulate_physics_and_fix_final_poses(
            random.uniform(*p["min_simulation_time_range"]),
            random.uniform(*p["max_simulation_time_range"]),
            p["check_object_interval"],
            p["object_stopped_location_threshold"],
            p["object_stopped_rotation_threshold"],
            p["substeps_per_frame"],
            p["solver_iters"],
            p["verbose"],
            p["use_volume_com"],
        )
        # That call runs inside BlenderProc's UndoAfterExecution, which ends on
        # bpy.ops.ed.undo() - and an undo frees and re-reads datablocks, so
        # every Python reference held across it can come back freed. BlenderProc
        # refreshes its own wrappers by name afterwards; `tree` is not one of
        # them, so it has to be re-resolved the same way. Skipping this made the
        # first Change Scene after Load Assets die on 'StructRNA of type
        # IllusionRandomizerTree has been removed' at the viz rebuild below,
        # after the scene had already been composed.
        tree = refs.valid_or_none(bpy.data.node_groups.get(tree_name))

    # Rebuilt after randomizing so the volumes reflect the poses just sampled
    # (the camera volume depends on the visible objects' bounding box).
    from . import viz

    viz.rebuild(tree, ctx)
    if tree is not None and tree.show_viz:
        viz.start_watch()

    _tag_redraw()
    return warnings


def run_randomize_for_live() -> None:
    """Entry point for live.py's debounced timer - resolves the tree from
    stored state (a timer has no space_data/context to read it from).

    Live updates use Preview Scene: dragging a slider should show its effect on
    the layout, not reshuffle the materials and background on every keystroke.
    Before the first Change Scene there is nothing to preview, so this stays
    quiet rather than warning on every edit."""
    tree = bpy.data.node_groups.get(_state.get("tree_name") or "")
    if tree is None or not _state.get("composition"):
        return
    run_randomize(
        tree,
        include_physics=tree.live_include_physics,
        mode=MODE_PREVIEW_SCENE,
    )


class ILLUSION_OT_load_assets(bpy.types.Operator):
    bl_idname = "illusion.randomizer_load_assets"
    bl_label = "Load Assets"
    bl_description = (
        "Build a Context from the current tree and load all models. WARNING: this wipes "
        "ALL objects/meshes/materials in the current .blend file (BlenderProc's own reset "
        "does this globally, not per-scene) - only use this in an empty/dedicated file. "
        "Expensive - only re-run when assets/counts change, use Preview to re-randomize"
    )

    @classmethod
    def poll(cls, context):
        return refs.edit_tree(context) is not None

    def execute(self, context):
        tree = refs.require_edit_tree(self, context)
        if tree is None:
            return {"CANCELLED"}
        try:
            spec = _spec_with_asset_dir(context, tree)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        # Install the loguru sink before anything in the illusion package runs,
        # so model-loading problems are visible too.
        log.configure(tree.log_level)

        # bproc.init()'s reset walks every bpy.data collection - including
        # bpy.data.node_groups, which would delete this very tree mid-load.
        # The vendored BlenderProc honours this marker as an opt-out (see
        # Initializer.remove_all_data).
        tree["bproc_preserve"] = True

        scene = _get_or_create_preview_scene()
        prev_scene = context.window.scene
        context.window.scene = scene

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False, encoding="utf-8"
            ) as f:
                yaml.safe_dump(spec, f)
                spec_path = Path(f.name)

            # Imported here, not at module load time - only needed once the
            # user actually loads assets, and importing it registers/loads
            # blenderproc's whole api surface (see build_wheels.py).
            import blenderproc as bproc
            from blenderproc.python.utility.GlobalStorage import GlobalStorage
            from telekinesis.illusion.workers.bin_picking_worker import BinPickingWorker

            # Context.__init__ always calls bproc.init(), which internally
            # does GlobalStorage.add("bproc_init_complete", True) - add()
            # raises if the key already exists at all (not just if True), so
            # this hits on every Load Assets click after the first one in
            # the same Blender session. bproc.clean_up() resets the scene
            # but not this flag, and GlobalStorage exposes no public removal
            # method - popping the private dict directly is the only way to
            # let bproc.init() succeed again.
            if GlobalStorage.is_in_storage("bproc_init_complete"):
                bproc.clean_up()
                GlobalStorage._storage_dict.pop("bproc_init_complete", None)

            worker = BinPickingWorker(spec_path)
        except Exception as exc:
            if prev_scene is not None:
                try:
                    context.window.scene = prev_scene
                except ReferenceError:
                    # bproc's cleanup may already have deleted it.
                    pass
            self.report({"ERROR"}, f"Failed to load assets: {exc}")
            return {"CANCELLED"}

        _state["worker"] = worker
        _state["scene_name"] = PREVIEW_SCENE_NAME
        _state["tree_name"] = tree.name
        # Freshly loaded assets are all hidden - there is no composed scene for
        # Preview Scene to preserve until Change Scene has run once.
        _state["composition"] = None
        # The whole spec was just baked into a new worker, so nothing is
        # waiting on a Change Scene or a reload any more.
        stages.clear_pending()
        stages.clear_reload_needed()
        self.report({"INFO"}, "Loaded assets - click Change Scene to compose a scene")
        return {"FINISHED"}


def _resolve_tree(context):
    """The tree the buttons act on - the one being edited, falling back to the
    one Load Assets was run against.

    Both candidates go through refs.valid_or_none() rather than a plain None
    check: for one redraw after Load Assets, the node editor's edit_tree can be
    a freed reference. Load Assets switches the window's scene and BlenderProc's
    reset sweeps nearly all of bpy.data (screens and workspaces included), and
    the editor doesn't revalidate its stored tree pointer until it next draws.
    A freed reference isn't None, so the old check sailed past it and the first
    Change Scene click died on 'StructRNA ... has been removed'."""
    tree = refs.edit_tree(context)
    if tree is not None:
        return tree

    tree = refs.valid_or_none(bpy.data.node_groups.get(_state.get("tree_name") or ""))
    if tree is None:
        log.info("could not resolve the node tree - re-run Load Assets")
    return tree


class _RandomizeOperatorBase:
    """Shared execute() for the two randomize buttons - they differ only in
    which mode they pass and what they call the result."""

    mode = MODE_CHANGE_SCENE

    @classmethod
    def poll(cls, context):
        return _state.get("worker") is not None

    def execute(self, context):
        tree = _resolve_tree(context)
        if tree is None:
            # Randomizing without the tree would silently reuse the spec baked
            # in at Load Assets and ignore every node edit since - a scene that
            # looks fine but doesn't match the graph is worse than an error.
            self.report(
                {"ERROR"}, "Lost track of the node tree - click Load Assets again"
            )
            return {"CANCELLED"}
        try:
            warnings = run_randomize(tree, include_physics=True, mode=self.mode)
        except Exception as exc:
            self.report({"ERROR"}, f"{self.bl_label} failed: {exc}")
            return {"CANCELLED"}

        for warning in warnings:
            self.report({"WARNING"}, warning)
        self.report({"INFO"}, f"{self.bl_label} done")
        return {"FINISHED"}


class ILLUSION_OT_preview_scene(_RandomizeOperatorBase, bpy.types.Operator):
    bl_idname = "illusion.randomizer_preview_scene"
    bl_label = "Preview Scene"
    bl_description = (
        "Re-sample object poses and camera views only, keeping the current materials, "
        "background and set of visible objects - use this to iterate on layout and "
        "framing. Includes physics settling if the Physics Simulator node is active. "
        "Requires a scene composed by Change Scene first"
    )
    mode = MODE_PREVIEW_SCENE


class ILLUSION_OT_change_scene(_RandomizeOperatorBase, bpy.types.Operator):
    bl_idname = "illusion.randomizer_change_scene"
    bl_label = "Change Scene"
    bl_description = (
        "Re-randomize everything - which objects are visible, their materials, the "
        "background and the camera - including physics settling if the Physics "
        "Simulator node is active. This is the true-to-output result"
    )
    mode = MODE_CHANGE_SCENE


class ILLUSION_OT_look_through_camera(bpy.types.Operator):
    bl_idname = "illusion.randomizer_look_through_camera"
    bl_label = "Look Through Camera"
    bl_description = (
        "Switch 3D viewports to the scene camera so you see the actual framing that would "
        "be rendered. Scrub the frame number to step through the sampled views"
    )

    def execute(self, context):
        switched = 0
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type != "VIEW_3D":
                    continue
                for space in area.spaces:
                    if space.type == "VIEW_3D":
                        space.region_3d.view_perspective = "CAMERA"
                        switched += 1
        if not switched:
            self.report({"WARNING"}, "No 3D Viewport open to switch to camera view")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Switched {switched} viewport(s) to camera view")
        return {"FINISHED"}


CLASSES = (
    ILLUSION_OT_load_assets,
    ILLUSION_OT_preview_scene,
    ILLUSION_OT_change_scene,
    ILLUSION_OT_look_through_camera,
)
