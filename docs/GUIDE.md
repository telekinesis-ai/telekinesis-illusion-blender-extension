# Illusion Randomizer Tree — Guide

Usage reference, node behaviour, troubleshooting and build details for the
Blender extension. For the engine itself see
[Telekinesis Agentic OS: Illusion](https://docs.telekinesis.ai/data-engine/synthetic-datasets/overview.html)
and illusion's own `docs/GUIDE.md`.

- [Assets](#assets)
- [First-time setup](#first-time-setup)
- [Usage](#usage)
- [Seeing what will be rendered](#seeing-what-will-be-rendered)
- [Sampling visualizations](#sampling-visualizations)
- [Which button applies which setting](#which-button-applies-which-setting)
- [When a scene doesn't match the node graph](#when-a-scene-doesnt-match-the-node-graph)
- [Known limitations](#known-limitations)
- [Running a generated spec](#running-a-generated-spec)
- [Building from source](#building-from-source)
- [Repository layout](#repository-layout)
- [How the preview works](#how-the-preview-works)

## Assets

The extension ships no 3D assets, and this is the main thing to know before
concluding something is broken:

- **Material Randomizer's type list will be empty.** It is populated by scanning
  `<asset directory>/materials` on disk, so with no assets there is nothing to
  list and the node falls back to a free-text field.
- **`Load Assets` will fail** on any spec whose `models[].path` points at a
  `.glb` you don't have.

So you need an illusion checkout's `assets/` directory — or any directory laid
out the same way, with `models/`, `hdris/` and `materials/` populated — and the
add-on pointed at it.

## First-time setup

The add-on needs to know where the asset directory lives so model and HDRI
paths in specs resolve. Set it in
`Edit > Preferences > Add-ons > Illusion Randomizer Tree`, or from Blender's
Python Console:

```python
import bpy
prefs = bpy.context.preferences.addons['bl_ext.user_default.telekinesis_illusion_randomizer'].preferences
prefs.asset_directory = r'C:\path\to\illusion\assets'
bpy.ops.wm.save_userpref()
```

> Blender's Preferences UI lists *online* extensions under Official/Community/
> Testing. This one installs into the local **User Default** repository, so it
> won't appear under any of those tabs — the console snippet above is the
> reliable route.

## Usage

1. Switch an editor to **Illusion Randomizer Tree** (it's listed directly in the
   editor-type menu, under General) and click **New**.
2. Press `N` → **Illusion** tab for the tool panel.
3. **Load YAML** an existing spec (e.g.
   `illusion/configs/*.yaml`) or build a tree with
   `Shift+A`. **Arrange Nodes** lays it out in execution-order columns.
4. **Load Assets** — imports the models and builds the `Context`. Slow; only
   needed when assets change.
5. **Change Scene** — re-randomizes everything: which objects are visible,
   their materials, the background and the camera. This is what a real
   generation run does per image.
6. **Preview Scene** — re-samples object poses and camera views only, keeping
   the materials, background and object selection from the last **Change
   Scene**. Use it to iterate on layout and framing without the scene changing
   underneath you. Or tick **Live Preview** and just drag fields — live updates
   use this same geometry-only path.
7. **Save YAML** when you're happy.

## Seeing what will be rendered

- **Camera View** / **Free View** buttons (or `Numpad 0`) toggle the camera framing.
- Set viewport shading to **Rendered** for real materials + HDRI lighting.
- Camera poses are keyframed one per view — use the **View** slider (or scrub the
  timeline) to step through them. The frame range is clamped to your view count.

## Sampling visualizations

**Show Sampling Volumes** draws wireframe overlays for the **selected** node
(everything, if nothing is selected):

| Node selected | Overlay |
|---|---|
| Camera Pose Randomizer | Sampling volume (or shell radii), point of interest, one frustum per sampled view |
| Pose Randomizer | Grid cell markers, or the drop-region box for the `random` strategy |
| Asset | Bounding box of each visible instance of that asset |
| Instance Count Randomizer | The instances its targets actually produced |
| Material Randomizer | The objects it will re-material |
| Physics Simulator | Only the objects with *Active In Simulation* ticked |

Background Randomizer and Worker/Output have no spatial extent, so they
deliberately draw nothing.

## Which button applies which setting

**Preview Scene** re-runs only the pose and camera stages, so these settings
have no visible effect until you click **Change Scene**:

| Setting | Applied by |
|---|---|
| Pose Randomizer (any field), Camera Pose Randomizer | Preview Scene |
| Instance Count Randomizer (min/max per role) | Change Scene |
| Material Randomizer, Background Randomizer | Change Scene |
| Physics Simulator | either (it runs after randomizing, in both modes) |
| Asset — model path, per-asset counts, role, preprocess | Load Assets |
| Asset — **Scale** | Preview Scene (rescaled in place, no reload needed) |

When you edit a deferred setting, **Change Scene** turns red and the panel says
what's waiting on it — so a setting that hasn't taken effect yet is visibly
deferred rather than apparently broken. Live Preview drives the Preview Scene
path, so it won't show those either.

## When a scene doesn't match the node graph

Set **Log Level** to **Info** and open **Window → Toggle System Console** (the
system console, not Blender's Python console — the illusion package logs to
stdout/stderr, which only lands somewhere readable when that window is open).

At Info you get the randomizers' own account of every placement: which cell an
object went to, `Collision detected after drop, retrying!`, and
`Giving up on <name>, hiding...`. That last one matters — an object that can't
be placed without collision is **reverted to its previous pose and hidden**, so
a too-dense grid or too-tight drop region shows up as objects that ignore your
settings rather than as an error.

Each randomize also prints the pose-sampling config the worker actually holds,
prefixed `[illusion]`. If a value you changed isn't in that line, the problem
is the node → spec plumbing; if it is there but the scene ignores it, the
problem is downstream — most often **physics settling, which re-orients
everything it simulates and will wash out a sampled Z rotation**. Untick the
Physics Simulator node to see the sampled poses on their own.

## Known limitations

Worth reading before you spend time tuning — these are properties of the
current `BinPickingWorker`, not bugs in the extension.

- **`Load Assets` wipes the entire .blend file.** BlenderProc's reset
  (`Initializer.remove_all_data`) clears *every* object/mesh/material in the
  file and deletes all scenes except one named `Scene`. It can't be scoped to a
  single scene. **Use a dedicated/empty .blend file.**
- **Some fields don't affect generated output yet.** `BinPickingWorker` derives
  these itself rather than reading them from the spec:
  - *Instance Count Randomizer* nodes entirely (it uses Worker/Output's
    Min/Max Visible Models)
  - *Target Objects* on all randomizers (it derives targets from each Asset's
    **Role**)
  - *Material Randomizer* (hardcoded metal/plastic by role)
  - *Background Randomizer* (hardcoded `indoor/industrial` + `indoor/misc`)

  They round-trip through YAML correctly and their overlays show what they
  *would* affect; the worker just ignores them for now.
- **The links are currently decorative.** Verified: deleting every link produces
  a byte-identical spec. They only order Asset nodes in the exported list and
  guard against cycles — execution order is hardcoded in the worker. Making
  topology genuinely drive execution is the planned next step.
- **Close Blender before reinstalling.** Blender writes preferences from memory
  on exit, so a session open across a reinstall can silently disable the add-on.
  Recovery:
  ```python
  import bpy, addon_utils
  addon_utils.enable('bl_ext.user_default.telekinesis_illusion_randomizer', default_set=True, persistent=True)
  bpy.ops.wm.save_userpref()
  ```

## Running a generated spec

From the illusion checkout, in its own env (not Blender):

```bash
conda activate telekinesis-illusion
python examples/generate_synthetic_data_with_bin_picking_worker.py --spec-file /path/to/spec.yaml --no-preview
```

Three traps in the worker's arithmetic that make a misconfigured run look like a
silent no-op:

- **Shard Size must be ≥ 2** — the generation loop runs `while n < num_images-1`,
  so a shard of 1 renders zero images.
- **Num Images must be ≥ Shard Size** — shard count is `int(num_images / shard_size)`,
  so 5 images with shard size 100 gives **0 shards**.
- Net output is roughly `num_shards × (shard_size - 1)` images.
- Also set **Base Output Directory** to a real path — some checked-in specs
  carry an absolute path from whichever machine last edited them.

## Building from source

Building requires an `illusion` checkout, because the bundled wheels are built
from it — and specifically a *patched* one. The extension depends on these
changes:

| Change | Why |
|---|---|
| `BlenderProc/.../api/{loader,writer,object,constructor}/__init__.py` — lazy per-function imports | Eager imports pulled in `sklearn`/`scipy` builds incompatible with the NumPy that Blender ships |
| `BlenderProc/.../utility/Initializer.py` — `bproc_preserve` opt-out in `remove_all_data` | Its reset walks *every* `bpy.data` collection, including `node_groups` — it would delete the add-on's own node tree mid-load |
| Deferred `tkinter` import in `dataset/dataset_generator.py` | `tkinter` isn't available in Blender's bundled Python and can't be pip-installed |
| Deferred `pycocotools`/dataset imports in `bin_picking_worker.py` | Only needed for shard merging, not for preview |
| `get_context()` / `get_randomizer()` on `BinPickingWorker` | Lets the add-on re-randomize without reaching into private attributes |

It will not build or run correctly against an unmodified checkout.

```bash
# 1. build the bundled wheels from the illusion checkout (expected at ../illusion)
conda activate telekinesis-illusion
python build_wheels.py                # or: ILLUSION_REPO=/path/to/illusion python build_wheels.py

# 2. package + install into Blender (close Blender first!)
./dev_reinstall.sh                    # Windows: "C:\Program Files\Git\bin\bash.exe" dev_reinstall.sh
```

`dev_reinstall.sh` builds the zip into `dist/`, reinstalls it, and checks the
add-on registered. Set `BLENDER=/path/to/blender.exe` if Blender isn't at the
default Windows location. Note its verify step only proves *registration* — it
passes even when the bundled wheel closure is broken, since nothing imports
`blenderproc` until `Load Assets`. The real smoke test is a `Load Assets` run.

To package without installing:

```bash
blender --command extension build --source-dir illusion_randomizer --output-dir dist
blender --command extension validate dist/telekinesis_illusion_randomizer-0.1.0.zip
```

## Repository layout

```
build_wheels.py           builds the bundled wheels from the illusion checkout
dev_reinstall.sh          build + reinstall + verify
illusion_randomizer/
  blender_manifest.toml   extension manifest (wheel list is generated)
  LICENSE                 GPL-3.0 text, packaged into the zip
  __init__.py             registration + Add menu
  node_tree.py            the custom NodeTree + tree-level toggles
  sockets.py              flow socket
  nodes/                  one module per node type
  spec_io.py              tree <-> YAML spec
  preview.py              Load Assets / Preview Scene / Change Scene (in-process)
  live.py                 debounced live re-randomize
  log.py                  routes illusion's loguru output to the console
  stages.py               which randomize mode applies which node's settings
  refs.py                 live-vs-freed datablock checks
  viz.py                  sampling-volume overlays
  layout.py               auto layout + linking
  targets.py              target multi-select operator
  names.py                target-name helpers
  panel.py                sidebar UI
  preferences.py          asset directory + API settings
  wheels/                 generated, gitignored
```

## How the preview works

The add-on runs illusion **in-process** inside Blender rather than shelling out
to `blenderproc run/debug`. `bproc.init()` turns out to be plain `bpy` calls
(scene reset, render settings), not subprocess bootstrapping, so it works inside
a live session — which is what makes live tuning possible. `Load Assets` builds
a real `BinPickingWorker`, so the preview uses the exact code path the
production pipeline does.
