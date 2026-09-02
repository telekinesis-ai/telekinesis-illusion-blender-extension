"""Tidy tree layout + flow-link wiring.

Without this, an imported spec produces a row of disconnected nodes with no
visual indication of what feeds what. Nodes are laid out in columns by kind
and chained together in the order the runtime actually executes them, so the
tree reads left-to-right as the pipeline it represents.

The chain is deliberately linear (one link per socket pair) because that
mirrors Randomizer.add_randomizer(), which also builds a simple chain - and
because a custom NodeSocket can't accept multiple incoming links, so
fan-in from several Asset nodes isn't expressible anyway.
"""

import bpy

from . import refs

# Column order == execution order. Assets aren't RandomizerNodes but sit at
# the head of the chain since everything downstream refers to them.
KIND_ORDER = (
    "IllusionAssetNode",
    "IllusionInstanceRandomizerNode",
    "IllusionPoseRandomizerNode",
    "IllusionMaterialRandomizerNode",
    "IllusionBackgroundRandomizerNode",
    "IllusionCameraRandomizerNode",
    "IllusionPhysicsNode",
    "IllusionWorkerOutputNode",
)

# Must exceed IllusionRandomizerNodeBase.bl_width_default or columns overlap.
COLUMN_WIDTH = 470
ROW_HEIGHT = 460


def _ordered_nodes(tree):
    """Nodes grouped by kind in KIND_ORDER, preserving existing order within
    a kind. Unknown//extra node types are appended so nothing gets stranded
    off-screen."""
    by_kind = {kind: [] for kind in KIND_ORDER}
    extras = []
    for node in tree.nodes:
        if node.bl_idname in by_kind:
            by_kind[node.bl_idname].append(node)
        else:
            extras.append(node)
    return by_kind, extras


def arrange_tree(tree, rewire: bool = True) -> None:
    """Position nodes in columns by kind and (optionally) rebuild the flow
    links as a single execution-order chain."""
    by_kind, extras = _ordered_nodes(tree)

    column = 0
    chain = []
    for kind in KIND_ORDER:
        nodes = by_kind[kind]
        if not nodes:
            continue
        for row, node in enumerate(nodes):
            node.location = (column * COLUMN_WIDTH, -row * ROW_HEIGHT)
            # bl_width_default only applies to newly created nodes - existing
            # ones keep the width stored in the .blend, so reset it here too
            # (this is what makes Arrange Nodes fix an older, narrower tree).
            node.width = node.bl_width_default
            # Re-assert colours so trees built before a colour change (or by
            # an older version) pick them up too.
            if hasattr(node, "node_color"):
                node.use_custom_color = True
                node.color = node.node_color
            chain.append(node)
        column += 1

    for row, node in enumerate(extras):
        node.location = (column * COLUMN_WIDTH, -row * ROW_HEIGHT)

    if not rewire:
        return

    for link in list(tree.links):
        tree.links.remove(link)
    for upstream, downstream in zip(chain, chain[1:]):
        out_socket = upstream.outputs.get("Out")
        in_socket = downstream.inputs.get("In")
        if out_socket is not None and in_socket is not None:
            tree.links.new(out_socket, in_socket)


class ILLUSION_OT_arrange_nodes(bpy.types.Operator):
    bl_idname = "illusion.randomizer_arrange_nodes"
    bl_label = "Arrange Nodes"
    bl_description = (
        "Lay out the tree in execution-order columns and reconnect every node into a "
        "single flow chain. Rebuilds all links - it does not change any field values"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return refs.edit_tree(context) is not None

    def execute(self, context):
        tree = refs.require_edit_tree(self, context)
        if tree is None:
            return {"CANCELLED"}
        arrange_tree(tree)
        self.report({"INFO"}, f"Arranged {len(tree.nodes)} nodes")
        return {"FINISHED"}


CLASSES = (ILLUSION_OT_arrange_nodes,)
