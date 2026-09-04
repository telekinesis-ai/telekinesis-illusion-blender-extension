"""Resolution of the asset directory, and scanning of what it contains.

Mirrors the illusion library's own rule (utils/assets.py: "the single place in
the library that knows where assets live") on the add-on side, so the node UI,
the preview operator and the sidebar all get the same answer.

The library resolves a spec's `metadata.asset_directory` against the spec
file's own directory. The preview writes its spec to a temp file, so a relative
path from the loaded YAML would resolve against the wrong anchor - hence the
add-on resolves to an absolute path itself and only ever hands the library that.
The literal string stays on the node so Save YAML can round-trip it unchanged.
"""

import os
import time

import bpy

# The subdirectories the library expects: models[].path is resolved against
# the asset dir, MaterialManager reads <asset_dir>/materials and
# BackgroundRandomizer reads <asset_dir>/hdris.
REQUIRED_SUBDIRS = ("models", "hdris", "materials")

# draw_buttons() runs on every node redraw, so the pickers must not hit the
# filesystem each time.
_CACHE_TTL_SECONDS = 5.0
_scan_cache = {}


def _addon_preferences(context):
    """The add-on's preferences, or None if it isn't fully registered yet
    (draw callbacks can run during registration)."""
    addon = context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def effective_asset_dir(context, tree) -> str:
    """The absolute asset directory to use for this tree.

    Prefers the Worker/Output node's Asset Directory - resolved against the
    directory the spec was loaded from or saved to when relative - and falls
    back to the add-on preference. Returns "" when neither is set."""
    node = (
        next((n for n in tree.nodes if n.bl_idname == "IllusionWorkerOutputNode"), None)
        if tree is not None
        else None
    )

    configured = (node.asset_directory or "").strip() if node is not None else ""
    if configured:
        path = bpy.path.abspath(configured)
        if not os.path.isabs(path):
            anchor = (
                bpy.path.abspath(tree.spec_directory) if tree.spec_directory else ""
            )
            # Without an anchor the spec was never loaded from or saved to
            # disk, so a relative path has nothing meaningful to resolve
            # against - fall through to the preference rather than silently
            # anchoring on Blender's cwd (its install directory).
            if not anchor:
                configured = ""
            else:
                return os.path.normpath(os.path.join(anchor, path))
        else:
            return os.path.normpath(path)

    prefs = _addon_preferences(context)
    fallback = (prefs.asset_directory or "").strip() if prefs is not None else ""
    return os.path.normpath(bpy.path.abspath(fallback)) if fallback else ""


def validate_asset_dir(path: str) -> str:
    """Check an asset directory is usable, returning "" or a message saying
    what's wrong.

    Without this the three consumers fail separately and unhelpfully: a
    missing directory raises deep inside resolve_asset_dir(), a missing
    'materials' hits a bare Path.iterdir(), and a missing 'hdris' surfaces as
    "no .exr files found"."""
    if not path:
        return "No asset directory set"
    if not os.path.exists(path):
        return f"Asset directory does not exist: {path}"
    if not os.path.isdir(path):
        return f"Asset directory is not a directory: {path}"

    missing = [
        name for name in REQUIRED_SUBDIRS if not os.path.isdir(os.path.join(path, name))
    ]
    if missing:
        noun = "subdirectories" if len(missing) > 1 else "subdirectory"
        return (
            f"Asset directory {path} is missing the "
            f"{', '.join(repr(m) for m in missing)} {noun}"
        )
    return ""


def subdir_names(asset_dir: str, subdir: str, depth: int = 1) -> list:
    """Names of the directories under <asset_dir>/<subdir>, cached briefly.

    `depth` 1 lists material types ('metal'), depth 2 lists HDRI categories
    ('indoor/industrial') - joined with '/' to match the category strings
    BackgroundRandomizer matches against its catalog paths. Returns an empty
    list when the directory is missing, so callers can fall back to free text.
    """
    key = (asset_dir, subdir, depth)
    cached = _scan_cache.get(key)
    now = time.monotonic()
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    names = sorted(_scan(os.path.join(asset_dir, subdir), depth)) if asset_dir else []
    _scan_cache[key] = (now, names)
    return names


def _scan(root: str, depth: int) -> list:
    try:
        entries = [
            e for e in os.scandir(root) if e.is_dir() and not e.name.startswith(".")
        ]
    except OSError:
        return []

    if depth <= 1:
        return [e.name for e in entries]
    return [f"{e.name}/{child}" for e in entries for child in _scan(e.path, depth - 1)]
