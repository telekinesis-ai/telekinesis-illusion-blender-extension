"""Physics simulator node - maps to the physics_simulator YAML block, applied
via bproc.object.simulate_physics_and_fix_final_poses (see
synthetic_data_generator.py)."""

import bpy

from ._base import IllusionRandomizerNodeBase
from ..live import on_tunable_change


class IllusionPhysicsNode(IllusionRandomizerNodeBase, bpy.types.Node):
    bl_idname = "IllusionPhysicsNode"
    bl_label = "Physics Simulator"
    bl_icon = "PHYSICS"
    node_color = (0.42, 0.28, 0.14)

    active: bpy.props.BoolProperty(
        name="Active",
        description="Drop parts and let Blender's rigid-body physics settle them before rendering",
        default=False,
        update=on_tunable_change,
    )
    min_simulation_time_range_min: bpy.props.FloatProperty(
        name="Min Sim Time Range Min",
        description="Lower bound for the randomly-picked minimum simulation duration (seconds, 24fps)",
        default=0.5,
        update=on_tunable_change,
    )
    min_simulation_time_range_max: bpy.props.FloatProperty(
        name="Min Sim Time Range Max",
        description="Upper bound for the randomly-picked minimum simulation duration (seconds, 24fps)",
        default=1.0,
        update=on_tunable_change,
    )
    max_simulation_time_range_min: bpy.props.FloatProperty(
        name="Max Sim Time Range Min",
        description="Lower bound for the randomly-picked maximum simulation duration (seconds, 24fps)",
        default=2.0,
        update=on_tunable_change,
    )
    max_simulation_time_range_max: bpy.props.FloatProperty(
        name="Max Sim Time Range Max",
        description="Upper bound for the randomly-picked maximum simulation duration (seconds, 24fps)",
        default=5.0,
        update=on_tunable_change,
    )
    check_object_interval: bpy.props.FloatProperty(
        name="Check Object Interval",
        description="How often (seconds) to check whether objects have stopped moving",
        default=0.5,
        update=on_tunable_change,
    )
    object_stopped_location_threshold: bpy.props.FloatProperty(
        name="Stopped Location Threshold",
        description="Max position change between checks for an object to count as having stopped",
        default=0.01,
        update=on_tunable_change,
    )
    object_stopped_rotation_threshold: bpy.props.FloatProperty(
        name="Stopped Rotation Threshold",
        description="Max rotation change (degrees) between checks for an object to count as having stopped",
        default=1.0,
        update=on_tunable_change,
    )
    substeps_per_frame: bpy.props.IntProperty(
        name="Substeps Per Frame",
        description="Physics solver substeps per simulated frame - higher is more accurate but slower",
        default=10,
        min=1,
        update=on_tunable_change,
    )
    solver_iters: bpy.props.IntProperty(
        name="Solver Iterations",
        description="Rigid-body constraint solver iterations per substep - higher is more accurate but slower",
        default=10,
        min=1,
        update=on_tunable_change,
    )
    verbose: bpy.props.BoolProperty(
        name="Verbose",
        description="Log detailed physics-simulation progress",
        default=False,
        update=on_tunable_change,
    )
    use_volume_com: bpy.props.BoolProperty(
        name="Use Volume CoM",
        description="Compute each object's center of mass from its volume instead of Blender's default",
        default=False,
        update=on_tunable_change,
    )
    clean_up_scene: bpy.props.BoolProperty(
        name="Clean Up Scene After",
        description="Remove physics simulation baked data from the scene once settling is done",
        default=False,
        update=on_tunable_change,
    )

    def draw_buttons(self, context, layout):
        layout.prop(self, "active")
        if not self.active:
            return
        row = layout.row(align=True)
        row.prop(self, "min_simulation_time_range_min")
        row.prop(self, "min_simulation_time_range_max")
        row = layout.row(align=True)
        row.prop(self, "max_simulation_time_range_min")
        row.prop(self, "max_simulation_time_range_max")
        layout.prop(self, "check_object_interval")
        layout.prop(self, "object_stopped_location_threshold")
        layout.prop(self, "object_stopped_rotation_threshold")
        layout.prop(self, "substeps_per_frame")
        layout.prop(self, "solver_iters")
        layout.prop(self, "verbose")
        layout.prop(self, "use_volume_com")
        layout.prop(self, "clean_up_scene")

    def to_spec_dict(self) -> dict:
        return {
            "active": self.active,
            "min_simulation_time_range": [
                self.min_simulation_time_range_min,
                self.min_simulation_time_range_max,
            ],
            "max_simulation_time_range": [
                self.max_simulation_time_range_min,
                self.max_simulation_time_range_max,
            ],
            "check_object_interval": self.check_object_interval,
            "object_stopped_location_threshold": self.object_stopped_location_threshold,
            "object_stopped_rotation_threshold": self.object_stopped_rotation_threshold,
            "substeps_per_frame": self.substeps_per_frame,
            "solver_iters": self.solver_iters,
            "verbose": self.verbose,
            "use_volume_com": self.use_volume_com,
            "clean_up_scene": self.clean_up_scene,
        }


CLASSES = (IllusionPhysicsNode,)
