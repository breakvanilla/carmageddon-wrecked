#!/usr/bin/env python3
"""Paint the mod's own textures (minigun, hatch, rocket launcher, explosions, bullet holes, debris) into
DATA/HIRES/carmamod_*.png, which the patched renderer loads by name. Seeded, so every run gives the same result.

Usage: make_minigun_textures.py DATA_DIR [DATA_DIR ...]
Needs Pillow and numpy (see setup-native.sh).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 512
FONT = "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf"
rng = np.random.default_rng(1997)


def fbm(size=SIZE, octaves=6, stretch=(1, 1)):
    """Fractal noise in 0..1, tileable, optionally stretched along u or v."""
    out = np.zeros((size, size), np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        cells = 2 ** (o + 2)
        grid = rng.random((max(1, cells // stretch[1]), max(1, cells // stretch[0]))).astype(np.float32)
        tiled = np.tile(grid, (3, 3))
        img = Image.fromarray((tiled * 255).astype(np.uint8)).resize((size * 3, size * 3), Image.BICUBIC)
        layer = np.asarray(img, np.float32)[size:2 * size, size:2 * size] / 255.0
        out += amp * layer
        total += amp
        amp *= 0.55
    return out / total


def colourise(base, noise, amount):
    return np.asarray(base, np.float32)[None, None, :] * (1 + amount * (noise[..., None] - 0.5) * 2)


def scratches(img, count, colour, length=(20, 90), width=1, angle_spread=np.pi):
    draw = ImageDraw.Draw(img, "RGBA")
    for _ in range(count):
        x, y = rng.integers(0, SIZE, 2)
        a = rng.uniform(-angle_spread, angle_spread)
        n = rng.uniform(*length)
        x2, y2 = x + np.cos(a) * n, y + np.sin(a) * n
        draw.line([(x, y), (x2, y2)], fill=colour + (int(rng.integers(40, 110)),), width=width)
    return img


def soft(arr, alpha):
    """RGBA with soft edges from alpha. The colour is spread under the see-through part so blending and mipmaps
    don't pull in dark fringes."""
    alpha = np.clip(alpha, 0, 1).astype(np.float32)
    arr = np.clip(arr, 0, 255).astype(np.float32)
    solid = (alpha > 0.05).astype(np.float32)
    radius = max(2, arr.shape[0] // 32)

    def box(a, axis):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (radius + 1, radius)
        c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis)
        hi = np.take(c, range(2 * radius + 1, c.shape[axis]), axis=axis)
        lo = np.take(c, range(0, c.shape[axis] - 2 * radius - 1), axis=axis)
        return (hi - lo) / (2 * radius + 1)

    def blur(a):
        for _ in range(3):  # three box blurs come out close to a Gaussian
            a = box(box(a, 0), 1)
        return a
    den = blur(solid)
    spread = np.stack([blur(arr[..., c] * solid) for c in range(3)], -1) / np.maximum(den, 1e-4)[..., None]
    mean = (arr * solid[..., None]).sum((0, 1)) / max(1.0, solid.sum())
    spread = np.where(den[..., None] > 1e-3, spread, mean)
    rgb = np.where(solid[..., None] > 0, arr, spread)
    out = np.concatenate([np.clip(rgb, 1, 255), (alpha * 255)[..., None]], -1)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def finish(arr):
    # Pure black is the colour key (see-through), so keep solid textures just above it
    return Image.fromarray(np.clip(arr, 3, 255).astype(np.uint8), "RGB")


def gunmetal():
    n = fbm()
    brushed = fbm(stretch=(8, 1))
    arr = colourise((78, 81, 86), n, 0.18) * (0.92 + 0.16 * brushed[..., None])
    grime = fbm(octaves=4)
    arr *= 1 - 0.35 * np.clip((grime[..., None] - 0.55) * 3, 0, 1)
    img = finish(arr)
    img = scratches(img, 260, (170, 172, 176), (10, 60))
    return img


