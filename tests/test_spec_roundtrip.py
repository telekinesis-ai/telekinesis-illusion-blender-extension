"""Round-trip tests for spec_io, run outside Blender against a stub bpy.

The node classes are bpy.types.Node subclasses whose fields are bpy.props
descriptors, so they can't be instantiated here. Instead this stubs bpy just
far enough to import the package's pure-Python modules, then drives
spec_to_tree/tree_to_spec against a fake tree whose nodes are plain objects
carrying the same attribute names and to_spec_dict() implementations.

Run with:  python tests/test_spec_roundtrip.py
"""

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _install_bpy_stub():
    """Minimal bpy so `import illusion_randomizer.spec_io` succeeds."""
    bpy = types.ModuleType("bpy")

    def _prop(**kwargs):
        return kwargs

    bpy.props = types.SimpleNamespace(
        StringProperty=_prop,
        IntProperty=_prop,
        FloatProperty=_prop,
        BoolProperty=_prop,
        EnumProperty=_prop,
        FloatVectorProperty=_prop,
        PointerProperty=_prop,
        CollectionProperty=_prop,
    )

    class _Base:
        pass

    bpy.types = types.SimpleNamespace(
        Node=_Base,
        NodeTree=_Base,
        NodeSocket=_Base,
        Operator=_Base,
        Panel=_Base,
        AddonPreferences=_Base,
        PropertyGroup=_Base,
        Menu=_Base,
    )
    bpy.app = types.SimpleNamespace(
        timers=types.SimpleNamespace(
            register=lambda *a, **k: None,
            is_registered=lambda *a: False,
            unregister=lambda *a: None,
        )
    )
    bpy.utils = types.SimpleNamespace(
        register_class=lambda c: None, unregister_class=lambda c: None
    )
    bpy.data = types.SimpleNamespace(node_groups={}, scenes={})
    bpy.path = types.SimpleNamespace(abspath=lambda p: p)
    sys.modules["bpy"] = bpy


_install_bpy_stub()

from illusion_randomizer import spec_io  # noqa: E402


# --- fake node graph -------------------------------------------------------


class FakeNode:
    """A node whose attributes are set directly, standing in for RNA props.

    Sealed once built: assigning an attribute the real node class doesn't
    define raises, the way Blender's RNA does. Without this, spec_to_tree
    could keep writing to a property that had been removed from the node and
    the test would happily pass."""

    _sealed = False

    def __init__(self, bl_idname, name):
        self.bl_idname = bl_idname
        self.name = name
        self.inputs = {}
        self.outputs = {}
        self.width = 0
        self.location = (0, 0)
        self.use_custom_color = False
        self.color = (0, 0, 0)

    def seal(self):
        self._sealed = True

    def __setattr__(self, key, value):
        if self._sealed and not hasattr(self, key):
            raise AttributeError(
                f"{self.bl_idname} has no property {key!r} - "
                "Blender's RNA would reject this assignment"
            )
        object.__setattr__(self, key, value)


class FakeTree:
    def __init__(self):
        self.worker_type = "bin_picking"
        self.nodes = _FakeNodes()


class _FakeNodes(list):
    _COUNTER = [0]

    def new(self, bl_idname):
        self._COUNTER[0] += 1
        node = _make_node(bl_idname, f"{bl_idname}.{self._COUNTER[0]:03d}")
        self.append(node)
        return node

    def remove(self, node):
        list.remove(self, node)

    def get(self, name):
        return next((n for n in self if n.name == name), None)


def _make_node(bl_idname, name):
    """Build a FakeNode pre-seeded with the real node class's defaults and
    bound to a to_spec_dict() matching the real implementation."""
    node = FakeNode(bl_idname, name)
    _BUILDERS[bl_idname](node)
    node.seal()
    return node


def _asset(node):
    node.object_name = ""
    node.model_path = ""
    node.role = "part"
    node.category_id_is_none = False
    node.category_id = 0
    node.category_name = ""
    node.min_number_instances = 1
    node.max_number_instances = 1
    node.active_in_simulation = False
    node.collision_shape = "CONVEX_HULL"
    node.scale = 1.0
    node.preprocess_model = True
    node.to_spec_dict = lambda: {
        "name": node.object_name,
        "id": None if node.category_id_is_none else node.category_id,
        "supercategory": node.role,
        "category_name": node.category_name,
        "path": node.model_path,
        "instances": {
            "min": node.min_number_instances,
            "max": node.max_number_instances,
        },
        "simulation": {
            "active": node.active_in_simulation,
            "collision_shape": node.collision_shape,
        },
        "scale": node.scale,
        "preprocess_model": node.preprocess_model,
    }


