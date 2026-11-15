#!/usr/bin/env python3
"""Better smoke and fire for the game's own effects.

The hi-res smoke puff (SMOKE.PIX, from tools/hires_textures.py) gets soft edges in its alpha in place of the black
colour key, and the 20 flame frames of burning cars (FLAMES.PIX) are painted anew. The keyed upscales are kept in
HIRES/keyed/.

Usage: soft_effects.py DATA_DIR [DATA_DIR ...]
Needs Pillow and numpy (see setup-native.sh).
"""
import os
import re
import sys

import numpy as np
from PIL import Image

SMOKE = re.compile(r"^smoke-\d+x\d+-[0-9a-f]{8}\.png$")
# Name, size and checksum of each 8-bit original flame frame, as the renderer looks them up
FLAMES = [
    ("flm01", 20, 25, "ba32e919"), ("flm02", 24, 32, "82c32f48"), ("flm03", 24, 34, "ab10419f"), ("flm04", 28, 44, "34cf01ea"),
    ("flm05", 28, 49, "f9ec5241"), ("flm06", 32, 53, "b4f3cbf7"), ("flm07", 28, 61, "49899878"), ("flm08", 28, 69, "074b346c"),
    ("flm09", 24, 61, "f785e1a2"), ("flm10", 28, 64, "ec5309a9"), ("flm11", 24, 70, "51be38ff"), ("flm12", 20, 65, "f35d6058"),
    ("flm13", 20, 64, "d605dccd"), ("flm14", 20, 74, "acd42325"), ("flm15", 28, 55, "906f5229"), ("flm16", 24, 62, "6dc61864"),
    ("flm17", 28, 47, "b566146e"), ("flm18", 20, 51, "a5dd09a0"), ("flm19", 20, 45, "fc88f855"), ("flm20", 20, 45, "d07e76bf"),
]
FLAME_SCALE = 8


def blur(a, radius):
    def box(a, axis):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (radius + 1, radius)
        c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis)
        hi = np.take(c, range(2 * radius + 1, c.shape[axis]), axis=axis)
        lo = np.take(c, range(0, c.shape[axis] - 2 * radius - 1), axis=axis)
        return (hi - lo) / (2 * radius + 1)

    for _ in range(3):
        a = box(box(a, 0), 1)
    return a


def soften(rgb, alpha):
    """RGBA, with the colour spread out under the see-through part so blending doesn't pull in dark fringes."""
    solid = (alpha > 0.05).astype(np.float32)
    radius = max(2, rgb.shape[0] // 32)
    den = blur(solid, radius)
    spread = np.stack([blur(rgb[..., c] * solid, radius) for c in range(3)], -1) / np.maximum(den, 1e-4)[..., None]
    rgb = np.where(solid[..., None] > 0, rgb, np.where(den[..., None] > 1e-3, spread, rgb))
    out = np.concatenate([np.clip(rgb, 1, 255), np.clip(alpha, 0, 1)[..., None] * 255], -1)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def noise(rng, width, height, cells_x, cells_y):
    """Smooth random field in 0..1, width x height."""
    grid = rng.random((cells_y + 3, cells_x + 3)).astype(np.float32)
    img = Image.fromarray((grid * 255).astype(np.uint8)).resize((width * (cells_x + 3) // cells_x, height * (cells_y + 3) // cells_y), Image.BICUBIC)
    return np.asarray(img, np.float32)[:height, :width] / 255.0


def flame(index, width, height):
    """Frame index (0-19) of a flame's life: it flares up, stretches into licking tongues and burns out."""
    t = index / 19.0
    rng = np.random.default_rng(4400 + index)
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)
    u = (x + 0.5) / width * 2 - 1           # across, -1..1
    v = 1 - (y + 0.5) / height              # up from the base, 0..1
    sway = noise(rng, width, height, 2, 4) - 0.5
    lick = noise(rng, width, height, 3, 6)
    curl = noise(rng, width, height, 5, 10)
    # Wide at the base, narrowing to tongues that wander more higher up
    xs = u + 0.7 * v * sway * 2
    widths = 0.95 * (1 - v) ** 0.55 + 0.05
    body = np.clip(1 - np.abs(xs) / widths, 0, 1)
    # Breaks into separate licks towards the top, more as it burns out
    tongues = np.clip((lick - (0.15 + 0.6 * v * (0.5 + t))) * 3, 0, 1)
    shape = body * np.clip(tongues + (1 - v) ** 2, 0, 1) * (0.8 + 0.4 * curl)
    heat = np.clip(shape * (1.25 - 0.8 * v) * (1.15 - 0.55 * t), 0, 1)
    ramp = np.array([[0.0, 90, 12, 4], [0.3, 200, 50, 10], [0.55, 255, 130, 25], [0.8, 255, 210, 70], [1.0, 255, 250, 215]], np.float32)
    rgb = np.stack([np.interp(heat, ramp[:, 0], ramp[:, c]) for c in (1, 2, 3)], -1)
    alpha = np.clip(shape * 3, 0, 1) * np.clip(heat * 4, 0, 1) * (1 - 0.45 * t) * np.clip(v * 12, 0, 1)
    return soften(rgb, alpha)


def convert(path):
    img = Image.open(path)
    if img.mode == "RGBA" and np.asarray(img)[..., 3].min() < 250:
        return False
    rgb = np.asarray(img.convert("RGB"), np.float32)
    lum = rgb.max(-1) / 255.0
    key = (lum > 0.02).astype(np.float32)
    radius = max(1, rgb.shape[0] // 48)
    if os.path.basename(path).startswith("smoke"):
        # A soft-edged puff: fades in from the edge of the keyed shape
        alpha = np.clip((blur(key, radius * 3) - 0.15) * 1.8, 0, 1)
    else:
        # Flames: bright is solid, the dim red licks at the edge fade out
        alpha = np.clip((lum - 0.04) / 0.3, 0, 1) * np.clip(blur(key, radius) * 1.5, 0, 1)
    soften(rgb, alpha).save(path)
    return True


def keep_keyed(hires, name):
    keyed = os.path.join(hires, "keyed")
    path = os.path.join(hires, name)
    if os.path.exists(path) and not os.path.exists(os.path.join(keyed, name)):
        os.makedirs(keyed, exist_ok=True)
        Image.open(path).save(os.path.join(keyed, name))


def main():
    flames = [flame(i, w * FLAME_SCALE, h * FLAME_SCALE) for i, (_, w, h, _) in enumerate(FLAMES)]
    for data_dir in sys.argv[1:]:
        hires = os.path.join(data_dir, "HIRES")
        os.makedirs(hires, exist_ok=True)
        smoke = 0
        for name in sorted(os.listdir(hires)):
            if SMOKE.match(name):
                keep_keyed(hires, name)
                smoke += convert(os.path.join(hires, name))
        for (base, w, h, crc), img in zip(FLAMES, flames):
            name = f"{base}-{w}x{h}-{crc}.png"
            keep_keyed(hires, name)
            img.save(os.path.join(hires, name))
        print(f"{hires}: {len(flames)} flame frames painted, {smoke} smoke textures softened")


if __name__ == "__main__":
    main()
