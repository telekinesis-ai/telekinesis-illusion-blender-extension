#!/usr/bin/env bash
# Rebuild the extension zip and reinstall it into Blender.
#
# Close Blender first: it saves preferences from memory on exit, so a session
# left open across a remove/install writes back a stale snapshot and silently
# leaves the add-on disabled.
#
# Usage:
#   ./dev_reinstall.sh                    # build + reinstall
#   ./dev_reinstall.sh path/to/check.py   # ...then run a script inside Blender
#   BLENDER=/path/to/blender.exe ./dev_reinstall.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLENDER="${BLENDER:-/c/Program Files/Blender Foundation/Blender 4.2/blender.exe}"
EXT_ID="telekinesis_illusion_randomizer"
SRC_DIR="$HERE/illusion_randomizer"
DIST_DIR="$HERE/dist"

# Read the version rather than hardcoding it: `extension build` names the zip
# from the manifest, so a hardcoded copy silently goes stale on a version bump
# and the script then removes/installs a path that no longer exists.
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$SRC_DIR/blender_manifest.toml")"
if [ -z "$VERSION" ]; then
  echo "Could not read version from $SRC_DIR/blender_manifest.toml" >&2
  exit 1
fi
ZIP="$DIST_DIR/${EXT_ID}-${VERSION}.zip"

if [ ! -x "$BLENDER" ]; then
  echo "Blender not found at: $BLENDER" >&2
  echo "Set BLENDER=/path/to/blender.exe (4.2+ required for the extensions API)." >&2
  exit 1
fi

if tasklist //FI "IMAGENAME eq blender.exe" 2>/dev/null | grep -qi "blender.exe"; then
  echo "WARNING: Blender is running - close it, or it may clobber preferences" >&2
  echo "         on exit and leave the add-on disabled." >&2
fi

mkdir -p "$DIST_DIR"
rm -f "$ZIP"

echo "--- build ---"
"$BLENDER" --command extension build --source-dir "$SRC_DIR" --output-dir "$DIST_DIR" 2>&1 | tail -2

echo "--- remove old ---"
"$BLENDER" --command extension remove "$EXT_ID" 2>&1 | tail -1 || true

echo "--- install ---"
"$BLENDER" --command extension install-file --repo user_default --enable "$ZIP" 2>&1 | tail -1

echo "--- verify ---"
"$BLENDER" --background --python-expr "
import bpy
mod = 'bl_ext.user_default.$EXT_ID'
print('addon loaded:', mod in bpy.context.preferences.addons.keys())
" 2>&1 | grep "addon loaded"

if [ $# -ge 1 ]; then
  echo "--- run $1 ---"
  "$BLENDER" --background --python "$1"
fi