def _instance(node):
    node.role = "part"
    node.min_num_total_objects = 1
    node.max_num_total_objects = 1
    node.to_spec_dict = lambda: {
        "min": node.min_num_total_objects,
        "max": node.max_num_total_objects,
    }


def _material(node):
    node.role = "part"
    node.types = ""
    node.to_spec_dict = lambda: {
        "types": [t.strip() for t in node.types.split(",") if t.strip()],
    }


def _background(node):
    node.categories = ""
    node.to_spec_dict = lambda: {
        "categories": [c.strip() for c in node.categories.split(",") if c.strip()],
    }


def _pose(node):
    node.strategy = "random"
    node.sample_on_surface = ""
    node.min_height = 0.0
    node.max_height = 0.0
    node.face_sample_range_min = 0.25
    node.face_sample_range_max = 0.75
    node.grid_rows = 5
    node.grid_cols = 5
    node.grid_layers = 1
    node.grid_layer_spacing = 0.03
    node.grid_shuffle = True
    node.grid_xy_jitter = 0.0
    node.grid_z_rotation_range_min = 0.0
    node.grid_z_rotation_range_max = 0.0

    def spec():
        out = {
            "strategy": node.strategy,
            "sample_on_surface": node.sample_on_surface or None,
            "params": {
                "min_height": node.min_height,
                "max_height": node.max_height,
                "face_sample_range": [
                    node.face_sample_range_min,
                    node.face_sample_range_max,
                ],
            },
        }
        if node.strategy == "grid":
            out["grid"] = {
                "rows": node.grid_rows,
                "cols": node.grid_cols,
                "layers": node.grid_layers,
                "layer_spacing": node.grid_layer_spacing,
                "shuffle": node.grid_shuffle,
                "xy_jitter": node.grid_xy_jitter,
                "z_rotation_range": [
                    node.grid_z_rotation_range_min,
                    node.grid_z_rotation_range_max,
                ],
            }
        return out

    node.to_spec_dict = spec


def _camera(node):
    node.sampler = "volume_sampler"
    node.number_of_views = 2
    node.use_poi_override = False
    node.point_of_interest = (0.0, 0.0, 0.0)
    node.distance_range_min = 0.5
    node.distance_range_max = 1.3
    node.radius_min = 0.4
    node.radius_max = 0.6
    node.elevation_min = -90.0
    node.elevation_max = 90.0
    node.azimuth_min = -180.0
    node.azimuth_max = 180.0
    node.inplane_rot_min = -30.0
    node.inplane_rot_max = 30.0
    node.to_spec_dict = lambda: {
        "sampler": node.sampler,
        "number_of_views": node.number_of_views,
        "params": {
            "distance_range": [node.distance_range_min, node.distance_range_max],
            "inplane_rot_min": node.inplane_rot_min,
            "inplane_rot_max": node.inplane_rot_max,
        },
    }


def _physics(node):
    node.active = False
    node.min_simulation_time_range_min = 0.5
    node.min_simulation_time_range_max = 1.0
    node.max_simulation_time_range_min = 2.0
    node.max_simulation_time_range_max = 5.0
    node.check_object_interval = 0.5
    node.object_stopped_location_threshold = 0.01
    node.object_stopped_rotation_threshold = 1.0
    node.substeps_per_frame = 10
    node.solver_iters = 10
    node.verbose = False
    node.use_volume_com = False
    node.clean_up_scene = False
    node.to_spec_dict = lambda: {"active": node.active}


def _worker_output(node):
    node.dataset_name = ""
    node.base_output_directory = ""
    node.asset_directory = ""
    node.description = ""
    node.num_images = 5
    node.shard_size = 5
    node.max_size_gb = 10.0
    node.dataset_format = "NONE"
    node.seed = 42
    node.stratify = True
    node.train_val_test_ratio = ""
    node.image_width = 720
    node.image_height = 720
    node.field_of_view = 0.691111
    node.clip_start = 0.1
    node.clip_end = 1000.0
    node.image_format = "PNG"
    node.to_spec_dict = lambda: {
        "dataset_name": node.dataset_name,
        "base_output_directory": node.base_output_directory,
        "asset_directory": node.asset_directory,
        "description": node.description,
        "num_images": node.num_images,
        "shard_size": node.shard_size,
        "max_size_gb": node.max_size_gb,
        "dataset_format": None
        if node.dataset_format == "NONE"
        else node.dataset_format,
        "seed": node.seed,
        "stratify": node.stratify,
        "train_val_tes_ratio": node.train_val_test_ratio or None,
        "camera": {
            "image_width": node.image_width,
            "image_height": node.image_height,
            "field_of_view": node.field_of_view,
            "clip_start": node.clip_start,
            "clip_end": node.clip_end,
        },
        "image_format": node.image_format,
    }


