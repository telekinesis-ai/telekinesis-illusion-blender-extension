"""Wireframe helpers that show *where* the randomizers are allowed to sample,
plus a marker per sampled camera view.

Everything lives in a dedicated collection, is display_type='WIRE' and
hide_render=True, and is rebuilt from scratch on each refresh. The geometry
mirrors the maths in sampler/camera_pose_sampler.py and
sampler/upper_region_sampler.py - see the comments on each builder for how
each shape is derived, since a viz that silently diverges from the sampler is
worse than none.

These objects are non-mesh-relevant to the pipeline (BlenderProc's collision
and rendering paths select MESH objects from the illusion Context, not by
scanning the scene) and are wiped by the next Load Assets like everything
else.
"""

import math

import bpy

from . import refs

COLLECTION_NAME = "Illusion Viz"
_MARKER_KEY = "illusion_viz"

# Node selection doesn't fire property update callbacks, and mutating data
# from a depsgraph handler risks re-entrancy, so selection is polled instead.
# Only a tuple of names is compared per tick, so this is cheap.
WATCH_INTERVAL = 0.25
_watch_pending = False
_last_signature = None


def _selection_signature(tree):
    return tuple(n.name for n in tree.nodes if n.select and n.bl_idname in VIZ_BUILDERS)


def start_watch():
    """Begin polling node selection so the viz follows what's selected."""
    global _watch_pending
    if not _watch_pending:
        _watch_pending = True
        bpy.app.timers.register(_watch, first_interval=WATCH_INTERVAL)


def _watch():
    global _watch_pending, _last_signature
    from . import preview

    # Validated, not just None-checked: a timer that raises gets unregistered
    # by Blender, so a freed reference here would silently kill the overlays
    # until the next Load Assets.
    tree = refs.valid_or_none(
        bpy.data.node_groups.get(preview._state.get("tree_name") or "")
    )
    if tree is None or not getattr(tree, "show_viz", False):
        _watch_pending = False
        _last_signature = None
        return None  # stop polling

    signature = _selection_signature(tree)
    if signature != _last_signature:
        worker = preview._state.get("worker")
        if worker is not None:
            rebuild(tree, worker.get_context())
        else:
            _last_signature = signature
    return WATCH_INTERVAL


def _get_collection():
    coll = bpy.data.collections.get(COLLECTION_NAME)
    if coll is None:
        coll = bpy.data.collections.new(COLLECTION_NAME)
    scene = bpy.context.scene
    if coll.name not in {c.name for c in scene.collection.children}:
        scene.collection.children.link(coll)
    # Survive the next bproc.init() reset only if the user asked for it? No -
    # deliberately NOT marked bproc_preserve, so a fresh Load Assets starts
    # from a clean scene and stale volumes can't linger.
    return coll


def clear():
    """Remove every previously-built viz object (and its data)."""
    coll = bpy.data.collections.get(COLLECTION_NAME)
    if coll is None:
        return
    for obj in list(coll.objects):
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if isinstance(data, bpy.types.Mesh) and data.users == 0:
            bpy.data.meshes.remove(data)


def _add(obj, color=(0.2, 0.8, 1.0, 1.0)):
    obj[_MARKER_KEY] = True
    obj.display_type = "WIRE"
    obj.hide_render = True
    obj.hide_select = True
    obj.color = color
    _get_collection().objects.link(obj)
    return obj


def _wire_box(name, center, size):
    """Axis-aligned box given its centre and (x, y, z) extents."""
    mesh = bpy.data.meshes.new(name)
    sx, sy, sz = (s / 2.0 for s in size)
    verts = [
        (-sx, -sy, -sz),
        (sx, -sy, -sz),
        (sx, sy, -sz),
        (-sx, sy, -sz),
        (-sx, -sy, sz),
        (sx, -sy, sz),
        (sx, sy, sz),
        (-sx, sy, sz),
    ]
    edges = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    ]
    mesh.from_pydata(verts, edges, [])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = center
    return obj


def _wire_sphere(name, center, radius, segments=32):
    """Three orthogonal circles - enough to read a radius without the cost of
    a full UV sphere."""
    mesh = bpy.data.meshes.new(name)
    verts, edges = [], []
    for axis in range(3):
        start = len(verts)
        for i in range(segments):
            angle = 2.0 * math.pi * i / segments
            c, s = radius * math.cos(angle), radius * math.sin(angle)
            if axis == 0:
                verts.append((c, s, 0.0))
            elif axis == 1:
                verts.append((c, 0.0, s))
            else:
                verts.append((0.0, c, s))
        edges.extend((start + i, start + (i + 1) % segments) for i in range(segments))
    mesh.from_pydata(verts, edges, [])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = center
    return obj


