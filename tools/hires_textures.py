#!/usr/bin/env python3
"""Build hi-res replacement textures for the native (dethrace) game with Upscayl's AI upscaler.

Writes DATA/HIRES/<identifier>-<width>x<height>-<crc32>.png for every 8-bit texture in DATA/PIXELMAP/*.PIX. Tracks
reuse names for different pictures, so the size and pixel checksum pick the right one.

- 4x; skies (named in the race files) fill more of the screen, so they go to 8x and are debanded.
- Edges are wrap-padded before upscaling so tiling textures stay seamless; skies wrap only sideways.
- Palette index 0, the colour key, comes out pure black, and nothing else does.
- Existing PNGs are kept unless --force, so an interrupted run carries on.

Usage: hires_textures.py DATA_DIR [--skies | --only PATTERN] [--force]
Needs Pillow and numpy (see setup-native.sh) and Upscayl in /Applications.
"""
import argparse
import fnmatch
import glob
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decrypt_txt import decrypt, junk  # noqa: E402

UPSCAYL = "/Applications/Upscayl.app/Contents/Resources"
MODEL = "upscayl-standard-4x"
PAD = 8  # source pixels of wrapped border around each texture

BR_PMT_INDEX_8 = 3
FID_OLD_PIXELMAP = 0x03
FID_PIXELMAP = 0x3D
FID_PIXELS = 0x21


def read_pix(path):
    """Yield (identifier, width, height, row_bytes, type, pixels) for each pixelmap in a BRender .PIX file."""
    data = open(path, "rb").read()
    off = 0
    header = None
    while off + 8 <= len(data):
        cid, length = struct.unpack(">II", data[off:off + 8])
        body = data[off + 8:off + 8 + length]
        off += 8 + length
        if cid in (FID_OLD_PIXELMAP, FID_PIXELMAP):
            ptype, row_bytes, width, height = struct.unpack(">BHHH", body[:7])
            name_at = 11 if cid == FID_OLD_PIXELMAP else 13
            name = body[name_at:body.index(b"\0", name_at)].decode("latin-1")
            header = (name, width, height, row_bytes, ptype)
        elif cid == FID_PIXELS and header is not None:
            count, size = struct.unpack(">II", body[:8])
            yield header + (body[8:8 + count * size],)
            header = None


def read_palette(path):
    for _, _, height, _, _, pixels in read_pix(path):
        entries = np.frombuffer(pixels, dtype=np.uint8).reshape(height, 4)
        return entries[:, 1:4]  # stored as X, R, G, B
    sys.exit(f"{path}: no palette found")


def base_name(identifier):
    return os.path.splitext(identifier.lower())[0]


def output_name(identifier, index):
    height, width = index.shape
    return f"{base_name(identifier)}-{width}x{height}-{zlib.crc32(index.tobytes()):08x}.png"


def sky_names(data_dir):
    """Base names of the sky textures the race files use."""
    skies = set()
    for path in glob.glob(os.path.join(data_dir, "RACES", "*.TXT")):
        lines = [line.rstrip(b"\r") for line in open(path, "rb").read().split(b"\n")]
        for line in min((decrypt(lines, m) for m in (1, 2)), key=junk):
            if b"name of sky texture" in line.lower():
                name = line.split(b"//")[0].strip().decode("latin-1")
                if name.lower() != "none":
                    skies.add(base_name(name))
    return skies


def collect(data_dir, pattern):
    """Every distinct 8-bit texture, keyed by output file name."""
    textures = {}
    pix_dir = os.path.join(data_dir, "PIXELMAP")
    for file in sorted(os.listdir(pix_dir)):
        if not file.upper().endswith(".PIX"):
            continue
        for name, width, height, row_bytes, ptype, pixels in read_pix(os.path.join(pix_dir, file)):
            if ptype != BR_PMT_INDEX_8 or width == 0 or height == 0:
                continue
            if not fnmatch.fnmatch(name.lower(), pattern.lower()):
                continue
            index = np.ascontiguousarray(
                np.frombuffer(pixels, dtype=np.uint8)[:row_bytes * height].reshape(height, row_bytes)[:, :width])
            textures[output_name(name, index)] = (base_name(name), index)
    return textures


