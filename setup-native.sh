#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dethrace_rev="166dd93"
src="$root/local/ports/dethrace"
bin="$src/build/dethrace"
native="$root/local/native"
work="$native/cd"

for tool in cmake oggenc bchunk; do
    command -v "$tool" >/dev/null || { echo "Missing $tool. Run: brew install sdl2 cmake vorbis-tools bchunk" >&2; exit 1; }
done
if [[ ! -d "$native/CARMA" || ! -d "$native/CARSPLAT" ]] && [[ ! -d "$root/local/carmaged/cd" ]]; then
    echo "Game files missing in $root/local/carmaged. Run ./setup.sh first." >&2
    exit 1
fi

if [[ ! -d "$src" ]]; then
    git clone https://github.com/dethrace-labs/dethrace "$src"
    git -C "$src" checkout -q "$dethrace_rev"
    git -C "$src" submodule update --init --recursive
fi
for patch in "$root"/patches/*.patch; do
    dir="$src"
    if [[ "$(basename "$patch")" == brender-* ]]; then
        dir="$src/lib/BRender-v1.3.2"
    fi
    if ! git -C "$dir" apply --reverse --check "$patch" 2>/dev/null; then
        git -C "$dir" apply "$patch"
    fi
done
# stb_image v2.30 (nothings/stb@003501f)
cp "$root/vendor/stb_image.h" "$src/lib/BRender-v1.3.2/drivers/glrend/stb_image.h"
if [[ ! -f "$src/build/CMakeCache.txt" ]]; then
    cmake -S "$src" -B "$src/build" -DCMAKE_BUILD_TYPE=Release -DCARMA_DEV=ON
fi
cmake --build "$src/build" -j "$(sysctl -n hw.ncpu)"

# The install leaves cutscenes and sounds on the CD, so each game is copied with the CD's DATA merged in.
build_game() {
    local game=$1 cd_name=$2 tag=$3
    local dest="$native/$game"
    if [[ -d "$dest" ]]; then
        echo "$dest already exists; skipping."
        return
    fi
    mkdir -p "$work/$tag"
    (cd "$work/$tag" && bchunk -w "$root/local/carmaged/cd/$cd_name.BIN" "$root/local/carmaged/cd/$cd_name.CUE" track >/dev/null)
    mkdir "$work/$tag/iso"
    bsdtar -xf "$work/$tag/track01.iso" -C "$work/$tag/iso"

    cp -cR "$root/local/carmaged/$game" "$dest"
    rsync -a --ignore-existing "$work/$tag/iso/DATA/" "$dest/DATA/"
    chmod -R u+w "$dest"
    rm -f "$dest/DATA/PATHS.TXT"
    if [[ -f "$dest/DATA/RACES/VOODOO.TXT" ]]; then
        python3 -I "$root/tools/decrypt_txt.py" "$dest/DATA/RACES/VOODOO.TXT" version
    fi
    python3 -I "$root/tools/set_keys.py" "$dest/DATA/KEYMAP_0.TXT"

    mkdir "$dest/MUSIC"
    for wav in "$work/$tag"/track*.wav; do
        local n="${wav##*track}"
        oggenc -Q -q 6 "$wav" -o "$dest/MUSIC/Track${n%.wav}.ogg" &
    done
    wait
    rm -rf "$work/$tag"
}

build_game CARMA CARMAGEDDON carma
build_game CARSPLAT "SPLAT PACK" splat
rmdir "$work" 2>/dev/null || true
for game in CARMA CARSPLAT; do
    python3 -I "$root/tools/add_minigun_sound.py" "$native/$game/DATA"
done

# Hi-res skies only; tools/make_mod.sh says how to make the rest
if [[ -x /Applications/Upscayl.app/Contents/Resources/bin/upscayl-bin ]]; then
    if [[ ! -x "$root/.venv/bin/python" ]]; then
        python3 -m venv "$root/.venv"
        "$root/.venv/bin/pip" install -q pillow numpy
    fi
    for game in CARMA CARSPLAT; do
        "$root/.venv/bin/python" -I "$root/tools/hires_textures.py" "$native/$game/DATA" --skies
    done
else
    echo "Upscayl not found in /Applications; skipping hi-res skies (brew install --cask upscayl)."
fi
if [[ ! -x "$root/.venv/bin/python" ]]; then
    python3 -m venv "$root/.venv"
    "$root/.venv/bin/pip" install -q pillow numpy
fi
"$root/.venv/bin/python" -I "$root/tools/make_minigun_textures.py" "$native/CARMA/DATA" "$native/CARSPLAT/DATA"
# After the hi-res textures, as it softens the upscaled smoke
"$root/.venv/bin/python" -I "$root/tools/soft_effects.py" "$native/CARMA/DATA" "$native/CARSPLAT/DATA"

# Full Disk Access is tied to the app's signature, so an existing app is left alone and the apps only call native.command
make_app() {
    local name=$1 game=$2 choice=$3
    local app="$root/local/$name.app"
    if [[ -d "$app" ]]; then
        return
    fi
    mkdir -p "$app/Contents/MacOS"
    cat > "$app/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>$name</string>
    <key>CFBundleExecutable</key><string>launch</string>
    <key>CFBundleIdentifier</key><string>local.carma.$game</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
EOF
    cat > "$app/Contents/MacOS/launch" <<EOF
#!/bin/sh
exec "$root/native.command" $choice "\$@"
EOF
    chmod +x "$app/Contents/MacOS/launch"
    codesign --force -s - "$app"
}

make_app "Carmageddon" CARMA carma
make_app "Carmageddon Splat Pack" CARSPLAT splat

echo "Done. Start the game with ./native.command, or double-click the apps once they have Full Disk Access."