def barrel(hot=False):
    grain = rng.normal(0, 1, (SIZE, SIZE)).astype(np.float32)
    grain = np.asarray(Image.fromarray(np.clip(grain * 40 + 128, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7)), np.float32) / 255
    streaks = fbm(stretch=(1, 16))  # v runs along the barrel
    arr = colourise((54, 55, 58), grain, 0.25) * (0.85 + 0.3 * streaks[..., None])
    v = np.linspace(0, 1, SIZE, dtype=np.float32)[:, None, None]  # v = 0 at the muzzle
    blued = np.exp(-((v - 0.25) / 0.12) ** 2)
    arr = arr * (1 - 0.5 * blued) + np.array([58, 62, 84], np.float32) * 0.5 * blued
    soot = np.clip(1 - v / 0.12, 0, 1)
    arr *= 1 - 0.6 * soot
    if hot:
        glow = np.clip(1.15 - v * 0.9, 0, 1) * (0.8 + 0.4 * fbm(octaves=4)[..., None])
        arr = arr * 0.35 + glow * np.array([255, 105, 25], np.float32)
        arr += np.clip(glow - 0.75, 0, 1) * np.array([255, 220, 120], np.float32)
    return finish(arr)


def ammo_box():
    n = fbm()
    arr = colourise((80, 88, 50), n, 0.22)
    chips = fbm(octaves=7)
    bare = np.clip((chips - 0.66) * 12, 0, 1)[..., None]
    arr = arr * (1 - bare) + np.array([118, 116, 108], np.float32) * bare
    edge = np.minimum(np.minimum(np.arange(SIZE), SIZE - 1 - np.arange(SIZE))[None, :],
                      np.minimum(np.arange(SIZE), SIZE - 1 - np.arange(SIZE))[:, None]).astype(np.float32)
    arr *= (0.65 + 0.35 * np.clip(edge / 40, 0, 1))[..., None]
    img = finish(arr)
    draw = ImageDraw.Draw(img, "RGBA")
    stencil = (226, 205, 120, 215)
    for y, text, size in ((120, "CARTRIDGES", 74), (200, "7.62 MM  M134", 68), (290, "LINKED  4000 RDS", 50),
                          (360, "LOT CRM-1997", 44)):
        font = ImageFont.truetype(FONT, size)
        w = draw.textlength(text, font=font)
        draw.text(((SIZE - w) / 2, y), text, font=font, fill=stencil)
    for x in range(26, SIZE, 46):
        for y in (22, SIZE - 22):
            draw.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(60, 66, 38, 255), outline=(140, 146, 110, 255))
    draw.rectangle([SIZE // 2 - 60, 40, SIZE // 2 + 60, 80], fill=(70, 74, 46, 255), outline=(30, 32, 22, 255), width=4)
    img = scratches(img, 120, (150, 148, 140), (8, 40))
    return img


def mount():
    n = fbm()
    arr = colourise((66, 66, 70), n, 0.2)
    img = finish(arr)
    draw = ImageDraw.Draw(img, "RGBA")
    # Hazard stripes round the edge, the middle left as bare plate
    stripes = Image.new("RGB", (SIZE, SIZE), (20, 20, 20))
    sd = ImageDraw.Draw(stripes)
    for k in range(-SIZE, 2 * SIZE, 64):
        sd.polygon([(k, 0), (k + 32, 0), (k + 32 - SIZE, SIZE), (k - SIZE, SIZE)], fill=(222, 178, 18))
    mask = Image.new("L", (SIZE, SIZE), 0)
    md = ImageDraw.Draw(mask)
    md.rectangle([0, 0, SIZE, SIZE], fill=255)
    md.rectangle([90, 90, SIZE - 90, SIZE - 90], fill=0)
    worn = (np.asarray(mask, np.float32) * np.clip(1.6 - fbm(octaves=7) * 1.4, 0, 1)).astype(np.uint8)
    img.paste(stripes, (0, 0), Image.fromarray(worn))
    for x, y in ((50, 50), (SIZE - 50, 50), (50, SIZE - 50), (SIZE - 50, SIZE - 50)):
        draw.ellipse([x - 18, y - 18, x + 18, y + 18], fill=(80, 80, 84, 255), outline=(25, 25, 25, 255), width=3)
        draw.line([(x - 10, y), (x + 10, y)], fill=(25, 25, 25, 255), width=4)
    # Weld bead round the bare plate
    for t in range(0, 4 * (SIZE - 180), 9):
        side, d = divmod(t, SIZE - 180)
        x, y = [(90 + d, 90), (SIZE - 90, 90 + d), (SIZE - 90 - d, SIZE - 90), (90, SIZE - 90 - d)][side]
        draw.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(96, 92, 88, 255), outline=(40, 38, 36, 255))
    img = scratches(img, 160, (170, 170, 170), (10, 70))
    return img


def chute():
    n = fbm()
    arr = colourise((64, 66, 58), n, 0.2)
    v = np.arange(SIZE, dtype=np.float32)[:, None]
    ribs = 0.5 + 0.5 * np.cos(v / SIZE * 2 * np.pi * 12)
    arr *= (0.7 + 0.45 * ribs[..., None] ** 3)
    return finish(arr)


def flash():
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    dx, dy = (x - SIZE / 2) / (SIZE / 2), (y - SIZE / 2) / (SIZE / 2)
    r = np.sqrt(dx * dx + dy * dy) + 1e-6
    a = np.arctan2(dy, dx)
    spikes = 0.32 + 0.68 * np.abs(np.cos(a * 3)) ** 6 + 0.1 * fbm(octaves=5)
    k = np.clip(1 - r / spikes, 0, 1)
    core = np.clip(1 - r / 0.22, 0, 1)
    arr = (k[..., None] ** 1.4) * np.array([255, 150, 40], np.float32) + (core[..., None] ** 0.7) * np.array([255, 255, 220], np.float32)
    return soft(arr, np.clip(k * 1.6, 0, 1) ** 0.9 + core)


def hatch():
    n = fbm()
    arr = colourise((58, 60, 64), n, 0.16)
    img = finish(arr)
    draw = ImageDraw.Draw(img, "RGBA")
    # Raised anti-slip pattern, a recessed edge and a hazard strip along the closing edge (u = 1)
    for y in range(24, SIZE - 24, 34):
        for x in range(24, SIZE - 70, 34):
            if (x // 34 + y // 34) % 2:
                draw.line([(x, y), (x + 18, y + 6)], fill=(100, 102, 106, 255), width=5)
            else:
                draw.line([(x, y + 6), (x + 18, y)], fill=(100, 102, 106, 255), width=5)
    draw.rectangle([4, 4, SIZE - 5, SIZE - 5], outline=(24, 24, 26, 255), width=8)
    stripes = Image.new("RGB", (56, SIZE), (20, 20, 20))
    sd = ImageDraw.Draw(stripes)
    for k in range(-64, SIZE + 64, 40):
        sd.polygon([(0, k), (0, k + 20), (56, k + 76), (56, k + 56)], fill=(222, 178, 18))
    img.paste(stripes, (SIZE - 60, 0))
    img = scratches(img, 140, (160, 160, 164), (8, 50))
    return img


def well():
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    edge = np.minimum(np.minimum(x, SIZE - 1 - x), np.minimum(y, SIZE - 1 - y))
    depth = np.clip(edge / 90, 0, 1)
    arr = np.array([34, 34, 36], np.float32)[None, None, :] * (1 - 0.8 * depth[..., None])
    arr *= 0.85 + 0.3 * fbm(octaves=4)[..., None]
    return finish(arr)


def bullet_hole():
    """Crater with radial cracks and soot, fading out at the edge."""
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    dx, dy = (x - SIZE / 2) / (SIZE / 2), (y - SIZE / 2) / (SIZE / 2)
    r = np.sqrt(dx * dx + dy * dy)
    a = np.arctan2(dy, dx)
    jag = 1 + 0.12 * np.sin(a * 7 + 1) + 0.08 * np.sin(a * 13 + 2) + 0.15 * (fbm(octaves=5) - 0.5)
    rr = r / jag
    soot = np.clip(1 - rr / 0.95, 0, 1) ** 0.8
    arr = np.full((SIZE, SIZE, 3), 0, np.float32)
    shade = 60 - 45 * soot
    arr[:] = shade[..., None]
    rim = np.exp(-((rr - 0.32) / 0.06) ** 2)
    arr += rim[..., None] * np.array([70, 66, 60], np.float32)
    hole = rr < 0.26
    arr[hole] = np.array([14, 13, 12], np.float32) * (0.7 + 0.6 * fbm(octaves=3)[hole][:, None])
    img = Image.fromarray(np.clip(arr, 4, 255).astype(np.uint8), "RGB")
    draw = ImageDraw.Draw(img)
    for k in range(9):
        ang = rng.uniform(0, 2 * np.pi)
        px, py = SIZE / 2 + np.cos(ang) * SIZE * 0.13, SIZE / 2 + np.sin(ang) * SIZE * 0.13
        for step in range(5):
            ang += rng.uniform(-0.5, 0.5)
            nx, ny = px + np.cos(ang) * SIZE * 0.07, py + np.sin(ang) * SIZE * 0.07
            draw.line([(px, py), (nx, ny)], fill=(22, 21, 20), width=max(1, 6 - step))
            px, py = nx, ny
    arr = np.asarray(img).astype(np.float32)
    return soft(arr, np.clip((0.98 - rr) / 0.12, 0, 1) * np.clip(soot * 5, 0, 1))


def chunk():
    """Grey grit, tinted in the game to the colour of the wall it broke off."""
    n = fbm(octaves=7)
    grain = rng.normal(0, 1, (SIZE, SIZE)).astype(np.float32) * 0.08
    v = np.clip(0.75 + 0.35 * (n - 0.5) + grain, 0.4, 1.0)
    arr = (v[..., None] * np.array([235, 232, 226], np.float32))
    return finish(arr)


def radial(size):
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    dx, dy = (x - size / 2) / (size / 2), (y - size / 2) / (size / 2)
    return np.sqrt(dx * dx + dy * dy), np.arctan2(dy, dx)


def noise_at(size, octaves=5):
    n = fbm(octaves=octaves)
    if size != SIZE:
        n = np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC), np.float32) / 255
    return n


