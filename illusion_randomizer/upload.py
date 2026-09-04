"""Load/Save Spec operators.

Load populates the current tree from an existing bin_picking YAML spec (e.g.
one of configs/*.yaml) - clears any existing nodes
first, since spec_io.spec_to_tree() only knows how to add nodes, not merge.

Save is the handoff step once you're happy with a preview: it writes the
finalized YAML to disk, for local testing against the existing headless
pipeline."""

import os

import bpy
import yaml

from . import refs, spec_io


class ILLUSION_OT_load_yaml(bpy.types.Operator):
    bl_idname = "illusion.randomizer_load_yaml"
    bl_label = "Load YAML"
    bl_description = "Replace the current tree's nodes with those from an existing bin_picking spec YAML"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.yaml;*.yml", options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return refs.edit_tree(context) is not None

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        tree = refs.require_edit_tree(self, context)
        if tree is None:
            return {"CANCELLED"}

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                spec = yaml.safe_load(f)
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to read {self.filepath}: {exc}")
            return {"CANCELLED"}

        for node in list(tree.nodes):
            tree.nodes.remove(node)

        # A relative metadata.asset_directory (the shipped example uses
        # '../assets') is only meaningful next to the file it came from, so
        # remember that anchor - see assets.effective_asset_dir.
        tree.spec_directory = os.path.dirname(self.filepath)

        try:
            spec_io.spec_to_tree(spec, tree)
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to import spec: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Loaded {len(tree.nodes)} nodes from {self.filepath}")
        return {"FINISHED"}


class ILLUSION_OT_save_yaml(bpy.types.Operator):
    bl_idname = "illusion.randomizer_save_yaml"
    bl_label = "Save YAML"
    bl_description = "Write the finalized spec to disk"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    @classmethod
    def poll(cls, context):
        return refs.edit_tree(context) is not None

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        tree = refs.require_edit_tree(self, context)
        if tree is None:
            return {"CANCELLED"}
        try:
            spec = spec_io.tree_to_spec(tree)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        with open(self.filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(spec, f, sort_keys=False)

        # The spec now lives here, so this is what a relative Asset Directory
        # is relative to.
        tree.spec_directory = os.path.dirname(self.filepath)

        self.report({"INFO"}, f"Saved spec to {self.filepath}")
        return {"FINISHED"}


CLASSES = (ILLUSION_OT_load_yaml, ILLUSION_OT_save_yaml)
