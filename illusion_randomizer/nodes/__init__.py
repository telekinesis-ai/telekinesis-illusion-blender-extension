"""Node type registry for the Illusion Randomizer tree.

Each module in this package defines one bpy.types.Node subclass mirroring a
RandomizerNode kind (or the Asset/worker-output nodes that aren't
RandomizerNodes but are still part of the spec). `CLASSES` here is the single
place __init__.py needs to import from to register everything; the Add menu
in the top-level __init__.py lists these bl_idnames directly.
"""

from . import asset
from . import instance_randomizer
from . import pose_randomizer
from . import material_randomizer
from . import background_randomizer
from . import camera_randomizer
from . import physics
from . import worker_output

MODULES = (
    asset,
    instance_randomizer,
    pose_randomizer,
    material_randomizer,
    background_randomizer,
    camera_randomizer,
    physics,
    worker_output,
)

CLASSES = tuple(cls for module in MODULES for cls in module.CLASSES)
