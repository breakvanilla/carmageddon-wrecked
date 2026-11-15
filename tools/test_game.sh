#!/usr/bin/env bash
# Runs the local build hidden, from a test script (commands: src/harness/testmode.c in dethrace-harness.patch).
# Usage: tools/test_game.sh SCRIPT [carma|splat] [dethrace options]
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bin="$root/local/ports/dethrace/build/dethrace"
script="${1:?usage: test_game.sh SCRIPT [carma|splat] [dethrace options]}"
game="${2:-carma}"
shift $(( $# >= 2 ? 2 : 1 ))

case "$game" in
    carma) dir="$root/local/native/CARMA" ;;
    splat) dir="$root/local/native/CARSPLAT" ;;
    *) echo "Unknown game: $game" >&2; exit 1 ;;
esac
name="$(basename "$script" .txt)"
out="${CARMA_TEST_OUTPUT:-/tmp/carma_test}/$name"
mkdir -p "$out"
find "$out" -maxdepth 1 -name '*.png' -delete
log="$out/run.log"

set +e
CARMA_MINIGUN_LOG="${CARMA_MINIGUN_LOG:-1}" CARMA_DEFORM_CHECK="${CARMA_DEFORM_CHECK:-1}" "$bin" --opengl --physics-per-frame --fps=120 --dir "$dir" -hires -nosound \
    --test-script="$(cd "$(dirname "$script")" && pwd)/$(basename "$script")" --test-output="$out" "$@" >"$log" 2>&1
status=$?
set -e

sed 's/\x1b\[[0-9;]*m//g' "$log" | grep -a -E '^\[(test|state|minigun)|PANIC|FATAL|GLREND: (curved|using)|Assertion|error' || true
echo "exit $status; log $log; screenshots:"
ls "$out"/*.png 2>/dev/null || echo "  none"
exit "$status"
