"""Camera pose randomizer node - maps to CameraPoseRandomizer.

The node's params are emitted per sampler because the two samplers take
different keyword arguments (sampler/camera_pose_sampler.py):
volume_sampler(point_of_interst, distance_range, ...) vs
shell_sampler(center, radius_min, radius_max, elevation_*, azimuth_*, ...).
CameraPoseRandomizer forwards **params straight into the chosen function, so
emitting volume keys for a shell sampler raises TypeError at randomize time.
"""

import bpy

from ._base import IllusionRandomizerNodeBase
from ..live import on_tunable_change

SAMPLER_ITEMS = (
    (
        "volume_sampler",
        "Volume Sampler",
        "Sample the camera inside the scene bounding box, then offset upward by the distance range",
    ),
    (
        "shell_sampler",
        "Shell Sampler",
        "Sample the camera on a spherical shell around the point of interest",
    ),
)


class IllusionCameraRandomizerNode(IllusionRandomizerNodeBase, bpy.types.Node):
    bl_idname = "IllusionCameraRandomizerNode"
    bl_label = "Camera Pose Randomizer"
    bl_icon = "CAMERA_DATA"
    node_color = (0.20, 0.36, 0.26)

    sampler: bpy.props.EnumProperty(
        name="Sampler",
        description="Sampling strategy used to place the camera each view",
        items=SAMPLER_ITEMS,
        default="volume_sampler",
        update=on_tunable_change,
    )
    number_of_views: bpy.props.IntProperty(
        name="Number Of Views",
        description="How many camera views (images) to render per scene",
        default=2,
        min=1,
        update=on_tunable_change,
    )

    use_poi_override: bpy.props.BoolProperty(
        name="Override Point Of Interest",
        description=(
            "Aim the camera at a fixed world coordinate instead of the automatically "
            "computed centre of the visible objects"
        ),
        default=False,
        update=on_tunable_change,
    )
    point_of_interest: bpy.props.FloatVectorProperty(
        name="Point Of Interest",
        description="World-space point the camera is aimed at (YAML 'point_of_interst' / shell 'center')",
        size=3,
        default=(0.0, 0.0, 0.0),
        update=on_tunable_change,
    )

    # volume_sampler params
    distance_range_min: bpy.props.FloatProperty(
        name="Distance Min",
        description="Smallest upward offset from the scene bounding box (volume sampler)",
        default=0.5,
        min=0.0,
        update=on_tunable_change,
    )
    distance_range_max: bpy.props.FloatProperty(
        name="Distance Max",
        description="Largest upward offset from the scene bounding box (volume sampler)",
        default=1.3,
        min=0.0,
        update=on_tunable_change,
    )

    # shell_sampler params
    radius_min: bpy.props.FloatProperty(
        name="Radius Min",
        description="Inner radius of the sampling shell (shell sampler)",
        default=0.4,
        min=0.0,
        update=on_tunable_change,
    )
    radius_max: bpy.props.FloatProperty(
        name="Radius Max",
        description="Outer radius of the sampling shell (shell sampler)",
        default=0.6,
        min=0.0,
        update=on_tunable_change,
    )
    elevation_min: bpy.props.FloatProperty(
        name="Elevation Min (deg)",
        description="Lowest angle above/below horizontal the camera may be sampled at (shell sampler)",
        default=-90.0,
        update=on_tunable_change,
    )
    elevation_max: bpy.props.FloatProperty(
        name="Elevation Max (deg)",
        description="Highest angle above/below horizontal the camera may be sampled at (shell sampler)",
        default=90.0,
        update=on_tunable_change,
    )
    azimuth_min: bpy.props.FloatProperty(
        name="Azimuth Min (deg)",
        description="Start of the horizontal angular range the camera may be sampled in (shell sampler)",
        default=-180.0,
        update=on_tunable_change,
    )
    azimuth_max: bpy.props.FloatProperty(
        name="Azimuth Max (deg)",
        description="End of the horizontal angular range the camera may be sampled in (shell sampler)",
        default=180.0,
        update=on_tunable_change,
    )

    # shared
    inplane_rot_min: bpy.props.FloatProperty(
        name="Inplane Rotation Min (deg)",
        description="Minimum random roll (rotation around the camera's own view axis)",
        default=-30.0,
        update=on_tunable_change,
    )
    inplane_rot_max: bpy.props.FloatProperty(
        name="Inplane Rotation Max (deg)",
        description="Maximum random roll (rotation around the camera's own view axis)",
        default=30.0,
        update=on_tunable_change,
    )

    def draw_buttons(self, context, layout):
        layout.prop(self, "sampler")
        layout.prop(self, "number_of_views")

        layout.prop(self, "use_poi_override")
        if self.use_poi_override:
            layout.prop(self, "point_of_interest")

        if self.sampler == "volume_sampler":
            row = layout.row(align=True)
            row.prop(self, "distance_range_min")
            row.prop(self, "distance_range_max")
        else:
            row = layout.row(align=True)
            row.prop(self, "radius_min")
            row.prop(self, "radius_max")
            row = layout.row(align=True)
            row.prop(self, "elevation_min")
            row.prop(self, "elevation_max")
            row = layout.row(align=True)
            row.prop(self, "azimuth_min")
            row.prop(self, "azimuth_max")

        row = layout.row(align=True)
        row.prop(self, "inplane_rot_min")
        row.prop(self, "inplane_rot_max")

    def to_spec_dict(self) -> dict:
        params = {
            "inplane_rot_min": self.inplane_rot_min,
            "inplane_rot_max": self.inplane_rot_max,
        }
        if self.sampler == "volume_sampler":
            # volume_sampler does `min_distance, max_distance = distance_range`
            # - min first, then max.
            params["distance_range"] = [
                self.distance_range_min,
                self.distance_range_max,
            ]
            if self.use_poi_override:
                params["point_of_interst"] = list(self.point_of_interest)
        else:
            params["radius_min"] = self.radius_min
            params["radius_max"] = self.radius_max
            params["elevation_min"] = self.elevation_min
            params["elevation_max"] = self.elevation_max
            params["azimuth_min"] = self.azimuth_min
            params["azimuth_max"] = self.azimuth_max
            if self.use_poi_override:
                params["center"] = list(self.point_of_interest)

        return {
            "sampler": self.sampler,
            "number_of_views": self.number_of_views,
            "params": params,
        }


CLASSES = (IllusionCameraRandomizerNode,)