def rocket_pod():
    """Olive launcher housing: chipped paint, rivets and stencils."""
    n = fbm()
    arr = colourise((74, 80, 46), n, 0.22)
    chips = fbm(octaves=7)
    bare = np.clip((chips - 0.68) * 12, 0, 1)[..., None]
    arr = arr * (1 - bare) + np.array([112, 110, 104], np.float32) * bare
    img = finish(arr)
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle([6, 6, SIZE - 7, SIZE - 7], outline=(36, 40, 22, 255), width=10)
    for x in range(30, SIZE, 52):
        for y in (26, SIZE - 26):
            draw.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(60, 66, 36, 255), outline=(130, 136, 100, 255))
    stencil = (230, 210, 130, 220)
    for y, text, size in ((150, "DANGER", 96), (250, "ROCKETS  HE-FRAG", 60), (320, "M72  CRM-1997", 50)):
        font = ImageFont.truetype(FONT, size)
        w = draw.textlength(text, font=font)
        draw.text(((SIZE - w) / 2, y), text, font=font, fill=stencil)
    stripes = Image.new("RGB", (SIZE, 44), (20, 20, 20))
    sd = ImageDraw.Draw(stripes)
    for k in range(-64, SIZE + 64, 44):
        sd.polygon([(k, 0), (k + 22, 0), (k + 66, 44), (k + 44, 44)], fill=(222, 178, 18))
    img.paste(stripes, (0, 70))
    img = scratches(img, 160, (150, 150, 140), (8, 50))
    return img


