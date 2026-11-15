#!/usr/bin/env python3
"""Add the minigun and rocket launcher sounds (IDs 5600-5606) to a Carmageddon data folder.

Synthesizes the WAVs into DATA/SOUND in the game's format (8-bit mono, 16 kHz) and lists each in SOUND.TXT once.

Usage: add_minigun_sound.py DATA_DIR
"""
import math
import os
import random
import struct
import sys

RATE = 16000
ROUNDS = 8
ROUND_PERIOD = 0.04

ENTRY = """
// {title} (added by Wrecked Carmageddon, see tools/add_minigun_sound.py)

{id}\t\t\t\t// Sound ID
0x00,0x01\t\t\t// Type (0), Flags (0)
{file}\t\t\t// File name
4000\t\t\t\t// Priority
1\t\t\t\t\t// Repeat rate
230,230 \t\t\t// MinVol, MaxVol
0,0\t\t\t\t\t// MinPitch, MaxPitch
0,0\t\t\t\t\t// MinSpeed, MaxSpeed
0x0\t\t\t\t\t// Special FX index
1\t\t\t\t\t// Number of low memory alternatives
9999
"""


def burst():
    rng = random.Random(5600)
    n = int(RATE * ROUND_PERIOD * ROUNDS)
    out = [0.0] * n
    for r in range(ROUNDS):
        start = int(r * ROUND_PERIOD * RATE)
        low = 0.0
        for i in range(int(0.035 * RATE)):
            if start + i >= n:
                break
            t = i / RATE
            noise = rng.uniform(-1, 1)
            low += (noise - low) * 0.25  # one-pole low-pass for the body of the shot
            crack = noise * math.exp(-t / 0.002)
            body = low * 2.2 * math.exp(-t / 0.012)
            thump = math.sin(2 * math.pi * 85 * t) * math.exp(-t / 0.018)
            out[start + i] += 0.5 * crack + 0.6 * body + 0.7 * thump
    # Barrel whir under the shots
    for i in range(n):
        t = i / RATE
        out[i] += 0.06 * math.sin(2 * math.pi * 150 * t) * (0.6 + 0.4 * math.sin(2 * math.pi * 25 * t))
    peak = max(abs(x) for x in out)
    return bytes(max(0, min(255, int(128 + 120 * x / peak))) for x in out)


def to_8bit(out, level=120):
    peak = max(abs(x) for x in out) or 1
    return bytes(max(0, min(255, int(128 + level * x / peak))) for x in out)


def hatch():
    rng = random.Random(5601)
    n = int(RATE * 0.55)
    out, low = [], 0.0
    for i in range(n):
        t = i / RATE
        env = min(1, t / 0.04) * max(0, 1 - t / 0.5)
        low += (rng.uniform(-1, 1) - low) * 0.5
        hiss = low * 0.5 * env
        motor = 0.35 * math.sin(2 * math.pi * (180 + 60 * t) * t) * env * (0.7 + 0.3 * math.sin(2 * math.pi * 33 * t))
        thunk = 0.9 * math.sin(2 * math.pi * 70 * (t - 0.47)) * math.exp(-(t - 0.47) / 0.03) if t > 0.47 else 0
        out.append(hiss + motor + thunk)
    return to_8bit(out)


def lift():
    n = int(RATE * 0.75)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / RATE
        phase += 2 * math.pi * (220 + 260 * (t / 0.75) ** 0.7) / RATE
        env = min(1, t / 0.05) * min(1, (0.75 - t) / 0.08)
        out.append(env * (0.6 * math.sin(phase) + 0.25 * math.sin(2 * phase) + 0.12 * math.sin(3.01 * phase)))
    return to_8bit(out, 100)


def lock():
    rng = random.Random(5603)
    n = int(RATE * 0.3)
    out = [0.0] * n
    for start, pitch in ((0, 140), (int(RATE * 0.11), 95)):
        for i in range(int(RATE * 0.12)):
            t = i / RATE
            if start + i < n:
                out[start + i] += (math.sin(2 * math.pi * pitch * t) + 0.6 * rng.uniform(-1, 1) * math.exp(-t / 0.004)) * math.exp(-t / 0.025)
                out[start + i] += 0.3 * math.sin(2 * math.pi * 2300 * t) * math.exp(-t / 0.01)  # metallic ring
    return to_8bit(out)