_BUILDERS = {
    "IllusionAssetNode": _asset,
    "IllusionInstanceRandomizerNode": _instance,
    "IllusionMaterialRandomizerNode": _material,
    "IllusionBackgroundRandomizerNode": _background,
    "IllusionPoseRandomizerNode": _pose,
    "IllusionCameraRandomizerNode": _camera,
    "IllusionPhysicsNode": _physics,
    "IllusionWorkerOutputNode": _worker_output,
}


def _load(spec):
    """spec_to_tree with layout.arrange_tree stubbed out (it needs real RNA)."""
    tree = FakeTree()
    import illusion_randomizer.layout as layout

    real = layout.arrange_tree
    layout.arrange_tree = lambda t, rewire=True: None
    try:
        spec_io.spec_to_tree(spec, tree)
    finally:
        layout.arrange_tree = real
    return tree


def _kinds(tree, bl_idname):
    return [n for n in tree.nodes if n.bl_idname == bl_idname]


# --- fixtures --------------------------------------------------------------


def legacy_spec():
    """A spec predating the three new sections, shaped like the production
    files under scripts/pipelines/bin_picking/specs_semi_structured/."""
    return {
        "metadata": {
            "dataset_name": "ds",
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
        "pose_sampling": {"strategy": "random", "params": {}},
        "camera": {"image_width": 848, "image_height": 480},
        "renderer": {"image_format": "PNG"},
        "output": {"max_size_gb": 50},
    }


def spec_with_distractors():
    spec = legacy_spec()
    spec["min_number_visible_distractors"] = 5
    spec["max_number_visible_distractors"] = 10
    spec["distractors"] = [
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
    ]
    return spec


# --- tests -----------------------------------------------------------------


def test_legacy_spec_creates_role_scoped_nodes():
    tree = _load(legacy_spec())

    instances = _kinds(tree, "IllusionInstanceRandomizerNode")
    assert [n.role for n in instances] == ["part", "container"], [
        n.role for n in instances
    ]
    part = next(n for n in instances if n.role == "part")
    assert (part.min_num_total_objects, part.max_num_total_objects) == (4, 8)
    container = next(n for n in instances if n.role == "container")
    assert (container.min_num_total_objects, container.max_num_total_objects) == (1, 1)

    materials = _kinds(tree, "IllusionMaterialRandomizerNode")
    assert {n.role: n.types for n in materials} == {
        "part": "metal",
        "container": "plastic",
    }

    backgrounds = _kinds(tree, "IllusionBackgroundRandomizerNode")
    assert len(backgrounds) == 1
    assert backgrounds[0].categories == "indoor/industrial, indoor/misc"
    print("OK  legacy spec -> nodes seeded with the worker's own defaults")


def test_distractor_nodes_only_when_distractors_present():
    assert not [
        n
        for n in _load(legacy_spec()).nodes
        if getattr(n, "role", None) == "distractor"
    ]

    tree = _load(spec_with_distractors())
    inst = next(
        n
        for n in _kinds(tree, "IllusionInstanceRandomizerNode")
        if n.role == "distractor"
    )
    assert (inst.min_num_total_objects, inst.max_num_total_objects) == (5, 10)
    mat = next(
        n
        for n in _kinds(tree, "IllusionMaterialRandomizerNode")
        if n.role == "distractor"
    )
    assert mat.types == "metal"
    print("OK  distractor nodes appear only when the spec has distractors")


def test_roundtrip_is_stable():
    original = spec_with_distractors()
    once = spec_io.tree_to_spec(_load(original))
    twice = spec_io.tree_to_spec(_load(once))
    assert once == twice, "second round-trip differs"

    assert once["instance_randomizer"] == {
        "part": {"min": 4, "max": 8},
        "container": {"min": 1, "max": 1},
        "distractor": {"min": 5, "max": 10},
    }, once["instance_randomizer"]
    assert once["material_randomizer"] == {
        "part": ["metal"],
        "container": ["plastic"],
        "distractor": ["metal"],
    }, once["material_randomizer"]
    assert once["background_randomizer"] == {
        "categories": ["indoor/industrial", "indoor/misc"],
    }
    # Legacy keys stay in sync with the instance nodes, since that's what the
    # worker falls back to when instance_randomizer is absent.
    assert once["min_number_visible_models"] == 4
    assert once["max_number_visible_models"] == 8
    assert once["min_number_visible_distractors"] == 5
    assert once["max_number_visible_distractors"] == 10
    print("OK  round-trip is stable and the legacy count keys stay in sync")


def test_explicit_sections_win_over_defaults():
    spec = spec_with_distractors()
    spec["instance_randomizer"] = {
        "part": {"min": 2, "max": 3},
        "container": {"min": 1, "max": 2},
    }
    spec["material_randomizer"] = {
        "part": ["plastic"],
        "container": [],
        "distractor": ["metal"],
    }
    spec["background_randomizer"] = {"categories": ["outdoor/day"]}
    tree = _load(spec)

    part = next(
        n for n in _kinds(tree, "IllusionInstanceRandomizerNode") if n.role == "part"
    )
    assert (part.min_num_total_objects, part.max_num_total_objects) == (2, 3)
    # Not listed in instance_randomizer -> falls back to the legacy keys.
    distractor = next(
        n
        for n in _kinds(tree, "IllusionInstanceRandomizerNode")
        if n.role == "distractor"
    )
    assert (distractor.min_num_total_objects, distractor.max_num_total_objects) == (
        5,
        10,
    )

    mats = {n.role: n.types for n in _kinds(tree, "IllusionMaterialRandomizerNode")}
    assert mats == {"part": "plastic", "container": "", "distractor": "metal"}, mats

    bg = _kinds(tree, "IllusionBackgroundRandomizerNode")[0]
    assert bg.categories == "outdoor/day"

    # An empty type list must survive the round-trip as "skip this role",
    # not silently revert to the default.
    out = spec_io.tree_to_spec(tree)
    assert out["material_randomizer"]["container"] == []
    print("OK  explicit spec sections override the defaults, incl. empty = skip")


def test_unknown_background_category_is_preserved():
    """Which categories exist depends on the asset directory, which spec_io
    can't see - so an unrecognised one must survive the round-trip rather than
    being dropped. The node's picker shows it as an orphan."""
    spec = legacy_spec()
    spec["background_randomizer"] = {"categories": ["outdoor/day", "nope/invalid"]}
    tree = _load(spec)
    bg = _kinds(tree, "IllusionBackgroundRandomizerNode")[0]
    assert bg.categories == "outdoor/day, nope/invalid"
    out = spec_io.tree_to_spec(tree)
    assert out["background_randomizer"]["categories"] == ["outdoor/day", "nope/invalid"]
    print("OK  unrecognised background category survives the round-trip")


def test_asset_directory_round_trips_and_is_omitted_when_blank():
    spec = legacy_spec()
    spec["metadata"]["asset_directory"] = "../assets"
    tree = _load(spec)
    output = _kinds(tree, "IllusionWorkerOutputNode")[0]
    assert output.asset_directory == "../assets"

    # Written verbatim, not resolved to an absolute path - a saved spec has to
    # stay portable. preview.py resolves it separately for the worker.
    out = spec_io.tree_to_spec(tree)
    assert out["metadata"]["asset_directory"] == "../assets"

    # Blank means "use the add-on preference", which is machine-specific, so
    # the key must not appear at all rather than appearing empty.
    output.asset_directory = ""
    assert "asset_directory" not in spec_io.tree_to_spec(tree)["metadata"]

    blank = _load(legacy_spec())
    assert _kinds(blank, "IllusionWorkerOutputNode")[0].asset_directory == ""
    assert "asset_directory" not in spec_io.tree_to_spec(blank)["metadata"]
    print("OK  asset_directory round-trips verbatim and is omitted when blank")


def test_duplicate_role_is_rejected():
    tree = _load(legacy_spec())
    dup = tree.nodes.new("IllusionMaterialRandomizerNode")
    dup.role = "part"
    dup.types = "metal"
    try:
        spec_io.tree_to_spec(tree)
    except ValueError as exc:
        assert "both target role" in str(exc), exc
        print("OK  two Material nodes with the same role are rejected")
    else:
        raise AssertionError("expected ValueError for duplicate role")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("\nall spec_io round-trip tests passed")