def rocket_tube():
    """Inside of a launch tube: dark metal, sooty towards the back (v = 1)."""
    n = fbm(stretch=(1, 8))
    arr = colourise((60, 62, 60), n, 0.25)
    v = np.linspace(0, 1, SIZE, dtype=np.float32)[:, None, None]
    arr *= 1 - 0.75 * v
    return finish(arr)


def rocket_body():
    """Round the rocket (u) and along it from the nose (v = 0): off-white with red bands and markings."""
    n = fbm(octaves=5)
    arr = colourise((222, 218, 204), n, 0.08)
    v = np.linspace(0, 1, SIZE, dtype=np.float32)[:, None]
    band = ((v > 0.06) & (v < 0.16)) | ((v > 0.78) & (v < 0.84))
    arr[np.broadcast_to(band, (SIZE, SIZE))] = np.array([180, 26, 20], np.float32)
    soot = np.clip((v - 0.85) / 0.15, 0, 1)[..., None]
    arr *= 1 - 0.7 * soot
    img = finish(arr)
    draw = ImageDraw.Draw(img, "RGBA")
    font = ImageFont.truetype(FONT, 60)
    for u in (40, 296):
        text = Image.new("RGBA", (300, 80), (0, 0, 0, 0))
        ImageDraw.Draw(text).text((0, 0), "HE  CRM-97", font=font, fill=(26, 26, 30, 230))
        text = text.rotate(90, expand=True)
        img.paste(text, (u, 150), text)
    return img


def rocket_nose():
    n = fbm(octaves=5)
    arr = colourise((196, 34, 24), n, 0.12)
    v = np.linspace(0, 1, SIZE, dtype=np.float32)[:, None, None]
    arr *= 0.75 + 0.35 * v  # darker at the tip
    return finish(arr)


def rocket_fin():
    n = fbm()
    arr = colourise((54, 58, 50), n, 0.2)
    img = finish(arr)
    img = scratches(img, 60, (140, 140, 130), (8, 30))
    return img


