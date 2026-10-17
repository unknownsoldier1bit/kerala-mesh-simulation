#!/usr/bin/env bash
# Runs one simulation from sim/ and writes its outputs to results/.
#
# Usage: scripts/run.sh <sim-name> [--flag=value ...]
#   scripts/run.sh diamond --protocol=olsr --run=3
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
NS3_DIR="${NS3_DIR:-$(cat "$REPO/.ns3-path" 2>/dev/null || true)}"
if [ ! -x "$NS3_DIR/ns3" ]; then
  echo "NS-3 isn't set up yet. Run scripts/setup.sh first."; exit 1
fi
if [ $# -lt 1 ]; then
  echo "Usage: scripts/run.sh <sim-name> [--flag=value ...]"; exit 1
fi

SIM="$1"; shift
mkdir -p "$REPO/results"
cd "$NS3_DIR"
./ns3 run "$SIM $* --outDir=$REPO/results"
