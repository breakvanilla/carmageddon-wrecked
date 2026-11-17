#!/usr/bin/env bash
# Builds the Mac and Windows packages in local/dist/ from a fresh dethrace checkout with patches/*.patch applied.
# Usage: tools/make_mod.sh. For every HD texture, not only the skies, first run tools/hires_textures.py on
# local/native/CARMA/DATA and local/native/CARSPLAT/DATA.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="$root/local/mod-build"
src="$work/src"
deps="$work/deps"
dist="$root/local/dist"
dethrace_rev="166dd93"
sdl_version="2.32.10"
sdl_src_sha256="5f5993c530f084535c65a6879e9b26ad441169b3e25d789d83287040a9ca5165"
sdl_mingw_sha256="83a5d74012311edc3c0d40ea6faecbe57ad692aa033fa5dc273cc937e3938ff2"
python="$root/.venv/bin/python"
jobs=4
# Strip the build folder from source paths in the binaries (__FILE__ in asserts and logs)
prefix_map="-ffile-prefix-map=$work/="

for tool in cmake x86_64-w64-mingw32-gcc; do
    command -v "$tool" >/dev/null || { echo "Missing $tool. Run: brew install cmake mingw-w64" >&2; exit 1; }
done
[[ -x "$python" ]] || { echo "Missing $python. Run ./setup-native.sh first." >&2; exit 1; }

# SDL2: static universal build from source for the Mac, the official build for Windows
fetch() {
    local file=$1 sha=$2
    if [[ ! -f "$deps/$file" ]]; then
        curl -sSL "https://github.com/libsdl-org/SDL/releases/download/release-$sdl_version/$file" -o "$deps/$file"
    fi
    echo "$sha  $deps/$file" | shasum -a 256 -c --quiet - || { echo "$file: checksum mismatch" >&2; exit 1; }
}
mkdir -p "$deps"
fetch "SDL2-$sdl_version.tar.gz" "$sdl_src_sha256"
fetch "SDL2-devel-$sdl_version-mingw.tar.gz" "$sdl_mingw_sha256"
if [[ ! -f "$deps/sdl2-mac/lib/libSDL2.a" ]] || strings -a "$deps/sdl2-mac/lib/libSDL2.a" | grep -q -F -e "$HOME/" -e "$work/"; then
    rm -rf "$deps/sdl2-mac" "$deps/sdl2-mac-build" "$deps/SDL2-$sdl_version"
    tar xzf "$deps/SDL2-$sdl_version.tar.gz" -C "$deps"
    cmake -S "$deps/SDL2-$sdl_version" -B "$deps/sdl2-mac-build" -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_OSX_ARCHITECTURES="arm64;x86_64" -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0 \
        -DSDL_SHARED=OFF -DSDL_STATIC=ON -DSDL_TEST=OFF -DCMAKE_INSTALL_PREFIX="$deps/sdl2-mac" \
        -DCMAKE_C_FLAGS="$prefix_map" -DCMAKE_OBJC_FLAGS="$prefix_map" >/dev/null
    nice cmake --build "$deps/sdl2-mac-build" -j "$jobs" >/dev/null
    cmake --install "$deps/sdl2-mac-build" >/dev/null
fi
sdl_mingw="$deps/SDL2-$sdl_version/x86_64-w64-mingw32"
if [[ ! -d "$sdl_mingw" ]]; then
    tar xzf "$deps/SDL2-devel-$sdl_version-mingw.tar.gz" -C "$deps"
fi

if [[ ! -d "$src" ]]; then
    git clone -q https://github.com/dethrace-labs/dethrace "$src"
fi
git -C "$src" checkout -q -f "$dethrace_rev"
git -C "$src" clean -fdq
git -C "$src" submodule update -q --init --recursive
git -C "$src/lib/BRender-v1.3.2" checkout -q -f .
git -C "$src/lib/BRender-v1.3.2" clean -fdq
git -C "$src" apply "$root/patches/dethrace-game.patch"
git -C "$src" apply "$root/patches/dethrace-harness.patch"
git -C "$src/lib/BRender-v1.3.2" apply "$root/patches/brender-glrend.patch"
cp "$root/vendor/stb_image.h" "$src/lib/BRender-v1.3.2/drivers/glrend/stb_image.h"

cmake -S "$src" -B "$work/build-mac" -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES="arm64;x86_64" \
    -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0 -DSDL2_DIR="$deps/sdl2-mac/lib/cmake/SDL2" -DCMAKE_FIND_FRAMEWORK=NEVER \
    -DCMAKE_C_FLAGS="$prefix_map" -DCMAKE_CXX_FLAGS="$prefix_map" >/dev/null
build() {
    nice cmake --build "$1" -j "$jobs" >"$1.log" 2>&1 || { tail -30 "$1.log" >&2; exit 1; }
}
build "$work/build-mac"
# Everything but SDL2.dll and Windows' own DLLs linked in statically
cmake -S "$src" -B "$work/build-win" -DCMAKE_TOOLCHAIN_FILE="$root/tools/mingw-w64-x86_64.cmake" -DCMAKE_BUILD_TYPE=Release \
    -DSDL2_DIR="$sdl_mingw/lib/cmake/SDL2" -DCMAKE_PREFIX_PATH="$sdl_mingw" -DCMAKE_EXE_LINKER_FLAGS="-static" \
    -DCMAKE_C_FLAGS="$prefix_map" -DCMAKE_CXX_FLAGS="$prefix_map" >/dev/null
build "$work/build-win"

if otool -L "$work/build-mac/dethrace" | grep -q -e /opt/homebrew -e /usr/local; then
    echo "The Mac build links to Homebrew libraries" >&2
    exit 1
