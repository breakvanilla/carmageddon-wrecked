#!/usr/bin/env bash
# Unpacks the game zip (GAME_ZIP, default local/carmageddon.zip) into local/carmaged/ for setup-native.sh.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
game_zip="${GAME_ZIP:-$root/local/carmageddon.zip}"
dest="$root/local/carmaged"

if [[ -e "$dest" ]]; then
    echo "$dest already exists; remove it to re-extract." >&2
    exit 1
fi
if [[ ! -f "$game_zip" ]]; then
    echo "Game zip not found at $game_zip. Set GAME_ZIP to its path." >&2
    exit 1
fi

tmp="$(mktemp -d "$root/local/.extract.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT

unzip -q "$game_zip" -d "$tmp"
mv "$tmp/Carmaged" "$dest"

echo "Done. Next run ./setup-native.sh"