def _camera_marker(name, matrix_world, scale=0.05):
    """Little frustum showing a sampled view's position and facing. Blender
    cameras look down their local -Z."""
    mesh = bpy.data.meshes.new(name)
    d = scale
    verts = [
        (0.0, 0.0, 0.0),
        (-d, -d, -2 * d),
        (d, -d, -2 * d),
        (d, d, -2 * d),
        (-d, d, -2 * d),
    ]
    edges = [(0, 1), (0, 2), (0, 3), (0, 4), (1, 2), (2, 3), (3, 4), (4, 1)]
    mesh.from_pydata(verts, edges, [])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.matrix_world = matrix_world
    return obj


def _visible_bbox(illusion_ctx):
    """Same AABB volume_sampler derives its sampling box from."""
    from telekinesis.illusion.sampler.camera_pose_sampler import (
        compute_axis_aligned_bbox,
    )

    return compute_axis_aligned_bbox(context=illusion_ctx, visible_only=True)


def _poi(illusion_ctx, cam_node):
    from telekinesis.illusion.types.object import compute_poi

    if cam_node is not None and cam_node.use_poi_override:
        return tuple(cam_node.point_of_interest)
    objects = [o for o in illusion_ctx.get_objects().values() if not o.is_hidden()]
    if not objects:
        return None
    return tuple(compute_poi(objects))


def build_camera_viz(illusion_ctx, cam_node):
    """POI marker, the camera sampling region, and one marker per sampled
    view."""
    poi = _poi(illusion_ctx, cam_node)
    if poi is not None:
        _add(_wire_sphere("Illusion POI", poi, 0.02), color=(1.0, 0.9, 0.2, 1.0))

    if cam_node is not None:
        if cam_node.sampler == "volume_sampler":
            # volume_sampler samples uniformly in the visible-objects AABB and
            # then adds U(min, max) along +Z, so the reachable region is that
            # box stretched upward by the distance range.
            length, width, height, center = _visible_bbox(illusion_ctx)
            d_min, d_max = cam_node.distance_range_min, cam_node.distance_range_max
            z_lo = center[2] - height / 2.0 + d_min
            z_hi = center[2] + height / 2.0 + d_max
            _add(
                _wire_box(
                    "Illusion Camera Volume",
                    (center[0], center[1], (z_lo + z_hi) / 2.0),
                    (length, width, max(z_hi - z_lo, 1e-6)),
                ),
                color=(0.2, 0.6, 1.0, 1.0),
            )
        elif poi is not None:
            # shell_sampler picks a radius in [radius_min, radius_max] about
            # the POI; the elevation/azimuth wedge isn't drawn (two radii
            # already convey the reachable band).
            _add(
                _wire_sphere("Illusion Camera Shell Min", poi, cam_node.radius_min),
                color=(0.2, 0.6, 1.0, 1.0),
            )
            _add(
                _wire_sphere("Illusion Camera Shell Max", poi, cam_node.radius_max),
                color=(0.2, 0.6, 1.0, 1.0),
            )

    # One marker per keyframed view, so every sampled view is visible at once
    # even though the viewport can only look through one at a time.
    scene = bpy.context.scene
    camera = scene.camera
    if camera is None:
        return
    views = cam_node.number_of_views if cam_node is not None else 1
    original_frame = scene.frame_current
    try:
        for frame in range(views):
            scene.frame_set(frame)
            _add(
                _camera_marker(
                    f"Illusion View {frame + 1}", camera.matrix_world.copy()
                ),
                color=(1.0, 0.4, 0.2, 1.0),
            )
    finally:
        scene.frame_set(original_frame)


def _cross_marker(name, points, size=0.008):
    """One small 3-axis cross per point, all in a single mesh so a large grid
    stays cheap to draw."""
    mesh = bpy.data.meshes.new(name)
    verts, edges = [], []
    for px, py, pz in points:
        base = len(verts)
        verts.extend(
            [
                (px - size, py, pz),
                (px + size, py, pz),
                (px, py - size, pz),
                (px, py + size, pz),
                (px, py, pz - size),
                (px, py, pz + size),
            ]
        )
        edges.extend([(base, base + 1), (base + 2, base + 3), (base + 4, base + 5)])
    mesh.from_pydata(verts, edges, [])
    mesh.update()
    return bpy.data.objects.new(name, mesh)


