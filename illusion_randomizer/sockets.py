"""Socket types for the Illusion Randomizer node tree.

Only one socket type exists: a flow socket expressing execution order between
randomizer nodes (mirrors `Randomizer.add_edge`/`_topological_order`). Node
parameters like `target_objects` are ordinary properties on the node, not
sockets, matching how the YAML spec already expresses them as plain name
strings.
"""

import bpy


class IllusionFlowSocket(bpy.types.NodeSocket):
    bl_idname = "IllusionFlowSocket"
    bl_label = "Execution Flow"

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    def draw_color(self, context, node):
        return (0.8, 0.8, 0.2, 1.0)


CLASSES = (IllusionFlowSocket,)
