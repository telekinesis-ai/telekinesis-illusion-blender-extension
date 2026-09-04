"""Which randomize mode each node's settings take effect in.

Preview Scene only re-runs the pose and camera stages of the worker's
randomizer DAG, so a change to an instance count, a material list or the
background has no visible effect until Change Scene runs. That is the whole
point of the split - but without something tracking it, editing one of those
fields looks like the setting is broken rather than deferred.

So this module mirrors the stage tags BinPickingWorker._add_randomizers()
attaches to its randomizer nodes, keyed by GUI node instead of worker node, and
records which stages have pending edits. panel.py and preview.py use that to
say "click Change Scene" instead of leaving the user guessing.

The same idea one step further out: edits that are baked in when the models are
imported (the Asset instance counts) are tracked separately, since not even
Change Scene applies them - they highlight Load Assets until it runs.

Kept import-light and dependency-free (no bpy, no spec_io) so live.py, panel.py
and preview.py can all import it without the circular-import dance described in
live.py's docstring.
"""

STAGE_COMPOSITION = "composition"
STAGE_POSE = "pose"
STAGE_APPEARANCE = "appearance"
STAGE_CAMERA = "camera"

# Mirrors the NodeConfig(stage=...) tagging in
# BinPickingWorker._add_randomizers(), keyed by GUI node. Only nodes wired to
# live.on_tunable_change can appear here, since that callback is what feeds
# mark_edited().
#
# Deliberately absent:
#   Asset          - its only tunable field is Scale, and that one needs no
#                    Change Scene: _apply_model_scales() re-scales the loaded
#                    meshes in place on every sync, so Preview Scene shows it.
#                    Every other Asset field re-imports geometry - the instance
#                    counts go through live.on_reload_required and the reload
#                    flag below, the rest have no callback at all. Either way
#                    there is nothing for Change Scene to defer, so leaving
#                    Asset out makes mark_edited() a no-op for it.
#   Physics        - not a randomizer node; runs after randomize() in both
#                    modes, so its settings are never deferred.
#   Worker/Output  - only affects a real generation run.
STAGE_BY_IDNAME = {
    "IllusionInstanceRandomizerNode": STAGE_COMPOSITION,
    "IllusionPoseRandomizerNode": STAGE_POSE,
    "IllusionMaterialRandomizerNode": STAGE_APPEARANCE,
    "IllusionBackgroundRandomizerNode": STAGE_APPEARANCE,
    "IllusionCameraRandomizerNode": STAGE_CAMERA,
}

# Must match BinPickingWorker.GEOMETRY_STAGES.
PREVIEW_SCENE_STAGES = frozenset({STAGE_POSE, STAGE_CAMERA})

# Wording for the "needs Change Scene" hint, in the user's terms rather than
# the pipeline's.
STAGE_LABELS = {
    STAGE_COMPOSITION: "object counts",
    STAGE_APPEARANCE: "materials/background",
}

# Stages edited since the last Change Scene whose changes Preview Scene can't
# show. Module state rather than tree IDProperties for the same reason
# preview.py keeps its own: it describes this session's editing, not the
# document, and a stale flag surviving in the .blend would be worse than
# useless.
_pending = set()


# Set when a field that is baked into the imported models is edited. Separate
# from _pending because no amount of re-randomizing applies it: only a fresh
# Load Assets does, so Change Scene must not clear it.
_reload_pending = False


def mark_reload_needed() -> None:
    """Record an edit that only re-importing the models can apply."""
    global _reload_pending
    _reload_pending = True


def clear_reload_needed() -> None:
    """Called once Load Assets has re-imported everything."""
    global _reload_pending
    _reload_pending = False


def reload_needed() -> bool:
    """Whether an edit is waiting on a Load Assets."""
    return _reload_pending


def mark_edited(bl_idname: str) -> None:
    """Record an edit to a node, if its stage is one Preview Scene skips."""
    stage = STAGE_BY_IDNAME.get(bl_idname)
    if stage is not None and stage not in PREVIEW_SCENE_STAGES:
        _pending.add(stage)


def clear_pending() -> None:
    """Called once Change Scene has run and applied everything."""
    _pending.clear()


def pending_labels() -> list:
    """User-facing names of the stages waiting on a Change Scene, or []."""
    return sorted(STAGE_LABELS[stage] for stage in _pending if stage in STAGE_LABELS)
