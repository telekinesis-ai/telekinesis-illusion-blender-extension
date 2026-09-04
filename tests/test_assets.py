"""Tests for asset-directory resolution, run outside Blender against a stub bpy.

The interesting case is a relative asset_directory: the illusion library
anchors it on the spec file, but preview writes its spec to a temp file - so
the add-on must anchor it on where the user's spec actually lives, and never
on Blender's cwd (its install directory).

Run with:  python tests/test_assets.py
"""

import os
import sys
import tempfile
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_spec_roundtrip import _install_bpy_stub  # noqa: E402

_install_bpy_stub()

import bpy  # noqa: E402

# The real bpy.path.abspath expands Blender's '//' blend-relative prefix and
# leaves everything else alone.
bpy.path.abspath = lambda p: (
    os.path.join(os.getcwd(), p[2:]) if p.startswith("//") else p
)

from illusion_randomizer import assets  # noqa: E402


class FakeNode:
    bl_idname = "IllusionWorkerOutputNode"

    def __init__(self, asset_directory=""):
        self.asset_directory = asset_directory


class FakeTree:
    def __init__(self, asset_directory="", spec_directory=""):
        self.nodes = [FakeNode(asset_directory)]
        self.spec_directory = spec_directory


def fake_context(pref_dir=""):
    prefs = types.SimpleNamespace(asset_directory=pref_dir)
    addon = types.SimpleNamespace(preferences=prefs)
    return types.SimpleNamespace(
        preferences=types.SimpleNamespace(addons={"illusion_randomizer": addon})
    )


def make_asset_tree(root, subdirs=assets.REQUIRED_SUBDIRS):
    for name in subdirs:
        os.makedirs(os.path.join(root, name), exist_ok=True)
    return root


def test_absolute_node_value_wins():
    with tempfile.TemporaryDirectory() as tmp:
        node_dir = make_asset_tree(os.path.join(tmp, "from_node"))
        pref_dir = make_asset_tree(os.path.join(tmp, "from_pref"))
        tree = FakeTree(asset_directory=node_dir)
        assert assets.effective_asset_dir(
            fake_context(pref_dir), tree
        ) == os.path.normpath(node_dir)
    print("OK  an absolute node value beats the preference")


def test_relative_node_value_anchors_on_spec_directory():
    """The bug this guards: anchoring '../assets' on cwd or on the temp spec's
    directory instead of the directory the spec was loaded from."""
    with tempfile.TemporaryDirectory() as tmp:
        make_asset_tree(os.path.join(tmp, "assets"))
        spec_dir = os.path.join(tmp, "configs")
        os.makedirs(spec_dir, exist_ok=True)

        tree = FakeTree(asset_directory="../assets", spec_directory=spec_dir)
        resolved = assets.effective_asset_dir(fake_context(), tree)

        assert resolved == os.path.normpath(os.path.join(tmp, "assets")), resolved
        assert assets.validate_asset_dir(resolved) == ""
        assert tempfile.gettempdir() not in resolved or resolved.startswith(tmp)
    print("OK  a relative node value anchors on the spec directory")


def test_relative_without_anchor_falls_back_to_preference():
    """A tree never loaded from or saved to disk has nothing to anchor on -
    falling back beats silently resolving against Blender's install dir."""
    with tempfile.TemporaryDirectory() as tmp:
        pref_dir = make_asset_tree(os.path.join(tmp, "from_pref"))
        tree = FakeTree(asset_directory="../assets", spec_directory="")
        assert assets.effective_asset_dir(
            fake_context(pref_dir), tree
        ) == os.path.normpath(pref_dir)
    print("OK  a relative value with no anchor falls back to the preference")


def test_blank_node_uses_preference_and_blank_both_gives_empty():
    with tempfile.TemporaryDirectory() as tmp:
        pref_dir = make_asset_tree(os.path.join(tmp, "from_pref"))
        assert assets.effective_asset_dir(
            fake_context(pref_dir), FakeTree()
        ) == os.path.normpath(pref_dir)
        assert assets.effective_asset_dir(fake_context(), FakeTree()) == ""
    print("OK  blank node falls back to the preference; both blank gives ''")


def test_validate_names_what_is_missing():
    with tempfile.TemporaryDirectory() as tmp:
        assert "No asset directory set" in assets.validate_asset_dir("")

        missing = os.path.join(tmp, "nope")
        assert "does not exist" in assets.validate_asset_dir(missing)

        partial = make_asset_tree(os.path.join(tmp, "partial"), ["hdris", "materials"])
        msg = assets.validate_asset_dir(partial)
        assert "'models'" in msg and "subdirectory" in msg, msg

        empty = os.path.join(tmp, "empty")
        os.makedirs(empty)
        msg = assets.validate_asset_dir(empty)
        for name in assets.REQUIRED_SUBDIRS:
            assert repr(name) in msg, msg
        assert "subdirectories" in msg, msg

        assert assets.validate_asset_dir(make_asset_tree(os.path.join(tmp, "ok"))) == ""
    print("OK  validate_asset_dir names exactly which subdirectories are missing")


def test_subdir_names_scans_at_the_right_depth():
    with tempfile.TemporaryDirectory() as tmp:
        root = make_asset_tree(tmp)
        for p in (
            "materials/metal",
            "materials/plastic",
            "materials/.hidden",
            "hdris/indoor/industrial",
            "hdris/indoor/studio",
            "hdris/outdoor/day",
        ):
            os.makedirs(os.path.join(root, *p.split("/")), exist_ok=True)

        assert assets.subdir_names(root, "materials") == ["metal", "plastic"]
        # depth 2, joined with '/' to match the category strings
        # BackgroundRandomizer matches against its catalog paths.
        assert assets.subdir_names(root, "hdris", depth=2) == [
            "indoor/industrial",
            "indoor/studio",
            "outdoor/day",
        ]
        assert assets.subdir_names(root, "nonexistent") == []
        assert assets.subdir_names("", "materials") == []
    print("OK  subdir_names scans depth 1 and 2, skipping dotfiles")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("\nall asset-resolution tests passed")
