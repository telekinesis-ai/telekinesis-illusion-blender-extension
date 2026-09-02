"""Converts between an IllusionRandomizerTree node graph and the YAML spec
dict BinPickingWorker consumes (`bin_picking` worker mode only for now - see
node_tree.py's `worker_type`).

The DAG *topology* is defined in code, by
BinPickingWorker._add_randomizers() - the node graph is a view of it, not a
definition of it. The spec supplies only the tunable parameters. Which is why
the role-scoped randomizers appear here once per supercategory: that's exactly
how the worker builds them.

The `instance_randomizer`, `material_randomizer` and `background_randomizer`
sections are read by BinPickingWorker with a fallback to its own defaults, so
a spec predating them still behaves identically.
"""

from .nodes.asset import ROLE_ITEMS

KNOWN_ROLES = {item[0] for item in ROLE_ITEMS}

# Kept in sync with the DEFAULT_*_CFG constants in BinPickingWorker (see
# workers/bin_picking_worker.py), which is the source of truth. Duplicated
# rather than imported because the telekinesis package only exists inside
# Blender once the bundled wheels are installed, and importing it would drag
# blenderproc in at add-on registration time - spec_io has to stay importable
# without it. These are what spec_to_tree() seeds the nodes with when a spec
# omits a section, so the graph shows the values the worker will actually use.
DEFAULT_MATERIAL_RANDOMIZER_CFG = {
    "part": ["metal"],
    "container": ["plastic"],
    "distractor": ["metal"],
}
DEFAULT_BACKGROUND_CATEGORIES = ["indoor/industrial", "indoor/misc"]
DEFAULT_CONTAINER_INSTANCE_CFG = {"min": 1, "max": 1}

NODE_KIND_BY_IDNAME = {
    "IllusionAssetNode": "asset",
    "IllusionInstanceRandomizerNode": "instance_randomizer",
    "IllusionPoseRandomizerNode": "pose_randomizer",
    "IllusionMaterialRandomizerNode": "material_randomizer",
    "IllusionBackgroundRandomizerNode": "background_randomizer",
    "IllusionCameraRandomizerNode": "camera_randomizer",
    "IllusionPhysicsNode": "physics",
    "IllusionWorkerOutputNode": "worker_output",
}


def _topological_order(nodes):
    """Kahn's algorithm over the tree's flow-socket links, restricted to the
    given nodes - same approach as Randomizer._topological_order, so the
    export order matches how Randomizer.randomize() would actually execute
    an equivalent graph built via add_node/add_edge."""
    node_set = set(nodes)
    indegree = {n: 0 for n in nodes}
    succ = {n: [] for n in nodes}

    for node in nodes:
        in_socket = node.inputs.get("In")
        if in_socket is None:
            continue
        for link in in_socket.links:
            if link.from_node in node_set:
                succ[link.from_node].append(node)
                indegree[node] += 1

    ready = [n for n in nodes if indegree[n] == 0]
    order = []
    while ready:
        n = ready.pop(0)
        order.append(n)
        for child in succ[n]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)

    if len(order) != len(nodes):
        raise ValueError(
            "Cycle detected among randomizer nodes - the graph must be acyclic."
        )
    return order


def _nodes_by_kind(tree):
    by_kind = {kind: [] for kind in NODE_KIND_BY_IDNAME.values()}
    for node in tree.nodes:
        kind = NODE_KIND_BY_IDNAME.get(node.bl_idname)
        if kind is not None:
            by_kind[kind].append(node)
    return by_kind


def _by_role(nodes, label):
    """Index role-scoped randomizer nodes by their role, rejecting duplicates.

    BinPickingWorker builds one of each per supercategory, so two nodes with
    the same role have no meaning - and keying them into the spec would
    silently keep only the last one."""
    by_role = {}
    for node in nodes:
        if node.role in by_role:
            raise ValueError(
                f"Two {label} nodes both target role {node.role!r} - "
                "the worker builds exactly one per role."
            )
        by_role[node.role] = node
    return by_role