def rocket_exhaust():
    """Exhaust plume, across (u) and away from the nozzle (v = 0)."""
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32) / SIZE
    width = 0.12 + 0.3 * y * (1 - y) * 2
    wobble = 0.04 * (fbm(octaves=4) - 0.5)
    d = np.abs(x - 0.5 + wobble) / width
    k = np.clip(1 - d, 0, 1) * np.clip(1 - y, 0, 1) ** 1.5
    core = np.clip(1 - d * 2.2, 0, 1) * np.clip(1 - y * 2.5, 0, 1)
    arr = k[..., None] * np.array([255, 130, 30], np.float32) + core[..., None] * np.array([255, 240, 200], np.float32)
    return soft(arr, np.clip(k * 2.5, 0, 1))


def rocket_glow():
    r, _ = radial(256)
    k = np.clip(1 - r, 0, 1) ** 1.6
    core = np.clip(1 - r / 0.35, 0, 1)
    arr = k[..., None] * np.array([255, 150, 50], np.float32) + core[..., None] * np.array([255, 245, 210], np.float32)
    return soft(arr, np.clip(k * 2, 0, 1))


def fireball(frame, frames=8):
    """One frame of an explosion: a white-hot ragged ball that cools to orange and dark red and breaks up."""
    size = 256
    t = frame / (frames - 1)
    r, a = radial(size)
    n = noise_at(size, 6)
    n2 = noise_at(size, 4)
    edge = 0.62 + 0.3 * t + 0.22 * (n - 0.5) + 0.06 * np.sin(a * 5 + frame)
    k = np.clip(1 - r / edge, 0, 1)
    # Breaks up into licks of flame as it burns out
    holes = np.clip((n2 - (0.75 - 0.5 * t)) * 4, 0, 1)
    k *= 1 - holes
    heat = np.clip(k * (1.4 - 1.1 * t) + 0.25 * (n - 0.5), 0, 1)
    ramp = np.array([[0.0, 0, 0, 0], [0.25, 110, 18, 6], [0.5, 220, 80, 14], [0.75, 255, 170, 50], [1.0, 255, 250, 220]], np.float32)
    arr = np.stack([np.interp(heat, ramp[:, 0], ramp[:, c]) for c in (1, 2, 3)], -1)
    arr *= (1 - 0.35 * t)
    return soft(arr, np.clip(k * 3, 0, 1) * np.clip(heat * 4, 0, 1))


def smoke(dark=False):
    """A puff of smoke, wispy at the edge."""
    size = 256
    r, a = radial(size)
    n = noise_at(size, 6)
    edge = 0.8 + 0.25 * (n - 0.5) + 0.05 * np.sin(a * 6)
    k = np.clip(1 - r / edge, 0, 1)
    base = np.array([92, 88, 84] if dark else [176, 174, 170], np.float32)
    arr = base[None, None, :] * (0.75 + 0.45 * n[..., None]) * (0.8 + 0.2 * k[..., None])
    return soft(arr, np.clip(k * 2.2, 0, 1) ** 1.3 * (0.85 + 0.2 * n))


def scorch():
    """Blast mark: soot, darkest in the middle, with streaks thrown out from it, fading out at the edge."""
    r, a = radial(SIZE)
    n = fbm(octaves=6)
    streaks = 0.5 + 0.5 * np.sin(a * 23 + 4 * n) * np.sin(a * 9 + 2)
    edge = 0.72 + 0.14 * streaks ** 2 + 0.2 * (n - 0.5)
    k = np.clip(1 - r / edge, 0, 1)
    shade = 70 - 58 * np.clip(k * 1.6, 0, 1) ** 0.8
    arr = np.stack([shade * 1.02, shade, shade * 0.95], -1) * (0.8 + 0.4 * n[..., None])
    return soft(arr, np.clip(k * 2.5, 0, 1) ** 1.2)


def rim():
    """Broken concrete for rubble and blown-out holes: rough grey with cracks and bits of rebar."""
    n = fbm(octaves=7)
    grain = rng.normal(0, 1, (SIZE, SIZE)).astype(np.float32) * 0.06
    v = np.clip(0.55 + 0.4 * (n - 0.5) + grain, 0.2, 1.0)
    arr = v[..., None] * np.array([150, 146, 138], np.float32)
    pits = np.clip((fbm(octaves=5) - 0.62) * 6, 0, 1)[..., None]
    arr *= 1 - 0.55 * pits
    img = finish(arr)
    draw = ImageDraw.Draw(img, "RGBA")
    for _ in range(14):
        x, y = rng.integers(0, SIZE, 2)
        a = rng.uniform(0, 2 * np.pi)
        for step in range(6):
            a += rng.uniform(-0.6, 0.6)
            nx, ny = x + np.cos(a) * 40, y + np.sin(a) * 40
            draw.line([(x, y), (nx, ny)], fill=(40, 38, 36, 200), width=3)
            x, y = nx, ny
    for _ in range(5):
        y = int(rng.integers(30, SIZE - 30))
        draw.line([(0, y), (SIZE, y + int(rng.integers(-20, 20)))], fill=(92, 60, 40, 230), width=7)
    return img