def spin():
    n = int(RATE * 0.45)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / RATE
        phase += 2 * math.pi * (90 + 900 * (t / 0.45) ** 1.5) / RATE
        env = min(1, t / 0.03) * min(1, (0.45 - t) / 0.06)
        ratchet = 0.5 + 0.5 * math.sin(phase / 6)
        out.append(env * (0.5 * math.sin(phase) + 0.3 * ratchet * math.sin(phase * 2.5)))
    return to_8bit(out, 100)


def rocket_fire():
    rng = random.Random(5605)
    n = int(RATE * 0.9)
    out, low, low2 = [], 0.0, 0.0
    for i in range(n):
        t = i / RATE
        noise = rng.uniform(-1, 1)
        # Low-pass that closes as the rocket roars off
        cut = 0.08 + 0.5 * math.exp(-t / 0.12)
        low += (noise - low) * cut
        low2 += (low - low2) * 0.3
        env = min(1, t / 0.01) * math.exp(-t / 0.35)
        bang = (0.9 * noise * math.exp(-t / 0.006) + math.sin(2 * math.pi * 60 * t) * math.exp(-t / 0.05))
        out.append(1.6 * low2 * env + 0.8 * bang)
    return to_8bit(out)


def rocket_boom():
    rng = random.Random(5606)
    n = int(RATE * 1.8)
    out, low, low2 = [], 0.0, 0.0
    for i in range(n):
        t = i / RATE
        noise = rng.uniform(-1, 1)
        low += (noise - low) * (0.05 + 0.4 * math.exp(-t / 0.05))
        low2 += (low - low2) * 0.15
        crack = noise * math.exp(-t / 0.01)
        boom = math.sin(2 * math.pi * (55 - 20 * min(t, 0.5)) * t) * math.exp(-t / 0.25)
        rumble = low2 * 3.0 * min(1, t / 0.02) * math.exp(-t / 0.6)
        debris = 0.25 * noise * math.exp(-((t - 0.5) / 0.3) ** 2) * (rng.random() < 0.08)
        out.append(0.7 * crack + 0.9 * boom + rumble + debris)
    return to_8bit(out, 125)


SOUNDS = (
    (5600, "MINIGUN.WAV", "MINIGUN", None),
    (5601, "MGHATCH.WAV", "MINIGUN HATCH", hatch),
    (5602, "MGLIFT.WAV", "MINIGUN LIFT", lift),
    (5603, "MGLOCK.WAV", "MINIGUN LOCK", lock),
    (5604, "MGSPIN.WAV", "MINIGUN SPIN-UP", spin),
    (5605, "RKTFIRE.WAV", "ROCKET LAUNCH", rocket_fire),
    (5606, "RKTBOOM.WAV", "ROCKET EXPLOSION", rocket_boom),
)


def write_wav(path, samples):
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 36 + len(samples)) + b"WAVE")
        f.write(b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, RATE, RATE, 1, 8))
        f.write(b"data" + struct.pack("<I", len(samples)) + samples)


def main():
    sound_dir = os.path.join(sys.argv[1], "SOUND")
    bank = os.path.join(sound_dir, "SOUND.TXT")
    text = open(bank, "rb").read()
    added = []
    for sound_id, file, title, make in SOUNDS:
        write_wav(os.path.join(sound_dir, file), (make or burst)())
        if file.encode() in text:
            continue
        if not text.endswith(b"\n"):
            text += b"\r\n"
        text += ENTRY.format(id=sound_id, file=file, title=title).replace("\n", "\r\n").encode()
        added.append(sound_id)
    open(bank, "wb").write(text)
    print(f"{bank}: added sounds {added}" if added else f"{bank}: mod sounds already listed")


if __name__ == "__main__":
    main()
