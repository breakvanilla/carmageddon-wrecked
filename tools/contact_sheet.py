#!/usr/bin/env python3
"""Tile test screenshots into one image for a quick look. Usage: contact_sheet.py OUT.png IMAGE... (needs Pillow)"""
import sys
from PIL import Image, ImageDraw

out, files = sys.argv[1], sys.argv[2:]
w, h, cols = 480, 360, 3
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * w, rows * (h + 18)), (30, 30, 30))
draw = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    x, y = (i % cols) * w, (i // cols) * (h + 18)
    sheet.paste(Image.open(f).convert("RGB").resize((w, h)), (x, y + 18))
    draw.text((x + 4, y + 3), f.rsplit("/", 1)[-1], fill=(255, 255, 255))
sheet.save(out)
