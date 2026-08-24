"""Turns the source artwork into `assets/background.png`. Run by hand.

The same pattern as `sde/build_cyno_sets.py`: a generator committed beside the
artifact it produces, so the artifact is reproducible and the reasoning behind
it is not folded away into somebody's image editor.

⚠️ **numpy and OpenCV are used only here.** This file is never imported by the
application -- `ui/assets.py` loads the finished PNG and nothing else. The same
rule as `pyinstaller`: a tool, not a dependency, and `requirements.txt` stays
`requests` + `PySide6`.

    pip install opencv-python
    python assets/make_background.py "<source>.jfif"

The source is a 720x1456 portrait JPEG: a wireframe station at the top, a
radar dial through the middle, a ringed planet at the bottom.
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "background.png")

# Denoising strength. Luma stays at 3 and chroma goes to 10 on purpose: the
# artefact that shows on this picture is red/green speckle in the empty sky,
# while the station and the dial are thin bright lines that heavier luma
# smoothing eats. Measured at 4x exposure: h=3 clears the speckle and keeps
# the faint stars, h=7 starts erasing them.
DENOISE_LUMA, DENOISE_CHROMA = 3, 10

SCALE = 2

# ⚠️ NO CROP, and the reason is worth writing down because the first attempt
# got it backwards. The results window is used TALL AND NARROW -- measured on
# the real config, 552x1374, giving a viewport of about 538x1240, aspect 0.434.
# The whole picture is aspect 0.495. So the source composition already fits the
# window it is actually used in, and cover-scaling crops only a sliver off the
# top and bottom.
#
# The first version cropped a landscape band around the planet, chosen from
# renders at 900x560 and 700x420. Those renders were the mistake: the window's
# own saved geometry was in `config.json` all along. In a portrait window that
# landscape crop is magnified about 2.6x and shows one enormous soft fragment
# of the planet's limb.
#
# Stored width. 720 is the source's own width, so nothing is stored upscaled;
# the 2x Lanczos pass above is there to break up the JPEG's 8x8 blocks, and
# coming back down to 720 is what actually removes them. It also keeps the file
# under the 1 MB this repository is willing to carry forever -- 900 wide costs
# 1.35 MB for detail that is dimmed to 60% and sits behind an empty list.
STORE_W = 720

# Baked in rather than composited at runtime, so the app does no per-repaint
# work. 0.5 goes flat and 0.7 leaves the limb bright enough to pull the eye
# away from the topbar.
DIM = 0.60


def build(source: str) -> str:
    img = cv2.imread(source)
    if img is None:
        raise SystemExit(f"cannot read {source}")

    img = cv2.fastNlMeansDenoisingColored(
        img, None, DENOISE_LUMA, DENOISE_CHROMA, 7, 21)
    img = cv2.resize(img, (img.shape[1] * SCALE, img.shape[0] * SCALE),
                     interpolation=cv2.INTER_LANCZOS4)

    height = round(img.shape[0] * STORE_W / img.shape[1])
    img = cv2.resize(img, (STORE_W, height), interpolation=cv2.INTER_AREA)
    img = np.clip(img.astype(np.float32) * DIM, 0, 255).astype(np.uint8)

    cv2.imwrite(OUT, img, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    return OUT


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    path = build(sys.argv[1])
    print(f"{path}  {os.path.getsize(path) / 1024:.0f} KB")