def _grid_cell_centres(container, pose_node):
    """Replicates GridRegionSampler._rebuild_grid's cell centres, minus the
    per-call random jitter (jitter is shown as the cell box instead). Uses the
    sampler's own select_upper_region so the face/vectors can't diverge."""
    import numpy as np
    from telekinesis.illusion.sampler.upper_region_sampler import select_upper_region

    upper_dir = np.array([0.0, 0.0, 1.0])
    region = select_upper_region(container.get_object(), upper_dir)
    base_point = np.array(region.base_point(), dtype=float)
    vec1, vec2 = (np.array(v, dtype=float) for v in region.vectors())

    u_min, u_max = pose_node.face_sample_range_min, pose_node.face_sample_range_max
    points = []
    for layer in range(pose_node.grid_layers):
        layer_offset = upper_dir * (
            pose_node.min_height + layer * pose_node.grid_layer_spacing
        )
        for i in range(pose_node.grid_rows):
            u = u_min + (u_max - u_min) * (i + 0.5) / pose_node.grid_rows
            for j in range(pose_node.grid_cols):
                v = u_min + (u_max - u_min) * (j + 0.5) / pose_node.grid_cols
                points.append(tuple(base_point + u * vec1 + v * vec2 + layer_offset))
    return points


def build_pose_region_viz(illusion_ctx, pose_node, container_names):
    """The region ObjectPoseRandomizer may drop parts into: the container's
    bounding box top face narrowed by face_sample_range, extruded from
    min_height to max_height (mirrors upper_region_sampler).

    `container_names` comes from the Asset nodes' Role, matching how
    BinPickingWorker resolves the drop surface (it looks for the visible
    object whose name starts with a container asset's name) rather than
    guessing from mesh names.
    """
    if pose_node is None:
        return

    if pose_node.sample_on_surface:
        wanted = [pose_node.sample_on_surface]
    else:
        wanted = list(container_names)
    if not wanted:
        return

    container = next(
        (
            obj
            for name, obj in illusion_ctx.get_objects().items()
            if not obj.is_hidden() and any(w in name for w in wanted)
        ),
        None,
    )
    if container is None:
        return

    if pose_node.strategy == "grid":
        points = _grid_cell_centres(container, pose_node)
        if points:
            _add(
                _cross_marker("Illusion Grid Cells", points), color=(0.4, 1.0, 0.4, 1.0)
            )
        return

    bb = container.get_object().get_bound_box()
    xs = [v[0] for v in bb]
    ys = [v[1] for v in bb]
    zs = [v[2] for v in bb]
    lo, hi = pose_node.face_sample_range_min, pose_node.face_sample_range_max
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    top_z = max(zs)

    x_lo = x_min + (x_max - x_min) * lo
    x_hi = x_min + (x_max - x_min) * hi
    y_lo = y_min + (y_max - y_min) * lo
    y_hi = y_min + (y_max - y_min) * hi
    z_lo = top_z + pose_node.min_height
    z_hi = top_z + pose_node.max_height

    _add(
        _wire_box(
            "Illusion Drop Region",
            ((x_lo + x_hi) / 2.0, (y_lo + y_hi) / 2.0, (z_lo + z_hi) / 2.0),
            (max(x_hi - x_lo, 1e-6), max(y_hi - y_lo, 1e-6), max(z_hi - z_lo, 1e-6)),
        ),
        color=(0.4, 1.0, 0.4, 1.0),
    )


def _instance_highlights(illusion_ctx, asset_names, label, color, visible_only=True):
    """Wire box around each instance whose name matches one of `asset_names`.
    Prefix matching mirrors how the randomizers resolve their own targets
    (RandomizerNode uses name.startswith(prefixes))."""
    if not asset_names:
        return 0
    prefixes = tuple(asset_names)
    drawn = 0
    for name, obj in illusion_ctx.get_objects().items():
        if visible_only and obj.is_hidden():
            continue
        if not name.startswith(prefixes):
            continue
        bb = obj.get_object().get_bound_box()
        xs = [v[0] for v in bb]
        ys = [v[1] for v in bb]
        zs = [v[2] for v in bb]
        center = (
            (min(xs) + max(xs)) / 2,
            (min(ys) + max(ys)) / 2,
            (min(zs) + max(zs)) / 2,
        )
        size = (
            max(max(xs) - min(xs), 1e-6),
            max(max(ys) - min(ys), 1e-6),
            max(max(zs) - min(zs), 1e-6),
        )
        _add(_wire_box(f"Illusion {label} {name}", center, size), color=color)
        drawn += 1
    return drawn


def _container_names(tree):
    return [
        n.object_name
        for n in tree.nodes
        if n.bl_idname == "IllusionAssetNode"
        and n.role == "container"
        and n.object_name
    ]


def _viz_camera(tree, illusion_ctx, node):
    build_camera_viz(illusion_ctx, node)


def _viz_pose(tree, illusion_ctx, node):
    build_pose_region_viz(illusion_ctx, node, _container_names(tree))