def cavity():
    """The dark inside of a blown-out wall."""
    n = fbm(octaves=6)
    v = np.clip(0.5 + 0.5 * (n - 0.5), 0.2, 1.0)
    arr = v[..., None] * np.array([46, 42, 38], np.float32)
    return finish(arr)


def water_spray():
    """White water spray: a soft, broken-up cloud of foam."""
    size = 256
    r, a = radial(size)
    n = noise_at(size, 6)
    n2 = noise_at(size, 3)
    k = np.clip(1 - r / (0.85 + 0.2 * (n2 - 0.5)), 0, 1)
    alpha = np.clip(k * 2.0, 0, 1) ** 1.2 * np.clip((n - 0.25) * 2.2, 0, 1)
    arr = np.stack([np.full((size, size), 235.0), np.full((size, size), 242.0), np.full((size, size), 245.0)], -1) * (0.85 + 0.15 * n[..., None])
    return soft(arr, alpha)


def water_drop():
    """A water droplet: clear, with a bright highlight and a darker rim."""
    size = 128
    r, a = radial(size)
    body = np.clip(1 - r / 0.75, 0, 1)
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    highlight = np.exp(-(((x - 0.38) ** 2 + (y - 0.35) ** 2) / 0.006))
    arr = np.stack([170 + 85 * highlight, 200 + 55 * highlight, 215 + 40 * highlight], -1)
    alpha = np.clip(body * 3, 0, 1) * (0.45 + 0.4 * np.clip((r - 0.45) / 0.3, 0, 1) + 0.6 * highlight)
    return soft(arr, np.clip(alpha, 0, 1))


def water_bubble():
    """An air bubble under water: a thin bright ring with a highlight."""
    size = 128
    r, a = radial(size)
    ring = np.exp(-((r - 0.62) / 0.09) ** 2)
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    highlight = np.exp(-(((x - 0.36) ** 2 + (y - 0.34) ** 2) / 0.004))
    arr = np.stack([200 + 55 * highlight, 230 + 25 * highlight, 240 + 15 * highlight], -1)
    alpha = np.clip(ring * 0.9 + highlight + 0.12 * np.clip(1 - r / 0.62, 0, 1), 0, 1)
    return soft(arr, alpha)


TEXTURES = {
    "gunmetal": gunmetal,
    "barrel": barrel,
    "barrel_hot": lambda: barrel(hot=True),
    "ammo": ammo_box,
    "mount": mount,
    "chute": chute,
    "flash": flash,
    "hatch": hatch,
    "well": well,
}
OTHER_TEXTURES = {
    "destruct_bullethole": bullet_hole,
    "destruct_chunk": chunk,
    "destruct_scorch": scorch,
    "destruct_rim": rim,
    "destruct_cavity": cavity,
    "water_spray": water_spray,
    "water_drop": water_drop,
    "water_bubble": water_bubble,
    "rocket_pod": rocket_pod,
    "rocket_tube": rocket_tube,
    "rocket_body": rocket_body,
    "rocket_nose": rocket_nose,
    "rocket_fin": rocket_fin,
    "rocket_exhaust": rocket_exhaust,
    "rocket_glow": rocket_glow,
    "rocket_smoke": smoke,
    "rocket_smoke_dark": lambda: smoke(dark=True),
    **{f"rocket_fireball_{i}": (lambda i=i: fireball(i)) for i in range(8)},
}


def main():
    images = {f"minigun_{name}": make() for name, make in TEXTURES.items()}
    images.update({name: make() for name, make in OTHER_TEXTURES.items()})
    for data_dir in sys.argv[1:]:
        out_dir = os.path.join(data_dir, "HIRES")
        os.makedirs(out_dir, exist_ok=True)
        for name, img in images.items():
            img.save(os.path.join(out_dir, f"carmamod_{name}.png"))
        print(f"wrote {len(images)} textures to {out_dir}")


if __name__ == "__main__":
    main()
