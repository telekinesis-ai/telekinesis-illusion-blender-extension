"""Add-on preferences."""

import bpy


class IllusionRandomizerPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    asset_directory: bpy.props.StringProperty(
        name="Asset Directory",
        description=(
            "Directory holding the 'models', 'hdris' and 'materials' folders. Used "
            "when a spec does not set metadata.asset_directory itself"
        ),
        subtype="DIR_PATH",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "asset_directory")


CLASSES = (IllusionRandomizerPreferences,)