def tree_to_spec(tree) -> dict:
    """Builds a dict matching the YAML schema BinPickingWorker.__init__ reads.
    Raises ValueError if the tree is missing required nodes (exactly one
    IllusionWorkerOutputNode) or has no assets/pose randomizer defined."""
    if tree.worker_type != "bin_picking":
        raise ValueError(
            f"tree_to_spec only supports worker_type='bin_picking', got {tree.worker_type!r}"
        )

    by_kind = _nodes_by_kind(tree)

    output_nodes = by_kind["worker_output"]
    if len(output_nodes) != 1:
        raise ValueError(
            f"Expected exactly one Worker/Output Settings node, found {len(output_nodes)}"
        )
    output = output_nodes[0].to_spec_dict()

    pose_nodes = by_kind["pose_randomizer"]
    if len(pose_nodes) != 1:
        raise ValueError(
            f"Expected exactly one Pose Randomizer node, found {len(pose_nodes)}"
        )
    pose_spec = pose_nodes[0].to_spec_dict()

    # The DAG has exactly one slot per role for these, so two nodes claiming
    # the same role would silently drop one when keyed into the spec below.
    instance_by_role = _by_role(
        by_kind["instance_randomizer"], "Instance Count Randomizer"
    )
    material_by_role = _by_role(by_kind["material_randomizer"], "Material Randomizer")

    background_nodes = by_kind["background_randomizer"]
    if len(background_nodes) > 1:
        raise ValueError(
            f"Expected at most one Background Randomizer node, found {len(background_nodes)}"
        )

    asset_nodes = _topological_order(by_kind["asset"])
    assets = [n.to_spec_dict() for n in asset_nodes]

    # Context.add_model() rejects a new object_name that's a substring of
    # any already-registered one (including "" itself, which is a substring
    # of everything) - an empty Object Name field surfaces there as a
    # confusing "Redundant model import" error instead of pointing at the
    # actual empty field, so catch it here with a clearer message.
    empty_name_nodes = [n.name for n, a in zip(asset_nodes, assets) if not a["name"]]
    if empty_name_nodes:
        raise ValueError(
            f"Asset node(s) {empty_name_nodes} have an empty Object Name field - set it before loading."
        )
    names = [a["name"] for a in assets]
    if len(names) != len(set(names)):
        raise ValueError(f"Duplicate Object Name(s) among Asset nodes: {names}")

    models = [a for a in assets if a["supercategory"] != "distractor"]
    distractors = [a for a in assets if a["supercategory"] == "distractor"]

    # BinPickingWorker._add_randomizers() directly indexes
    # self._model_supercatgory_map["part"]/["container"] with no .get()
    # fallback - a tree missing either role would otherwise fail deep inside
    # BinPickingWorker with a bare `KeyError('part')`, not a clear message.
    present_roles = {a["supercategory"] for a in models}
    missing_roles = {"part", "container"} - present_roles
    if missing_roles:
        raise ValueError(
            f"Missing Asset node(s) with role {sorted(missing_roles)} - "
            "BinPickingWorker requires at least one 'part' and one 'container' asset."
        )

    # The top-level min/max_number_visible_* keys are now derived from the
    # role-scoped Instance nodes rather than the Worker/Output node.
    def counts_for(role, fallback_min, fallback_max):
        node = instance_by_role.get(role)
        if node is None:
            return {"min": fallback_min, "max": fallback_max}
        return node.to_spec_dict()

    part_counts = counts_for("part", 1, 1)
    distractor_counts = counts_for("distractor", 0, 0)

    spec = {
        "metadata": {
            "dataset_name": output["dataset_name"],
            "package_version": "0.0.1",
            "use_case": "instance_segmentation",
            "annotation_format": "coco_instances_rle",
            "num_images": output["num_images"],
            "base_output_directory": output["base_output_directory"],
            "info": {
                "description": output["description"],
                "url": "",
                "version": "1.0.0",
                "year": 2026,
                "contributor": "",
            },
            "licenses": [{"id": 1, "name": "", "url": ""}],
        },
        "shard": {"size": output["shard_size"]},
        # Still written even though `instance_randomizer` below supersedes
        # them: they're part of the documented schema and are what
        # BinPickingWorker falls back to when that section is absent.
        "min_number_visible_models": part_counts["min"],
        "max_number_visible_models": part_counts["max"],
        "models": models,
        "min_number_visible_distractors": distractor_counts["min"],
        "max_number_visible_distractors": distractor_counts["max"],
        "distractors": distractors,
        "pose_sampling": {
            "strategy": pose_spec["strategy"],
            "sample_on_surface": pose_spec.get("sample_on_surface"),
            "params": {
                **pose_spec.get("params", {}),
                **({"grid": pose_spec["grid"]} if "grid" in pose_spec else {}),
            },
        },
        "camera": output["camera"],
        "renderer": {"image_format": output["image_format"]},
        "output": {
            "max_size_gb": output["max_size_gb"],
            "dataset_format": output["dataset_format"],
            "train_val_tes_ratio": output["train_val_tes_ratio"],
            "seed": output["seed"],
            "stratify": output["stratify"],
        },
    }

    # Omitted entirely when blank, so a tree relying on the add-on preference
    # doesn't bake an empty key into a spec other people run.
    if output["asset_directory"]:
        spec["metadata"]["asset_directory"] = output["asset_directory"]

    camera_nodes = by_kind["camera_randomizer"]
    if camera_nodes:
        spec["camera_pose_randomizer"] = camera_nodes[0].to_spec_dict()

    physics_nodes = by_kind["physics"]
    if physics_nodes:
        spec["physics_simulator"] = physics_nodes[0].to_spec_dict()

    # Role-keyed sections mirroring the per-supercategory randomizers
    # BinPickingWorker builds. Omitted entirely when there are no such nodes,
    # so the worker falls back to its own defaults rather than seeing an empty
    # dict (which would read as "disable everything").
    if instance_by_role:
        spec["instance_randomizer"] = {
            role: node.to_spec_dict() for role, node in instance_by_role.items()
        }
    if material_by_role:
        spec["material_randomizer"] = {
            role: node.to_spec_dict()["types"]
            for role, node in material_by_role.items()
        }
    if background_nodes:
        spec["background_randomizer"] = background_nodes[0].to_spec_dict()

    return spec


