"""In-Blender smoke test for the role-scoped randomizer nodes.

Runs against the *installed* extension, so it exercises the real RNA
properties, the real node tree and the real Add menu - the things the
stub-bpy round-trip test in test_spec_roundtrip.py can't reach.

Usage:  ./dev_reinstall.sh tests/check_in_blender.py
"""

import os
import sys
import traceback

import bpy

MODULE = "bl_ext.user_default.telekinesis_illusion_randomizer"

failures = []


def check(label, fn):
    try:
        fn()
    except Exception:
        failures.append(label)
        print(f"FAIL {label}")
        traceback.print_exc()
    else:
        print(f"OK   {label}")


SPEC = {
    "metadata": {
        "dataset_name": "smoke",
        "num_images": 10,
        "base_output_directory": "/out",
        "info": {"description": "d"},
        "licenses": [],
    },
    "shard": {"size": 5},
    "min_number_visible_models": 4,
    "max_number_visible_models": 8,
    "models": [
        {
            "name": "Hinge_01",
            "id": 11,
            "supercategory": "part",
            "category_name": "hinge",
            "path": "a.glb",
            "instances": {"min": 0, "max": 8},
            "simulation": {"active": True, "collision_shape": "CONVEX_HULL"},
            "scale": 1.0,
            "preprocess_model": True,
        },
        {
            "name": "euronorm_1",
            "id": 1,
            "supercategory": "container",
            "category_name": "bin",
            "path": "b.glb",
            "instances": {"min": 0, "max": 1},
            "simulation": {"active": False, "collision_shape": "MESH"},
            "scale": 1.0,
            "preprocess_model": True,
        },
    ],
    "min_number_visible_distractors": 5,
    "max_number_visible_distractors": 10,
    "distractors": [
        {
            "name": "Screw_Head_01",
            "id": "None",
            "supercategory": "distractor",
            "category_name": "distractor",
            "path": "c.glb",
            "instances": {"min": 5, "max": 10},
            "simulation": {"active": True, "collision_shape": "CONVEX_HULL"},
            "scale": 1.0,
            "preprocess_model": True,
        },
    ],
    "pose_sampling": {"strategy": "random", "params": {}},
    "camera": {"image_width": 848, "image_height": 480},
    "renderer": {"image_format": "PNG"},
    "output": {"max_size_gb": 50},
}


def main():
    check(
        "add-on is enabled",
        lambda: _assert(MODULE in bpy.context.preferences.addons.keys()),
    )

    addon = sys.modules[MODULE]
    spec_io = sys.modules[MODULE + ".spec_io"]

    def add_menu_registered():
        _assert(
            addon._draw_add_menu in bpy.types.NODE_MT_add._dyn_ui_initialize(),
            "NODE_MT_add draw function not appended",
        )
        for cls in addon.MENU_CLASSES:
            _assert(
                hasattr(bpy.types, cls.bl_idname), f"{cls.bl_idname} not registered"
            )

    check("Add menu uses the 4.2 NODE_MT_add pattern", add_menu_registered)

    tree = bpy.data.node_groups.new("SmokeTree", "IllusionRandomizerTree")

    def load():
        spec_io.spec_to_tree(SPEC, tree)

    check("spec_to_tree runs against real RNA", load)
    if failures:
        return

    def by_idname(idname):
        return [n for n in tree.nodes if n.bl_idname == idname]

    def nodes_created():
        inst = by_idname("IllusionInstanceRandomizerNode")
        mat = by_idname("IllusionMaterialRandomizerNode")
        bg = by_idname("IllusionBackgroundRandomizerNode")
        _assert(
            sorted(n.role for n in inst) == ["container", "distractor", "part"],
            f"instance roles: {[n.role for n in inst]}",
        )
        _assert(
            sorted(n.role for n in mat) == ["container", "distractor", "part"],
            f"material roles: {[n.role for n in mat]}",
        )
        _assert(len(bg) == 1, f"expected 1 background node, got {len(bg)}")
        _assert(
            bg[0].categories == "indoor/industrial, indoor/misc",
            f"categories: {bg[0].categories}",
        )
        part = next(n for n in inst if n.role == "part")
        _assert((part.min_num_total_objects, part.max_num_total_objects) == (4, 8))

    check("all three role-scoped node kinds appear after load", nodes_created)

    def wired():
        for node in tree.nodes:
            if node.bl_idname == "IllusionWorkerOutputNode":
                _assert(
                    node.inputs["In"].links, "output node left unwired by arrange_tree"
                )

    check("arrange_tree wired the new nodes into the chain", wired)

    def worker_output_clean():
        node = by_idname("IllusionWorkerOutputNode")[0]
        for gone in (
            "min_number_visible_models",
            "max_number_visible_models",
            "min_number_visible_distractors",
            "max_number_visible_distractors",
        ):
            _assert(
                gone not in node.bl_rna.properties,
                f"{gone} still on the Worker/Output node",
            )

    check("instance counts removed from Worker/Output", worker_output_clean)

    def roundtrip():
        once = spec_io.tree_to_spec(tree)
        _assert(
            once["instance_randomizer"]
            == {
                "part": {"min": 4, "max": 8},
                "container": {"min": 1, "max": 1},
                "distractor": {"min": 5, "max": 10},
            },
            once["instance_randomizer"],
        )
        _assert(
            once["material_randomizer"]
            == {
                "part": ["metal"],
                "container": ["plastic"],
                "distractor": ["metal"],
            },
            once["material_randomizer"],
        )
        _assert(
            once["background_randomizer"]
            == {"categories": ["indoor/industrial", "indoor/misc"]},
            once["background_randomizer"],
        )
        _assert(once["min_number_visible_models"] == 4)
        _assert(once["max_number_visible_distractors"] == 10)

    check("tree_to_spec emits the role-keyed sections", roundtrip)

    def draws():
        """draw_buttons must not raise - a node that throws while drawing
        makes the whole editor unusable."""
        for node in tree.nodes:
            node.draw_buttons(bpy.context, _LayoutProbe())

    check("every node's draw_buttons runs", draws)

    _check_asset_dir(addon)


