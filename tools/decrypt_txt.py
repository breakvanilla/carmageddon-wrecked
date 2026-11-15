#!/usr/bin/env python3
"""Rewrite a Carmageddon data .TXT file as plain text.

Lines starting with '@' are XOR-encrypted with one of two methods, and the game picks one from GENERAL.TXT. The DOS
release's DATA/RACES/VOODOO.TXT uses the other one. Plain lines are read as-is, so a decrypted file works either way.

Usage: decrypt_txt.py FILE EXPECTED_FIRST_WORD
"""
import struct
import sys

KEY = struct.pack("<4I", 0x5F991B6C, 0x135FCDB9, 0x0E2004CB, 0x0EA11C5E)
COMMENT_KEY = struct.pack("<4I", 0x26D6A867, 0x1B45DDB6, 0x13227E32, 0x3794C215)


def decode(line, method):
    s = bytearray(line)
    key = KEY
    seed = len(s) % 16
    for i in range(len(s)):
        if i >= 2 and s[i - 1] == ord("/") and s[i - 2] == ord("/"):
            key = COMMENT_KEY
        if method == 1:
            if s[i] == 9:
                s[i] = 0x9F
            s[i] = ((key[seed] ^ ((s[i] - 32) & 0xFF)) & 0x7F) + 32
            if s[i] == 0x9F:
                s[i] = 9
        else:
            if s[i] == 9:
                s[i] = 0x80
            c = (s[i] - 32) & 0xFF
            if not c & 0x80:
                s[i] = ((c ^ (key[seed] & 0x7F)) + 32) & 0xFF
            if s[i] == 0x80:
                s[i] = 9
        seed = (seed + 7) % 16
    return bytes(s)


def decrypt(lines, method):
    return [decode(l[1:], method) if l.startswith(b"@") else l for l in lines]


def junk(lines):
    return sum(1 for l in lines for c in l if not (32 <= c < 127 or c == 9))


def main():
    path, first_word = sys.argv[1], sys.argv[2].encode().lower()
    lines = [l.rstrip(b"\r") for l in open(path, "rb").read().split(b"\n")]
    while lines and lines[-1] == b"":
        lines.pop()
    if not any(l.startswith(b"@") for l in lines):
        print(f"{path}: already plain text")
        return
    # The first line often decodes the same either way, so judge by the whole file.
    method, plain = min(((m, decrypt(lines, m)) for m in (1, 2)), key=lambda mp: junk(mp[1]))
    if not plain[0].lower().startswith(first_word) or junk(plain):
        sys.exit(f"{path}: no method decodes cleanly")
    open(path, "wb").write(b"\r\n".join(plain) + b"\r\n")
    print(f"{path}: decrypted (method {method})")


if __name__ == "__main__":
    main()
