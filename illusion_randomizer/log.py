"""Routing the illusion package's loguru output into Blender's console.

The randomizer nodes log a lot of useful detail through loguru - which grid
cell an object landed in, "Collision detected after drop, retrying!", "Giving
up on <object>, hiding..." - and that's usually the only way to tell why a
scene doesn't look the way the node graph says it should.

Two things get in the way by default:

  * loguru's default sink writes to stderr, which on Windows only goes
    somewhere visible if the system console is open (Window > Toggle System
    Console). Blender's own Python console is a different thing and won't show
    it.
  * loguru's default level is DEBUG, so leaving it alone floods the console
    with per-object placement chatter on every preview.

So this module installs a single sink at a level the user picks on the tree,
tagged so illusion's lines are distinguishable from BlenderProc's own output.
Configured from Load Assets and whenever the level changes.

loguru is imported lazily: it arrives with the telekinesis_illusion wheel, and
this module is imported at add-on registration time, before we know the wheel
is installed.
"""

PREFIX = "[illusion]"

# loguru's own format, minus the timestamp (Blender's console is not a log
# file) and with a marker so these lines are easy to spot among BlenderProc's.
_FORMAT = (
    PREFIX + " <level>{level: <8}</level> | {name}:{line} - <level>{message}</level>"
)


def configure(level: str) -> None:
    """Route illusion's loguru output to stdout at `level`.

    Clears loguru's handlers first and installs exactly one of our own. The
    clear matters for both correctness and for the level control working at
    all: loguru ships an stderr handler at DEBUG that can't be filtered, so
    leaving it in place would print every line twice and leak DEBUG chatter no
    matter what level was picked. Removing everything also means repeated Load
    Assets clicks can't stack up duplicate handlers.

    SyntheticDataGenerator.generate() calls logger.remove() itself for the same
    reason, so wiping the registry is the established convention here rather
    than a liberty this module takes.

    Silently does nothing if loguru isn't importable - logging is a diagnostic
    aid and must never be the reason Load Assets fails."""
    try:
        from loguru import logger
    except ImportError:
        return

    import sys

    logger.remove()

    if level == "OFF":
        return

    logger.add(sys.stdout, level=level, format=_FORMAT, colorize=False)


def on_log_level_change(self, context) -> None:
    """Property update callback for the tree's log_level."""
    configure(self.log_level)


def info(message: str) -> None:
    """Print one of the extension's own diagnostics.

    Deliberately a plain print rather than loguru: these are the extension
    talking, not the illusion package, and they should show up even when the
    user has illusion's own logging turned off."""
    print(f"{PREFIX} {message}")
