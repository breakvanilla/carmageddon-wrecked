#!/usr/bin/env python3
"""Remap Carmageddon driving controls to the arrow keys.

Driving moves from the keypad to the arrows, the camera and map from the arrows to [ ] ; ', and recovering the car
from Insert, which Mac keyboards lack, to Y. Menus read the arrows directly, so they are unaffected.

Usage: set_keys.py KEYMAP_0.TXT
"""
import sys

KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN = 70, 71, 72, 73
KEY_SEMICOLON, KEY_APOSTROPHE, KEY_LBRACKET, KEY_RBRACKET = 56, 57, 60, 61
KEY_Y = 45

# keymap slot -> key code
CHANGES = {
    46: KEY_LEFT,  # steer left
    47: KEY_RIGHT,  # steer right
    48: KEY_UP,  # accelerate
    49: KEY_DOWN,  # brake / reverse
    30: KEY_LBRACKET,  # camera zoom in, map up
    31: KEY_RBRACKET,  # camera zoom out, map down
    32: KEY_SEMICOLON,  # camera rotate left, map left
    33: KEY_APOSTROPHE,  # camera rotate right, map right
    59: KEY_Y,  # recover the car
}


def main():
    path = sys.argv[1]
    keys = [int(x) for x in open(path).read().split()]
    if len(keys) != 67:
        sys.exit(f"{path}: expected 67 key codes, found {len(keys)}")
    for slot, code in CHANGES.items():
        keys[slot] = code
    for slot, code in CHANGES.items():
        clashes = [i for i, k in enumerate(keys) if k == code and i != slot]
        if clashes:
            sys.exit(f"{path}: key {code} for slot {slot} is also bound to slots {clashes}")
    open(path, "w", newline="").write("".join(f"{k}\r\n" for k in keys))
    print(f"{path}: arrow-key driving set")


if __name__ == "__main__":
    main()
