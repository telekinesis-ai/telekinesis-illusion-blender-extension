"""Helpers for the comma-separated target-object name lists.

The stored format stays a plain comma-separated string (that's what the YAML
spec uses, and it keeps existing trees/specs loading unchanged) - the UI just
presents it as a set of toggles instead of a text field. See
nodes/_base.py's draw_target_selector and targets.py.
"""


def parse_names(value: str) -> list:
    return [part.strip() for part in value.split(",") if part.strip()]


def join_names(names) -> str:
    return ", ".join(names)


def asset_names(tree) -> list:
    """Object Names of every Asset node in the tree, in node order, skipping
    ones that haven't been named yet."""
    return [
        node.object_name
        for node in tree.nodes
        if node.bl_idname == "IllusionAssetNode" and node.object_name
    ]


def asset_names_for_role(tree, role: str) -> list:
    """Object Names of the Asset nodes with this role - the derived target
    list for the role-scoped Instance/Material randomizers.

    Mirrors BinPickingWorker._model_supercatgory_map[role] (and
    _distractor_names for 'distractor'), which is what those randomizers are
    actually constructed with, so the node graph shows the same targets the
    worker will use."""
    return [
        node.object_name
        for node in tree.nodes
        if node.bl_idname == "IllusionAssetNode"
        and node.object_name
        and node.role == role
    ]