fi
if x86_64-w64-mingw32-objdump -p "$work/build-win/dethrace.exe" | grep "DLL Name" | grep -q -i -e libgcc -e winpthread -e libstdc; then
    echo "The Windows build needs MinGW DLLs" >&2
    exit 1
fi
for exe in "$work/build-mac/dethrace" "$work/build-win/dethrace.exe"; do
    if strings -a "$exe" | grep -q -F -e "$HOME/" -e "$work/"; then
        echo "$exe contains build paths" >&2
        exit 1
    fi
done

name="wrecked-carmageddon"
stage="$work/stage"
rm -rf "$stage"
mod="$stage/$name"
mkdir -p "$mod/SOUND" "$mod/LICENSES" "$mod/SOURCE"
cp "$root/tools/mod/dethrace.ini" "$root/tools/mod/README.txt" "$mod/"
printf '// The mod'"'"'s sounds, loaded after the game'"'"'s own DATA/SOUND/SOUND.TXT\r\n' > "$mod/SOUND/SOUND.TXT"
"$python" -I "$root/tools/add_minigun_sound.py" "$mod" >/dev/null
# Upscales from both games, without the mod's own textures and flames made below. soft_effects.py softens the
# keyed smoke upscale, so that one comes from HIRES/keyed where an earlier run has already softened it.
mkdir -p "$mod/HIRES"
for game in CARMA CARSPLAT; do
    hires="$root/local/native/$game/DATA/HIRES"
    find "$hires" -maxdepth 1 -name '*.png' ! -name 'carmamod_*' ! -name 'flm[0-9]*' -exec cp -n {} "$mod/HIRES/" \;
    if [[ -d "$hires/keyed" ]]; then
        find "$hires/keyed" -maxdepth 1 -name 'smoke-*.png' -exec cp {} "$mod/HIRES/" \;
    fi
done
"$python" -I "$root/tools/make_minigun_textures.py" "$mod" >/dev/null
"$python" -I "$root/tools/soft_effects.py" "$mod" >/dev/null
rm -rf "$mod/HIRES/keyed"
cp "$src/LICENSE" "$mod/LICENSES/dethrace-GPL-3.0.txt"
cp "$src/lib/BRender-v1.3.2/LICENSE" "$mod/LICENSES/BRender-MIT.txt"
cp "$src/lib/inih/LICENSE.TXT" "$mod/LICENSES/inih-BSD.txt"
cp "$src/lib/miniaudio/LICENSE" "$mod/LICENSES/miniaudio.txt"
cp "$root/vendor/LGPL-2.1.txt" "$mod/LICENSES/libsmacker-LGPL-2.1.txt"
cp "$deps/SDL2-$sdl_version/LICENSE.txt" "$mod/LICENSES/SDL2-zlib.txt"
sed -n '/^ALTERNATIVE A - MIT License/,/^-\{10,\}/p' "$root/vendor/stb_image.h" > "$mod/LICENSES/stb_image-MIT.txt"
# The source of our changes, for the GPL
cp "$root"/patches/*.patch "$root/vendor/stb_image.h" "$root/tools/make_mod.sh" "$root/tools/mingw-w64-x86_64.cmake" \
    "$root/tools/add_minigun_sound.py" "$root/tools/make_minigun_textures.py" "$root/tools/soft_effects.py" "$mod/SOURCE/"
cat > "$mod/SOURCE/README.txt" <<EOF
The engine is dethrace (https://github.com/dethrace-labs/dethrace) at revision $dethrace_rev, with these patches. dethrace-game.patch and dethrace-harness.patch apply in the dethrace folder, and brender-glrend.patch in lib/BRender-v1.3.2.

stb_image.h goes in lib/BRender-v1.3.2/drivers/glrend. make_mod.sh is the script that built this package, and the Python scripts made the mod's textures and sounds. Its tools/mod/ is dethrace.ini and README.txt, the ones in the folder above.
EOF

# Mac app, signed ad hoc (no Apple Developer ID)
mac="$stage/mac"
app="$mac/Wrecked Carmageddon.app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
cp "$work/build-mac/dethrace" "$app/Contents/MacOS/dethrace"
cp "$src/packaging/macos/dethrace.icns" "$app/Contents/Resources/"
cat > "$app/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>Wrecked Carmageddon</string>
    <key>CFBundleDisplayName</key><string>Wrecked Carmageddon</string>
    <key>CFBundleExecutable</key><string>dethrace</string>
    <key>CFBundleIdentifier</key><string>io.github.breakvanilla.wrecked-carmageddon</string>
    <key>CFBundleIconFile</key><string>dethrace.icns</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>1.0.1</string>
    <key>CFBundleVersion</key><string>2</string>
    <key>LSMinimumSystemVersion</key><string>11.0</string>
    <key>LSApplicationCategoryType</key><string>public.app-category.racing-games</string>
    <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
EOF
codesign --force --sign - "$app" 2>/dev/null
cp -R "$mod" "$mac/"

win="$stage/windows"
mkdir -p "$win"
cp "$work/build-win/dethrace.exe" "$win/Wrecked Carmageddon.exe"
cp "$sdl_mingw/bin/SDL2.dll" "$win/"
cp -R "$mod" "$win/"

rm -rf "$dist"
mkdir -p "$dist"
(cd "$mac" && zip -qry "$dist/$name-mac.zip" "Wrecked Carmageddon.app" "$name")
(cd "$win" && zip -qr "$dist/$name-windows.zip" "Wrecked Carmageddon.exe" SDL2.dll "$name")
rm -rf "$stage"
ls -l "$dist"
