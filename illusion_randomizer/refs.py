"""Telling a live Blender datablock from a freed one.

Blender can free an ID datablock while Python still holds a wrapper for it -
BlenderProc's reset wipes nearly all of bpy.data, and an editor's stored
pointers aren't revalidated until that editor redraws. The resulting wrapper is
NOT None: it's a perfectly truthy object that raises

    ReferenceError: StructRNA of type IllusionRandomizerTree has been removed

on the first attribute access. So `if x is None` does not catch it, and the
only way to tell the two apart is to touch an attribute and see what happens.

Every operator that reads `context.space_data.edit_tree` is exposed to this, so
they all go through edit_tree() below rather than reading the attribute
directly.

Dependency-free apart from the implicit bpy objects passed in, so preview.py,
panel.py, viz.py, upload.py and layout.py can all use it without the
circular-import problem live.py's docstring describes.
"""


def is_valid(datablock) -> bool:
    """Whether `datablock` is a usable reference - not None, not freed."""
    if datablock is None:
        return False
    try:
        # Any attribute would do; `name` exists on every ID type.
        datablock.name
    except ReferenceError:
        return False
    return True


def valid_or_none(datablock):
    """`datablock` if it's still alive, else None.

    Lets callers keep a plain `if x is None` check at the call site while
    actually being safe against freed references."""
    return datablock if is_valid(datablock) else None


def edit_tree(context):
    """The node tree the editor is showing, or None if there isn't a usable one.

    The one way operators should reach for the current tree: it collapses
    "no node editor", "no tree open" and "the tree pointer is stale" into a
    single None, so a poll() is just `refs.edit_tree(context) is not None`."""
    return valid_or_none(getattr(context.space_data, "edit_tree", None))


def require_edit_tree(operator, context):
    """edit_tree() for use in execute(), reporting to the user when it's gone.

    A passing poll() is not a guarantee for execute(): the two are separate
    events, and for the file-select operators there's a whole trip through a
    file browser in between. Returning None here means the operator should
    return {"CANCELLED"} - the message has already been shown."""
    tree = edit_tree(context)
    if tree is None:
        operator.report({"ERROR"}, "No node tree open in this editor")
    return tree