def _viz_asset(tree, illusion_ctx, node):
    """Every currently-visible instance of just this asset."""
    if node.object_name:
        _instance_highlights(
            illusion_ctx, [node.object_name], "Asset", (0.3, 0.7, 1.0, 1.0)
        )


def _viz_instance(tree, illusion_ctx, node):
    """Which of this node's targets ended up visible after randomizing - the
    thing an instance-count randomizer actually controls."""
    from .names import asset_names_for_role

    _instance_highlights(
        illusion_ctx,
        asset_names_for_role(tree, node.role),
        "Instance",
        (0.9, 0.6, 1.0, 1.0),
    )


def _viz_material(tree, illusion_ctx, node):
    from .names import asset_names_for_role

    _instance_highlights(
        illusion_ctx,
        asset_names_for_role(tree, node.role),
        "Material",
        (1.0, 0.5, 0.8, 1.0),
    )


def _viz_physics(tree, illusion_ctx, node):
    """Objects that actually take part in the simulation, i.e. assets with
    Active In Simulation ticked."""
    if not node.active:
        return
    simulated = [
        n.object_name
        for n in tree.nodes
        if n.bl_idname == "IllusionAssetNode"
        and n.object_name
        and n.active_in_simulation
    ]
    _instance_highlights(illusion_ctx, simulated, "Physics", (1.0, 0.55, 0.15, 1.0))


# Node kinds with something spatial worth drawing. Background (HDRI) and
# Worker/Output (metadata) have no spatial extent, so they're deliberately
# absent rather than drawing something misleading.
VIZ_BUILDERS = {
    "IllusionCameraRandomizerNode": _viz_camera,
    "IllusionPoseRandomizerNode": _viz_pose,
    "IllusionAssetNode": _viz_asset,
    "IllusionInstanceRandomizerNode": _viz_instance,
    "IllusionMaterialRandomizerNode": _viz_material,
    "IllusionPhysicsNode": _viz_physics,
}


def viz_nodes(tree):
    """Nodes whose viz should be drawn: the selected ones, or all of them when
    nothing is selected."""
    candidates = [n for n in tree.nodes if n.bl_idname in VIZ_BUILDERS]
    selected = [n for n in candidates if n.select]
    return selected or candidates


def rebuild(tree, illusion_ctx):
    """Refresh the visualizations for whichever nodes are selected. Failures
    are reported to the console rather than aborting a randomize."""
    global _last_signature

    clear()
    if tree is None or not tree.show_viz:
        _last_signature = None
        return

    for node in viz_nodes(tree):
        try:
            VIZ_BUILDERS[node.bl_idname](tree, illusion_ctx, node)
        except Exception as exc:  # noqa: BLE001 - viz must never break tuning
            print(f"[illusion_randomizer] {node.bl_idname} viz failed: {exc}")

    _last_signature = _selection_signature(tree)


class ILLUSION_OT_toggle_viz(bpy.types.Operator):
    bl_idname = "illusion.randomizer_toggle_viz"
    bl_label = "Show Sampling Volumes"
    bl_description = (
        "Toggle wireframe overlays for the selected node - camera sampling volume and "
        "views, part drop region or grid cells, or the instances a node targets. With "
        "nothing selected, every node's overlay is drawn"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return refs.edit_tree(context) is not None

    def execute(self, context):
        from . import preview

        tree = refs.require_edit_tree(self, context)
        if tree is None:
            return {"CANCELLED"}
        tree.show_viz = not tree.show_viz

        worker = preview._state.get("worker")
        if worker is None:
            if tree.show_viz:
                self.report({"WARNING"}, "Load Assets first - nothing to visualize yet")
            else:
                clear()
            return {"FINISHED"}

        rebuild(tree, worker.get_context())
        if tree.show_viz:
            start_watch()
        self.report(
            {"INFO"}, f"Sampling volumes {'shown' if tree.show_viz else 'hidden'}"
        )
        return {"FINISHED"}


class ILLUSION_OT_exit_camera_view(bpy.types.Operator):
    bl_idname = "illusion.randomizer_exit_camera_view"
    bl_label = "Exit Camera View"
    bl_description = (
        "Return 3D viewports to a free orbit view (same as pressing Numpad 0)"
    )

    def execute(self, context):
        switched = 0
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type != "VIEW_3D":
                    continue
                for space in area.spaces:
                    if (
                        space.type == "VIEW_3D"
                        and space.region_3d.view_perspective == "CAMERA"
                    ):
                        space.region_3d.view_perspective = "PERSP"
                        switched += 1
        self.report({"INFO"}, f"Left camera view in {switched} viewport(s)")
        return {"FINISHED"}


CLASSES = (ILLUSION_OT_toggle_viz, ILLUSION_OT_exit_camera_view)