def pad(rgb, border, sky):
    if sky:
        rgb = np.pad(rgb, ((border, border), (0, 0), (0, 0)), mode="edge")
        return np.pad(rgb, ((0, 0), (border, border), (0, 0)), mode="wrap")
    return np.pad(rgb, ((border, border), (border, border), (0, 0)), mode="wrap")


def upscale(images, scale, work):
    """Upscale {key: padded RGB array} by scale (2 or 4) in one Upscayl run. Returns {key: array}."""
    src_dir = tempfile.mkdtemp(dir=work)
    out_dir = tempfile.mkdtemp(dir=work)
    for key, rgb in images.items():
        Image.fromarray(rgb, "RGB").save(os.path.join(src_dir, key), compress_level=1)
    subprocess.run([os.path.join(UPSCAYL, "bin", "upscayl-bin"), "-i", src_dir, "-o", out_dir,
                    "-m", os.path.join(UPSCAYL, "models"), "-n", MODEL, "-s", str(scale), "-f", "png"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    result = {}
    for key in images:
        path = os.path.join(out_dir, key)
        if os.path.exists(path):
            result[key] = np.asarray(Image.open(path).convert("RGB"))
        else:
            print(f"{key}: upscaler produced nothing", file=sys.stderr)
    return result


def deband(rgb):
    """Smooth flat areas (the 256-colour steps in sky gradients) and leave edges and detail alone."""
    out = rgb.astype(np.float32)
    for radius, threshold in ((48, 24.0), (16, 12.0)):
        blur = np.asarray(Image.fromarray(out.astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius)))
        blur = blur.astype(np.float32)
        flat = np.clip((threshold - np.abs(out - blur).max(axis=2, keepdims=True)) / threshold, 0, 1) ** 0.5
        out = out * (1 - flat) + blur * flat
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("data_dir")
    parser.add_argument("--only", default="*", help="identifier pattern, e.g. 'tree*'")
    parser.add_argument("--skies", action="store_true", help="only the sky textures")
    parser.add_argument("--force", action="store_true", help="redo textures that already have a PNG")
    args = parser.parse_args()

    out_dir = os.path.join(args.data_dir, "HIRES")
    os.makedirs(out_dir, exist_ok=True)
    palette = read_palette(os.path.join(args.data_dir, "REG", "PALETTES", "DRRENDER.PAL"))
    skies = sky_names(args.data_dir)
    textures = collect(args.data_dir, args.only)
    if args.skies:
        textures = {k: v for k, v in textures.items() if v[0] in skies}
    todo = {k: v[1] for k, v in textures.items() if args.force or not os.path.exists(os.path.join(out_dir, k))}
    sky_keys = {k for k, v in textures.items() if v[0] in skies}
    print(f"{len(textures)} textures match, {len(todo)} to upscale ({len(sky_keys & set(todo))} of them skies)")
    if not todo:
        return

    work = tempfile.mkdtemp(prefix="carma_hires_")
    try:
        first = upscale({k: pad(palette[index].astype(np.uint8), PAD, k in sky_keys) for k, index in todo.items()}, 4, work)
        results = {}
        for key, up in first.items():
            height, width = todo[key].shape
            results[key] = (up[PAD * 4:PAD * 4 + height * 4, PAD * 4:PAD * 4 + width * 4], 4)

        second_pass = [k for k in results if k in sky_keys]
        if second_pass:
            border = PAD * 4
            second = upscale({k: pad(np.ascontiguousarray(results[k][0]), border, True) for k in second_pass}, 2, work)
            for key, up in second.items():
                height, width = todo[key].shape
                results[key] = (deband(up[border * 2:border * 2 + height * 8, border * 2:border * 2 + width * 8]), 8)

        for key, (up, scale) in results.items():
            index = todo[key]
            height, width = index.shape
            up = up.copy()
            key_mask = np.asarray(Image.fromarray(((index == 0) * 255).astype(np.uint8)).resize(
                (width * scale, height * scale), Image.BILINEAR)) >= 128
            up[np.all(up == 0, axis=2)] = 1
            up[key_mask] = 0
            Image.fromarray(up, "RGB").save(os.path.join(out_dir, key), compress_level=6)
        print(f"wrote {len(results)} textures to {out_dir}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
