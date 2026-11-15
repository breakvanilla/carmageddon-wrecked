#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bin="$root/local/ports/dethrace/build/dethrace"

if [[ ! -x "$bin" || ! -d "$root/local/native/CARMA" ]]; then
    echo "Native build missing. Run ./setup-native.sh first." >&2
    exit 1
fi

game="${1:-}"
if [[ -z "$game" ]]; then
    echo "1) Carmageddon"
    echo "2) Carmageddon Splat Pack"
    read -r -p "Choose: " game
fi
case "$game" in
    1 | carma) dir="$root/local/native/CARMA" ;;
    2 | splat) dir="$root/local/native/CARSPLAT" ;;
    *) echo "Unknown choice: $game" >&2; exit 1 ;;
esac
shift || true

# --physics-per-frame: physics every frame, not every 40 ms. --fps=120 caps the frame rate only when vsync stops
# blocking (window hidden or on another Space). --game-completed unlocks every race, car and upgrade.
unlock=(--game-completed)
if [[ "${CARMA_UNLOCK_ALL:-1}" == "0" ]]; then
    unlock=()
fi
exec "$bin" --opengl --physics-per-frame --fps=120 --dir "$dir" -hires ${unlock[@]+"${unlock[@]}"} "$@"