def spec_to_tree(spec: dict, tree) -> None:
    """Populates an empty IllusionRandomizerTree from a bin_picking YAML
    spec dict (e.g. loaded from one of configs/*.yaml).
    Node positions and flow links are assigned by layout.arrange_tree() once
    every node exists."""
    tree.worker_type = "bin_picking"

    metadata = spec.get("metadata", {})
    shard = spec.get("shard", {})
    output_cfg = spec.get("output", {})
    camera_cfg = spec.get("camera", {})
    renderer_cfg = spec.get("renderer", {})

    output_node = tree.nodes.new("IllusionWorkerOutputNode")
    output_node.dataset_name = metadata.get("dataset_name", "")
    output_node.base_output_directory = metadata.get("base_output_directory", "")
    output_node.asset_directory = metadata.get("asset_directory", "")
    output_node.description = metadata.get("info", {}).get("description", "")
    output_node.num_images = metadata.get("num_images", 5)
    output_node.shard_size = shard.get("size", 5)
    # The min/max_number_visible_* keys go to the Instance Count Randomizer
    # nodes further down, not here.
    output_node.max_size_gb = output_cfg.get("max_size_gb", 10.0)
    output_node.dataset_format = output_cfg.get("dataset_format") or "NONE"
    output_node.seed = output_cfg.get("seed", 42)
    output_node.stratify = output_cfg.get("stratify", True)
    if output_cfg.get("train_val_tes_ratio"):
        output_node.train_val_test_ratio = output_cfg["train_val_tes_ratio"]
    output_node.image_width = camera_cfg.get("image_width", 720)
    output_node.image_height = camera_cfg.get("image_height", 720)
    output_node.field_of_view = camera_cfg.get("field_of_view", 0.691111)
    output_node.clip_start = camera_cfg.get("clip_start", 0.1)
    output_node.clip_end = camera_cfg.get("clip_end", 1000.0)
    output_node.image_format = renderer_cfg.get("image_format", "PNG")

    def add_asset(entry, role_override=None):
        node = tree.nodes.new("IllusionAssetNode")
        node.object_name = entry.get("name", "")
        node.model_path = entry.get("path", "")
        role = role_override or entry.get("supercategory", "part")
        if role not in KNOWN_ROLES:
            print(
                f"[illusion_randomizer] Unknown supercategory {role!r} for asset "
                f"{node.object_name!r}, falling back to 'part'"
            )
            role = "part"
        node.role = role
        cat_id = entry.get("id")
        # Existing spec YAMLs write an unquoted `id: None`, which plain YAML
        # parses as the literal string "None" (YAML null is `null`/`~`), not
        # Python None - handle both so real spec files import correctly.
        is_none = cat_id is None or cat_id == "None"
        node.category_id_is_none = is_none
        if not is_none:
            node.category_id = cat_id
        node.category_name = entry.get("category_name", "")
        instances = entry.get("instances", {})
        node.min_number_instances = instances.get("min", 1)
        node.max_number_instances = instances.get("max", 1)
        simulation = entry.get("simulation", {})
        node.active_in_simulation = simulation.get("active", False)
        node.collision_shape = simulation.get("collision_shape", "CONVEX_HULL")
        node.scale = entry.get("scale", 1.0)
        node.preprocess_model = entry.get("preprocess_model", True)
        return node

    for entry in spec.get("models", []):
        add_asset(entry)
    for entry in spec.get("distractors", []):
        add_asset(entry, role_override="distractor")

    pose_cfg = spec.get("pose_sampling", {})
    pose_node = tree.nodes.new("IllusionPoseRandomizerNode")
    pose_node.strategy = pose_cfg.get("strategy", "random")
    pose_node.sample_on_surface = pose_cfg.get("sample_on_surface") or ""
    params = pose_cfg.get("params", {})
    pose_node.min_height = params.get("min_height", 0.0)
    pose_node.max_height = params.get("max_height", 0.0)
    face_range = params.get("face_sample_range", [0.25, 0.75])
    pose_node.face_sample_range_min, pose_node.face_sample_range_max = face_range
    grid = params.get("grid", {})
    pose_node.grid_rows = grid.get("rows", 5)
    pose_node.grid_cols = grid.get("cols", 5)
    pose_node.grid_layers = grid.get("layers", 1)
    pose_node.grid_layer_spacing = grid.get("layer_spacing", 0.03)
    pose_node.grid_shuffle = grid.get("shuffle", True)
    pose_node.grid_xy_jitter = grid.get("xy_jitter", 0.0)
    z_range = grid.get("z_rotation_range", [0.0, 0.0])
    pose_node.grid_z_rotation_range_min, pose_node.grid_z_rotation_range_max = z_range

    cpr_cfg = spec.get("camera_pose_randomizer")
    if cpr_cfg:
        cam_node = tree.nodes.new("IllusionCameraRandomizerNode")
        cam_node.sampler = cpr_cfg.get("sampler", "volume_sampler")
        cam_node.number_of_views = cpr_cfg.get("number_of_views", 2)
        cpr_params = cpr_cfg.get("params", {})
        dist_range = cpr_params.get("distance_range", [0.5, 1.3])
        cam_node.distance_range_min, cam_node.distance_range_max = dist_range
        cam_node.inplane_rot_min = cpr_params.get("inplane_rot_min", -30.0)
        cam_node.inplane_rot_max = cpr_params.get("inplane_rot_max", 30.0)
        cam_node.radius_min = cpr_params.get("radius_min", 0.4)
        cam_node.radius_max = cpr_params.get("radius_max", 0.6)
        cam_node.elevation_min = cpr_params.get("elevation_min", -90.0)
        cam_node.elevation_max = cpr_params.get("elevation_max", 90.0)
        cam_node.azimuth_min = cpr_params.get("azimuth_min", -180.0)
        cam_node.azimuth_max = cpr_params.get("azimuth_max", 180.0)
        # 'point_of_interst' (volume sampler, sic - the typo is the real spec
        # key) / 'center' (shell sampler) are optional overrides; only a
        # literal coordinate triple maps onto this node's vector field. The
        # samplers also accept a list of object-name prefixes, which has no
        # node equivalent - warn rather than silently dropping it.
        poi = cpr_params.get("point_of_interst", cpr_params.get("center"))
        if (
            isinstance(poi, (list, tuple))
            and len(poi) == 3
            and all(isinstance(v, (int, float)) for v in poi)
        ):
            cam_node.use_poi_override = True
            cam_node.point_of_interest = tuple(float(v) for v in poi)
        elif poi is not None:
            print(
                f"[illusion_randomizer] camera_pose_randomizer point of interest {poi!r} "
                "is not a coordinate triple - not represented in the node graph"
            )

    physics_cfg = spec.get("physics_simulator")
    if physics_cfg:
        physics_node = tree.nodes.new("IllusionPhysicsNode")
        physics_node.active = physics_cfg.get("active", False)
        min_t = physics_cfg.get("min_simulation_time_range", [0.5, 1.0])
        (
            physics_node.min_simulation_time_range_min,
            physics_node.min_simulation_time_range_max,
        ) = min_t
        max_t = physics_cfg.get("max_simulation_time_range", [2.0, 5.0])
        (
            physics_node.max_simulation_time_range_min,
            physics_node.max_simulation_time_range_max,
        ) = max_t
        physics_node.check_object_interval = physics_cfg.get(
            "check_object_interval", 0.5
        )
        physics_node.object_stopped_location_threshold = physics_cfg.get(
            "object_stopped_location_threshold", 0.01
        )
        physics_node.object_stopped_rotation_threshold = physics_cfg.get(
            "object_stopped_rotation_threshold", 1.0
        )
        physics_node.substeps_per_frame = physics_cfg.get("substeps_per_frame", 10)
        physics_node.solver_iters = physics_cfg.get("solver_iters", 10)
        physics_node.verbose = physics_cfg.get("verbose", False)
        physics_node.use_volume_com = physics_cfg.get("use_volume_com", False)
        physics_node.clean_up_scene = physics_cfg.get("clean_up_scene", False)

    # The role-scoped randomizers. These mirror what
    # BinPickingWorker._add_randomizers() builds unconditionally, so they're
    # created whether or not the spec carries the corresponding section - a
    # spec that omits one is seeded with the same defaults the worker falls
    # back to, so the graph shows the values a run would actually use.
    has_distractors = bool(spec.get("distractors"))
    roles = ["part", "container"] + (["distractor"] if has_distractors else [])

    instance_cfg = spec.get("instance_randomizer") or {}
    instance_fallbacks = {
        "part": {
            "min": spec.get("min_number_visible_models", 1),
            "max": spec.get("max_number_visible_models", 1),
        },
        "container": DEFAULT_CONTAINER_INSTANCE_CFG,
        "distractor": {
            "min": spec.get("min_number_visible_distractors", 0),
            "max": spec.get("max_number_visible_distractors", 0),
        },
    }
    for role in roles:
        counts = instance_cfg.get(role) or instance_fallbacks[role]
        instance_node = tree.nodes.new("IllusionInstanceRandomizerNode")
        instance_node.role = role
        instance_node.min_num_total_objects = counts.get("min", 0)
        instance_node.max_num_total_objects = counts.get("max", 0)

    material_cfg = spec.get("material_randomizer") or {}
    for role in roles:
        # A role explicitly present but empty means "skip material
        # randomization" - keep the node so it stays visible and re-enableable,
        # just with no types selected.
        types = material_cfg.get(role, DEFAULT_MATERIAL_RANDOMIZER_CFG[role])
        material_node = tree.nodes.new("IllusionMaterialRandomizerNode")
        material_node.role = role
        material_node.types = ", ".join(types or [])

    background_cfg = spec.get("background_randomizer") or {}
    categories = background_cfg.get("categories", DEFAULT_BACKGROUND_CATEGORIES)
    background_node = tree.nodes.new("IllusionBackgroundRandomizerNode")
    # Kept verbatim rather than filtered against a known set: which categories
    # exist depends on the configured asset directory, which spec_io has no
    # access to. Anything absent from disk shows up as an orphan in the node's
    # picker, which is more useful than dropping it silently here.
    background_node.categories = ", ".join(categories)

    # Imported here rather than at module scope: layout imports bpy, and
    # keeping spec_io importable without a full node-UI stack makes the
    # round-trip easier to test.
    from .layout import arrange_tree

    arrange_tree(tree)
