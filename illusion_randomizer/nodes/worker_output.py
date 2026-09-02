"""Worker/output settings node - the tree's root. Maps to the top-level
metadata/shard/output fields of a bin_picking YAML spec. COCO info/licenses
are reduced to a single description field here - spec_io.py fills in minimal
valid info/licenses dicts from it, since exhaustive COCO metadata editing
isn't the point of tuning randomization behavior."""

import bpy

from ._base import IllusionRandomizerNodeBase

DATASET_FORMAT_ITEMS = (
    ("NONE", "None", "Don't split into train/val/test"),
    ("yolo", "YOLO", "Split and convert the generated dataset into YOLO format"),
    (
        "coco",
        "COCO",
        "Split the generated dataset into COCO-format train/val/test sets",
    ),
)


class IllusionWorkerOutputNode(IllusionRandomizerNodeBase, bpy.types.Node):
    bl_idname = "IllusionWorkerOutputNode"
    bl_label = "Worker / Output Settings"
    bl_icon = "SETTINGS"
    node_color = (0.36, 0.18, 0.22)

    dataset_name: bpy.props.StringProperty(
        name="Dataset Name",
        description="Name of the dataset - becomes the output subfolder name",
    )
    base_output_directory: bpy.props.StringProperty(
        name="Base Output Directory",
        description="Where generated shards are written, under a subfolder named after Dataset Name",
        subtype="DIR_PATH",
    )
    asset_directory: bpy.props.StringProperty(
        name="Asset Directory",
        description=(
            "Directory holding the 'models', 'hdris' and 'materials' folders (YAML "
            "'metadata.asset_directory'). A relative path is resolved against the spec "
            "file, as BinPickingWorker does. Leave empty to use the Asset Directory "
            "from Add-on Preferences"
        ),
        subtype="DIR_PATH",
    )
    description: bpy.props.StringProperty(
        name="Description",
        description="Human-readable summary written into the dataset's COCO 'info.description' field",
    )
    num_images: bpy.props.IntProperty(
        name="Num Images",
        description="Total number of images to generate for this dataset",
        default=5,
        min=1,
    )
    shard_size: bpy.props.IntProperty(
        name="Shard Size",
        description="Images per shard - Num Images is split into ceil(Num Images / Shard Size) shards",
        default=5,
        min=1,
    )
    # The visible-instance counts that used to live here now belong to the
    # Instance Count Randomizer nodes, one per role - see
    # nodes/instance_randomizer.py. spec_io still writes them back out to the
    # top-level min/max_number_visible_* spec keys.
    max_size_gb: bpy.props.FloatProperty(
        name="Max Output Size (GB)",
        description="Stop generating once the output directory reaches this size",
        default=10.0,
        min=0.0,
    )
    dataset_format: bpy.props.EnumProperty(
        name="Dataset Format",
        description="Whether/how to convert and split the raw generated shards after generation",
        items=DATASET_FORMAT_ITEMS,
        default="NONE",
    )
    seed: bpy.props.IntProperty(
        name="Seed",
        description="Random seed used for the train/val/test split (not for scene randomization itself)",
        default=42,
    )
    stratify: bpy.props.BoolProperty(
        name="Stratify Split",
        description="Keep each category's proportion consistent across the train/val/test split",
        default=True,
    )
    train_val_test_ratio: bpy.props.FloatVectorProperty(
        name="Train/Val/Test Ratio",
        description="Fraction of images assigned to train/val/test respectively - should sum to 1.0",
        size=3,
        default=(0.7, 0.2, 0.1),
        min=0.0,
        max=1.0,
    )

    # Camera (CameraConfig defaults)
    image_width: bpy.props.IntProperty(
        name="Image Width",
        description="Rendered image width in pixels",
        default=720,
        min=1,
    )
    image_height: bpy.props.IntProperty(
        name="Image Height",
        description="Rendered image height in pixels",
        default=720,
        min=1,
    )
    field_of_view: bpy.props.FloatProperty(
        name="Field Of View",
        description="Camera field of view in radians",
        default=0.691111,
    )
    clip_start: bpy.props.FloatProperty(
        name="Clip Start",
        description="Near clipping distance - nothing closer to the camera is rendered",
        default=0.1,
        min=0.0,
    )
    clip_end: bpy.props.FloatProperty(
        name="Clip End",
        description="Far clipping distance - nothing farther from the camera is rendered",
        default=1000.0,
        min=0.0,
    )

    # Renderer
    image_format: bpy.props.StringProperty(
        name="Image Format",
        description="Image file format for rendered output, e.g. PNG or JPEG",
        default="PNG",
    )

    def draw_buttons(self, context, layout):
        layout.prop(self, "dataset_name")
        layout.prop(self, "base_output_directory")

        layout.prop(self, "asset_directory")
        # Show what the path actually resolves to (it may be relative, or come
        # from Preferences), and why it won't work if it won't - otherwise the
        # first sign of trouble is a failure at Load Assets.
        from .. import assets

        resolved = assets.effective_asset_dir(context, self.id_data)
        problem = assets.validate_asset_dir(resolved)
        if problem:
            layout.label(text=problem, icon="ERROR")
        elif not self.asset_directory:
            layout.label(text=f"From Preferences: {resolved}", icon="INFO")
        elif resolved != self.asset_directory:
            layout.label(text=f"Resolves to: {resolved}", icon="INFO")

        layout.prop(self, "description")
        layout.prop(self, "num_images")
        layout.prop(self, "shard_size")
        layout.prop(self, "max_size_gb")
        layout.prop(self, "dataset_format")
        layout.prop(self, "seed")
        layout.prop(self, "stratify")
        layout.prop(self, "train_val_test_ratio")
        layout.separator()
        row = layout.row(align=True)
        row.prop(self, "image_width")
        row.prop(self, "image_height")
        layout.prop(self, "field_of_view")
        row = layout.row(align=True)
        row.prop(self, "clip_start")
        row.prop(self, "clip_end")
        layout.prop(self, "image_format")

    def to_spec_dict(self) -> dict:
        return {
            "dataset_name": self.dataset_name,
            "base_output_directory": self.base_output_directory,
            "asset_directory": self.asset_directory,
            "description": self.description,
            "num_images": self.num_images,
            "shard_size": self.shard_size,
            "max_size_gb": self.max_size_gb,
            "dataset_format": None
            if self.dataset_format == "NONE"
            else self.dataset_format,
            "seed": self.seed,
            "stratify": self.stratify,
            "train_val_tes_ratio": list(self.train_val_test_ratio),
            "camera": {
                "image_width": self.image_width,
                "image_height": self.image_height,
                "field_of_view": self.field_of_view,
                "clip_start": self.clip_start,
                "clip_end": self.clip_end,
            },
            "image_format": self.image_format,
        }


CLASSES = (IllusionWorkerOutputNode,)
