<div align="center">
  <p>
    <a href="https://gitlab.com/telekinesis/blender-extension">
      <img width="100%" src="media/images/telekinesis_banner.png" />
    </a>
  </p>

  <p align="center">
    <a href="https://docs.telekinesis.ai">
      <img src="https://img.shields.io/badge/docs-telekinesis.ai-blue" />
    </a>
    <a href="LICENSE">
      <img src="https://img.shields.io/badge/license-GPL--3.0--or--later-green" />
    </a>
    <a href="https://www.blender.org/download/releases/4-2/">
      <img src="https://img.shields.io/badge/Blender-4.2%20LTS-orange" />
    </a>
    <a href="#requirements">
      <img src="https://img.shields.io/badge/platform-Windows%20x64-lightgrey" />
    </a>
  </p>

  <p>
    <a href="https://docs.telekinesis.ai/data-engine/synthetic-data-generation/overview.html">Docs</a>
    &nbsp;&bull;&nbsp;
    <a href="docs/GUIDE.md">Guide</a>
    &nbsp;&bull;&nbsp;
    <a href="https://github.com/telekinesis-ai/telekinesis-illusion-blender-extension">GitHub</a>
    &nbsp;&bull;&nbsp;
    <a href="https://discord.gg/S5v8bYAnc6">Discord</a>
    &nbsp;&bull;&nbsp;
    <a href="https://www.linkedin.com/company/telekinesis-ai/">LinkedIn</a>
    &nbsp;&bull;&nbsp;
    <a href="https://x.com/telekinesis_ai">X</a>
    &nbsp;&bull;&nbsp;
    <a href="https://telekinesis.ai/">Website</a>
  </p>
</div>

# `telekinesis-illusion` Randomizer Tree Blender Extension

A Blender node-graph editor for building and tuning
[`telekinesis-illusion`](https://gitlab.com/telekinesis/illusion) synthetic-data
specs, with a live in-Blender preview.

Open source under [GPL-3.0-or-later](LICENSE).

Full documentation: [Telekinesis Agentic OS: Illusion](https://docs.telekinesis.ai/data-engine/synthetic-datasets/overview.html).

## Requirements

**Windows x64 and Blender 4.2.23 LTS only.** Please install Blender 4.2.23 LTS from the [offical website](https://www.blender.org/download/releases/4-2/). Support for Linux and Mac OS comming soon!

You also need an `telekinesis-illusion` checkout with its assets on disk - the extension
ships no 3D assets, and without them the Material Randomizer's type list is
empty and **Load Assets** fails on missing model paths. See
[docs/GUIDE.md](docs/GUIDE.md#assets).

## Installation

Download `telekinesis_illusion_randomizer-<version>.zip` from the releases page,
then either drag it onto an open Blender window or use
**Edit > Preferences > Add-ons > ▼ > Install from Disk…**

Point the add-on at your illusion checkout's asset directory so model and HDRI
paths resolve. You can set it from Blender in **Edit > Preferences > Add-ons > ▼ Illusion Randomizer Tree > Asset Directory** or with `bpy`:

```python
import bpy
prefs = bpy.context.preferences.addons['bl_ext.user_default.telekinesis_illusion_randomizer'].preferences
prefs.asset_directory = r'C:\path\to\illusion\assets'
bpy.ops.wm.save_userpref()
```

## Updating

1. Close Blender.
2. Download the new `telekinesis_illusion_randomizer-<version>.zip`.
3. Drag it onto a Blender window, or use **Edit > Preferences > Add-ons > ▼ > Install from Disk…**
   Do **not** uninstall the old version first — installing over it replaces it.
4. Restart Blender. Required whenever a release changes the bundled wheels; without it Blender keeps
   the previously imported `telekinesis` and `blenderproc` modules for the rest of the session.

Your Asset Directory is kept across updates. The installed version is shown in
**Edit > Preferences > Add-ons > Illusion Randomizer Tree**.

## Quickstart

1. Switch an editor to **Illusion Randomizer Tree** (listed in the editor-type
   menu under General) and click **New**.
2. Press `N` → **Illusion** tab for the tool panel.
3. **Load YAML** an existing spec (e.g.
   `illusion/configs/*.yaml`), or build a tree with
   `Shift+A` and **Arrange Nodes**.
4. **Load Assets** — imports the models and builds the `Context`. Slow; only
   needed when assets change.
5. **Change Scene** to re-randomize everything, or **Preview Scene** to
   re-sample poses and camera only. Tick **Live Preview** and drag fields.
6. **Save YAML** when you're happy.

> **`Load Assets` wipes the entire .blend file** — BlenderProc's reset is global,
> not per-scene. Use a dedicated/empty .blend.

The full walkthrough, the sampling-volume overlays, which button applies which
setting, and troubleshooting are all in [docs/GUIDE.md](docs/GUIDE.md).

## Building from source

Requires a *patched* `illusion` checkout — the bundled wheels are built from it.
See [docs/GUIDE.md](docs/GUIDE.md#building-from-source).

```bash
conda activate telekinesis-illusion
python build_wheels.py
"C:\Program Files\Git\bin\bash.exe" dev_reinstall.sh
```

`build_wheels.py` expects the `illusion` checkout to sit next to this repo, at
`../illusion`. If yours lives elsewhere, point `ILLUSION_REPO` at its root:

```bash
ILLUSION_REPO=/path/to/illusion python build_wheels.py
```

Bump `version` in `illusion_randomizer/blender_manifest.toml` for every release. Nothing in the
install path enforces it, but it names the built zip and it is the only way a user can tell which
build they have.

## Documentation

Find the documentation for Illusion at
[Telekinesis Agentic OS: Illusion](https://docs.telekinesis.ai/). For this
extension's usage reference, node-by-node behaviour, known limitations and
troubleshooting, see [docs/GUIDE.md](docs/GUIDE.md).

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).

This extension bundles a modified fork of
[BlenderProc](https://github.com/DLR-RM/BlenderProc) (GPL-3.0) and imports `bpy`
(GPL-2.0-or-later). The bundled wheels are pure-Python, so corresponding
source for every GPL component is included in the zip.

Bundled third-party wheels and their terms:
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Citation

```bibtex
@software{telekinesis_illusion_randomizer,
  author = {Telekinesis GmbH},
  title  = {Telekinesis-Illusion Randomizer Tree: A Blender Node Editor for Synthetic-Data Generation},
  year   = {2026},
  url    = {https://gitlab.com/telekinesis/blender-extension},
  note   = {GPL-3.0-or-later}
}
```