EXAMPLE_SPEC = (
    r"C:\Users\AndranikAristakesyan\Repos\illusion\configs"
    r"\example_bin_picking_gearwheel_2.yaml"
)


def _check_asset_dir(addon):
    """The reported bug: loading the shipped example spec must resolve an
    asset directory instead of falling back to Blender's cwd."""
    import yaml

    if not os.path.exists(EXAMPLE_SPEC):
        print(f"SKIP example spec not found at {EXAMPLE_SPEC}")
        return

    assets = sys.modules[MODULE + ".assets"]
    spec_io = sys.modules[MODULE + ".spec_io"]
    prefs = bpy.context.preferences.addons[MODULE].preferences

    tree = bpy.data.node_groups.new("AssetDirTree", "IllusionRandomizerTree")
    spec = yaml.safe_load(open(EXAMPLE_SPEC, encoding="utf-8"))
    tree.spec_directory = os.path.dirname(EXAMPLE_SPEC)
    spec_io.spec_to_tree(spec, tree)

    output = next(n for n in tree.nodes if n.bl_idname == "IllusionWorkerOutputNode")
    expected = os.path.normpath(
        os.path.join(os.path.dirname(EXAMPLE_SPEC), "..", "assets")
    )

    def relative_resolves():
        _assert(output.asset_directory == "../assets", output.asset_directory)
        resolved = assets.effective_asset_dir(bpy.context, tree)
        _assert(resolved == expected, f"{resolved!r} != {expected!r}")
        _assert(
            assets.validate_asset_dir(resolved) == "",
            assets.validate_asset_dir(resolved),
        )

    check(
        "example spec's '../assets' resolves against the spec directory",
        relative_resolves,
    )

    def preview_spec_is_absolute():
        preview = sys.modules[MODULE + ".preview"]
        built = preview._spec_with_asset_dir(bpy.context, tree)
        injected = built["metadata"]["asset_directory"]
        _assert(os.path.isabs(injected), f"not absolute: {injected}")
        _assert(injected == expected, f"{injected!r} != {expected!r}")

    check(
        "preview injects an absolute asset_directory into the spec",
        preview_spec_is_absolute,
    )

    def pickers_scan_the_tree():
        mats = assets.subdir_names(expected, "materials")
        hdris = assets.subdir_names(expected, "hdris", depth=2)
        _assert(mats == ["metal", "plastic"], mats)
        _assert(hdris and all("/" in h for h in hdris), hdris)
        # The tree must not offer categories it doesn't ship - that was the
        # old hardcoded list's failure mode.
        _assert("indoor/misc" not in hdris, hdris)
        _assert("indoor/industrial" in hdris, hdris)

    check(
        "material/HDRI pickers list what the asset tree actually ships",
        pickers_scan_the_tree,
    )

    def preference_fallback():
        output.asset_directory = ""
        prefs.asset_directory = expected
        try:
            resolved = assets.effective_asset_dir(bpy.context, tree)
            _assert(resolved == expected, resolved)
            _assert("asset_directory" not in spec_io.tree_to_spec(tree)["metadata"])
        finally:
            prefs.asset_directory = ""
            output.asset_directory = "../assets"

    check(
        "blank node field falls back to the Preferences asset directory",
        preference_fallback,
    )


class _LayoutProbe:
    """Accepts the subset of the UILayout API the nodes use."""

    def _self(self, *a, **k):
        return self

    box = column = row = _self
    separator = prop = prop_enum = label = _self

    def operator(self, *a, **k):
        return _OpProbe()

    def menu(self, *a, **k):
        return self


class _OpProbe:
    def __setattr__(self, k, v):
        pass


def _assert(cond, msg=""):
    if not cond:
        raise AssertionError(msg or "assertion failed")


main()
print()
if failures:
    print(f"{len(failures)} CHECK(S) FAILED: {failures}")
    sys.exit(1)
print("all in-Blender checks passed")
