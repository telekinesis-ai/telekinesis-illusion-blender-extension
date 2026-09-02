"""Debounced live re-randomize when tunable node fields change.

Property `update=` callbacks fire on every keystroke/slider drag, and a
re-randomize can take a noticeable amount of time (collision retries, and
physics settling if enabled). Doing that work synchronously inside the
callback would stall Blender's UI mid-drag, so callbacks only set a dirty
flag and a short bpy.app.timers debounce does the actual work once the user
stops fiddling.

Deliberately kept import-light (no spec_io/preview at module level): the node
modules import this, and preview.py imports spec_io which imports
nodes.asset - importing preview here too would be circular. The timer body
lazy-imports preview instead.
"""

import bpy

from . import stages

DEBOUNCE_SECONDS = 0.35

_dirty = False
_timer_pending = False


def on_tunable_change(self, context):
    """`update=` callback for node fields that only need a re-randomize (not
    a full asset reload) to take effect. Assets/model paths deliberately
    don't use this - changing those requires re-importing models, which is
    far too slow to run on every edit."""
    # Recorded before the live_preview check, and regardless of it: whether a
    # change needs a Change Scene to become visible has nothing to do with
    # whether live updates are switched on.
    stages.mark_edited(self.bl_idname)

    tree = getattr(self, "id_data", None)
    if tree is None or not getattr(tree, "live_preview", False):
        return
    mark_dirty()


def mark_dirty():
    global _dirty, _timer_pending
    _dirty = True
    if not _timer_pending:
        _timer_pending = True
        bpy.app.timers.register(_flush, first_interval=DEBOUNCE_SECONDS)


def _flush():
    """Timer body - runs in the main thread, so touching bpy data is safe.
    Returns None to unregister (a fresh timer is registered per dirty
    burst)."""
    global _dirty, _timer_pending
    _timer_pending = False
    if not _dirty:
        return None
    _dirty = False

    from . import preview

    try:
        preview.run_randomize_for_live()
    except Exception as exc:  # noqa: BLE001 - a timer must never propagate
        # Can't self.report() outside an operator; print so it lands in the
        # console rather than silently swallowing tuning failures.
        print(f"[illusion_randomizer] Live preview failed: {exc}")
    return None
