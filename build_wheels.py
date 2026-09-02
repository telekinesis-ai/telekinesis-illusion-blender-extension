"""Builds the wheels blender_manifest.toml bundles into the extension, and
rewrites the manifest's `wheels` list to match what actually got built.

Run inside the project's `telekinesis-illusion` conda env:
    python blender_extension/build_wheels.py

`pip wheel --no-deps` below is load-bearing, not a shortcut - do not remove
it. Blender never runs pip: it just unpacks the wheels listed in the
manifest onto sys.path, so the dependency closure has to be resolved here,
against Blender's *embedded* interpreter rather than the build env. Letting
pip resolve it instead resolves against metadata that is actively wrong for
this target: the BlenderProc fork's setup.py pins numpy==2.4.2 (Blender 4.2
ships 1.24.3, and every compiled wheel here is built against the 1.x ABI),
and illusion's pyproject pulls bpy, fiftyone, ruff/pylint/debugpy and the
`pathlib` PyPI backport that shadows the stdlib module. PYPI_DEPS is
therefore the single source of truth for what ships.

blenderproc's api/* __init__.py files import every submodule in their
category eagerly (loader/writer/object/...) and the vendored fork still
does - the lists are trimmed relative to upstream, but they are plain
top-level imports, not lazy. So `import blenderproc` inside Blender runs
`from .api import object` -> api/object/__init__.py line 1 -> FaceSlicer ->
sklearn, and drags in loaders illusion never calls
(AMASS/Matterport3D/BOP/HDF5/...). PYPI_DEPS is the minimal set actually
reachable from that closure plus telekinesis.illusion's own imports - found
by running it inside Blender and reacting to each ModuleNotFoundError, not
by guessing from metadata, and deliberately *not* the full declared
requirement set (e.g. scikit-image declares `packaging`, but the reached
path - measure.find_contours/measure.label - never imports it). Re-run and
extend the same way when a BlenderProc/telekinesis-illusion upgrade changes
what's imported eagerly; `./dev_reinstall.sh` only checks that the add-on
registers, which passes even when this closure is broken.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXT_DIR = HERE / "illusion_randomizer"
OUT_DIR = EXT_DIR / "wheels"
MANIFEST_PATH = EXT_DIR / "blender_manifest.toml"

# This repo is a sibling of the illusion checkout it packages, so the default
# is ../illusion. Override with ILLUSION_REPO when it lives elsewhere.
ILLUSION_REPO = Path(
    os.environ.get("ILLUSION_REPO") or HERE.parent / "illusion"
).resolve()

# Vendored/modified fork, not the public PyPI "blenderproc" package - must be
# built from the illusion checkout's copy so the extension matches what the
# pipeline actually runs.
BLENDERPROC_SRC = ILLUSION_REPO / "BlenderProc"

PYPI_DEPS = [
    "loguru==0.7.3",
    "tqdm==4.67.1",
    "pyyaml==6.0.2",
    # BlenderUtility.py and MeshObjectUtility.py, reached via the
    # illusion-required MeshObjectUtility import, not via any of the now-lazy
    # api/* categories - genuinely unavoidable, unconditional top-level
    # imports in a module illusion's own Context imports directly.
    "imageio==2.34.1",
    "Pillow==10.3.0",
    "opencv-contrib-python==4.13.0.90",
    "trimesh==4.12.2",
    # Initializer.py -> RendererUtility, unconditionally imported by
    # bproc.init() itself - can't be lazy, it's the one function we need.
    "rich==13.7.1",
    "markdown-it-py",
    "pygments",
    "mdurl",
    # PostProcessingUtility.py, reached via Initializer -> RendererUtility ->
    # WriterUtility -> PostProcessingUtility - also unconditional/unavoidable.
    # Pinned to a version whose numpy floor (<1.28) fits the numpy Blender
    # 4.2 ships internally (1.24.3) - newer scipy releases require numpy
    # >=1.26 and fail with `ModuleNotFoundError: numpy.exceptions`.
    "scipy==1.11.4",
    # FaceSlicer.py's `from sklearn.cluster import MeanShift`, reached
    # eagerly via blenderproc/__init__.py -> `from .api import object` ->
    # api/object/__init__.py line 1 - and again via illusion's
    # dataset/converter.py (below). joblib/threadpoolctl are scikit-learn's
    # own runtime imports; neither ships in Blender's site-packages, so
    # without them the scikit-learn wheel here is unimportable and
    # `import blenderproc` dies before preview.py gets anywhere.
    "scikit-learn==1.5.0",
    "joblib==1.4.2",
    "threadpoolctl==3.6.0",
    "scikit-image==0.23.2",
    # WriterUtility.py, same unavoidable chain as scipy above.
    "h5py==3.11.0",
    # api/writer/__init__.py line 1 -> GifWriterUtility.py, eagerly imported
    # by blenderproc/__init__.py's `from .api import writer`. matplotlib is
    # held at BlenderProc's own setup.py pin; the rest are matplotlib's
    # unconditional runtime imports (six via python-dateutil). contourpy is
    # pinned because current releases floor numpy at >=1.25, above the
    # 1.24.3 Blender ships - the same trap documented for scipy above.
    "matplotlib==3.9.0",
    "contourpy==1.2.1",
    "cycler",
    "fonttools",
    "kiwisolver",
    "pyparsing",
    "python-dateutil",
    "six",
    "packaging",
    # api/writer/__init__.py line 2 -> BopWriterUtility.py's `import png`.
    # Same pin as both BlenderProc's DefaultConfig and illusion's pyproject.
    "pypng==0.20220715.0",
    # illusion's own coco_writer.py, unconditionally imported by
    # BinPickingWorker.__init__ (it always constructs a CocoWriter, even
    # though the preview path never calls .generate()). 0.23.2's numpy/scipy
    # floors (>=1.23 / >=1.9) fit what's already pinned above.
    "scikit-image==0.23.2",
    "networkx",
    "tifffile",
    "lazy-loader",
    # illusion's dataset/converter.py, which bin_picking_worker.py imports
    # unconditionally at module level (`from ...dataset.converter import
    # DatasetConverter`) - so preview.py's BinPickingWorker import pulls it
    # even though nothing here ever converts a dataset. Its matplotlib
    # dependency is gated behind `extra == "all"` and mask.py only needs
    # numpy, so --no-deps costs nothing extra here.
    "pycocotools==2.0.11",
    # SetupUtility.py, unconditionally imported by blenderproc/__init__.py.
    "requests==2.32.5",
    "charset_normalizer",
    "idna",
    "urllib3",
    "certifi",
    # loguru's sys_platform=='win32' extras, dropped by --no-deps above but
    # actually imported eagerly (win32_setctime unconditionally on module
    # load, colorama for terminal output) - Windows-only build target.
    "win32-setctime>=1.0.0",
    "colorama>=0.3.4",
]


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def rewrite_manifest_wheels_list() -> None:
    """Replaces only the `wheels = [...]` array itself - deliberately does
    NOT try to also match/consume any preceding comment lines, since doing
    that with a DOTALL regex previously ate unrelated manifest fields
    (license, blender_version_min) that happened to appear earlier in the
    file behind their own comment lines."""
    wheel_paths = sorted(p.name for p in OUT_DIR.glob("*.whl"))
    entries = "\n".join(f'  "./wheels/{name}",' for name in wheel_paths)
    new_block = "wheels = [\n" + entries + "\n]"

    text = MANIFEST_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"wheels = \[.*?\]", re.DOTALL)
    assert pattern.search(text), "wheels = [...] block not found in manifest"
    MANIFEST_PATH.write_text(pattern.sub(new_block, text, count=1), encoding="utf-8")


def main() -> None:
    if not (ILLUSION_REPO / "pyproject.toml").is_file() or not BLENDERPROC_SRC.is_dir():
        raise SystemExit(
            f"Could not find an illusion checkout at {ILLUSION_REPO}.\n"
            "Set ILLUSION_REPO to the repo root, e.g.\n"
            "    ILLUSION_REPO=/path/to/illusion python build_wheels.py"
        )
    print(f"Packaging illusion from: {ILLUSION_REPO}")

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "-w",
            str(OUT_DIR),
            str(BLENDERPROC_SRC),
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "-w",
            str(OUT_DIR),
            str(ILLUSION_REPO),
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "-w",
            str(OUT_DIR),
            *PYPI_DEPS,
        ]
    )

    rewrite_manifest_wheels_list()
    print(f"\nWheels written to {OUT_DIR}, blender_manifest.toml updated.")


if __name__ == "__main__":
    main()
