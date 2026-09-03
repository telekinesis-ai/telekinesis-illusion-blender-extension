"""Asset node - maps to one entry of a bin_picking YAML spec's `models`/
`distractors` list (and, in turn, to Context.add_model(...))."""

import bpy

from ..live import on_reload_required, on_tunable_change
from ._base import IllusionRandomizerNodeBase

ROLE_ITEMS = (
    (
        "part",
        "Part",
        "A part instance-count/pose/material randomized like the other parts",
    ),
    ("container", "Container", "The bin/crate the parts are placed in or on"),
    (
        "distractor",
        "Distractor",
        "An extra object randomized alongside the parts but not a target part",
    ),
    # Seen in older configs/bin_picking/*.yaml dev specs - not used by any
    # current scripts/pipelines/bin_picking spec, but real files use it.
    ("object", "Object", "Generic supercategory used by some older dev spec files"),
)

COLLISION_SHAPE_ITEMS = (
    ("CONVEX_HULL", "Convex Hull", ""),
    ("MESH", "Mesh", ""),
    ("BOX", "Box", ""),
    ("SPHERE", "Sphere", ""),
    ("CAPSULE", "Capsule", ""),
    ("CYLINDER", "Cylinder", ""),
    ("CONE", "Cone", ""),
)


class IllusionAssetNode(IllusionRandomizerNodeBase, bpy.types.Node):
    bl_idname = "IllusionAssetNode"
    bl_label = "Asset"
    bl_icon = "MESH_DATA"
    node_color = (0.16, 0.28, 0.42)

    object_name: bpy.props.StringProperty(
        name="Object Name",
        description="Unique name this asset is referred to by from randomizer nodes (YAML 'name')",
    )
    model_path: bpy.props.StringProperty(
        name="Model Path",
        description=(
            "Path to the .glb model file, relative to the Asset Directory (YAML 'path'), "
            "e.g. 'models/mechanical_parts/gearwheel_2.glb'. An absolute path also works"
        ),
    )
    role: bpy.props.EnumProperty(
        name="Role",
        description="YAML 'supercategory'",
        items=ROLE_ITEMS,
        default="part",
    )
    category_id_is_none: bpy.props.BoolProperty(
        name="No Category Id",
        description="Leave unlabeled (YAML 'id: None') - typically used for unlabeled distractors",
        default=False,
    )
    category_id: bpy.props.IntProperty(
        name="Category Id",
        description="COCO category ID for this asset's annotations - must be consistent across datasets that share a category",
        default=1,
        min=0,
    )
    category_name: bpy.props.StringProperty(
        name="Category Name",
        description="COCO category label written into annotations, e.g. 'hinge' or 'flange' (YAML 'category_name')",
    )
    min_number_instances: bpy.props.IntProperty(
        name="Min Instances",
        description=(
            "Fewest copies of this asset that may be spawned in a scene. Baked in when "
            "the model is imported - click Load Assets to apply a change"
        ),
        default=1,
        min=0,
        update=on_reload_required,
    )
    max_number_instances: bpy.props.IntProperty(
        name="Max Instances",
        description=(
            "Most copies of this asset that may be spawned in a scene, and how many copies "
            "get created on import. Click Load Assets to apply a change"
        ),
        default=1,
        min=0,
        update=on_reload_required,
    )
    active_in_simulation: bpy.props.BoolProperty(
        name="Active In Simulation",
        description="Whether this object participates in the physics drop simulation",
        default=False,
    )
    collision_shape: bpy.props.EnumProperty(
        name="Collision Shape",
        description="Rigid-body collision shape used while this object is active in the physics simulation",
        items=COLLISION_SHAPE_ITEMS,
        default="CONVEX_HULL",
    )
    # The only Asset field with a live callback: every other one re-imports
    # geometry, but a scale change is applied in place to the already-loaded
    # meshes by BinPickingWorker._apply_model_scales(), which
    # apply_spec_updates() runs on every randomize. So it needs no Load Assets.
    scale: bpy.props.FloatProperty(
        name="Scale",
        description="Uniform scale factor applied to the imported model",
        default=1.0,
        min=0.0,
        update=on_tunable_change,
    )
    preprocess_model: bpy.props.BoolProperty(
        name="Preprocess Model",
        description="Run illusion's standard model cleanup (UV unwrap, clear split normals, dummy material) on import",
        default=True,
    )

    def draw_buttons(self, context, layout):
        layout.prop(self, "object_name")
        layout.prop(self, "model_path")
        layout.prop(self, "role")
        layout.prop(self, "category_id_is_none")
        if not self.category_id_is_none:
            layout.prop(self, "category_id")
        layout.prop(self, "category_name")
        row = layout.row(align=True)
        row.prop(self, "min_number_instances")
        row.prop(self, "max_number_instances")
        layout.prop(self, "active_in_simulation")
        layout.prop(self, "collision_shape")
        layout.prop(self, "scale")
        layout.prop(self, "preprocess_model")

    def to_spec_dict(self) -> dict:
        return {
            "name": self.object_name,
            "id": None if self.category_id_is_none else self.category_id,
            "supercategory": self.role,
            "category_name": self.category_name,
            "path": self.model_path,
            "instances": {
                "min": self.min_number_instances,
                "max": self.max_number_instances,
            },
            "simulation": {
                "active": self.active_in_simulation,
                "collision_shape": self.collision_shape,
            },
            "scale": self.scale,
            "preprocess_model": self.preprocess_model,
        }


CLASSES = (IllusionAssetNode,)
