#!/usr/bin/env bash
# Runs the FPGA testbenches with Icarus Verilog. SIMULATION ONLY.
# Usage (Git Bash, from anywhere):  app/tests/fpga/run_sim.sh
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
rtl="$here/../../hardware/fpga/rtl"
build="$here/build"
mkdir -p "$build"

# Testbenches read the golden frames by a path relative to the repo root.
cd "$here/../../.."

command -v iverilog >/dev/null || { echo "iverilog not found on PATH"; exit 2; }

fail=0
for tb in "$here"/tb_*.v; do
    name="$(basename "$tb" .v)"
    echo "=== $name ==="
    iverilog -g2001 -Wall -Wno-timescale -o "$build/$name.vvp" -s "$name" "$tb" "$rtl"/*.v
    # Fixture files are shorter than the 256-byte test arrays; that warning is expected.
    out="$(vvp -n "$build/$name.vvp" | grep -v "Not enough words in the file")"
    echo "$out"
    echo "$out" | grep -q "SIMULATION PASS" || fail=1
done

if [ "$fail" = 0 ]; then
    echo "All FPGA testbenches passed (simulation only)."
else
    echo "FPGA testbench FAILED."
fi
exit "$fail"
