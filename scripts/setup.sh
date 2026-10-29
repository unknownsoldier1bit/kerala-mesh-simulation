#!/usr/bin/env bash
# Finds NS-3 (or downloads and builds it), then links every simulation in sim/
# into NS-3's scratch folder and builds them.
#
# Usage: scripts/setup.sh
# Optional environment variables:
#   NS3_DIR          path to an existing ns-3.xx folder (the one containing ./ns3)
#   NS3_VERSION      version to look for or download (default 3.47)
#   NS3_INSTALL_DIR  where to download NS-3 if none is found (default: <repo>/.ns3)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
NS3_VERSION="${NS3_VERSION:-3.47}"
NS3_DIR="${NS3_DIR:-}"
NS3_INSTALL_DIR="${NS3_INSTALL_DIR:-$REPO/.ns3}"
FRESH_INSTALL=0

# 1. Look for an existing install.
if [ -z "$NS3_DIR" ]; then
  for candidate in \
    "$HOME/ns-allinone-$NS3_VERSION/ns-$NS3_VERSION" \
    "$NS3_INSTALL_DIR/ns-allinone-$NS3_VERSION/ns-$NS3_VERSION"; do
    if [ -x "$candidate/ns3" ]; then NS3_DIR="$candidate"; break; fi
  done
fi

# 2. Otherwise download and build only the modules this project uses.
if [ -z "$NS3_DIR" ]; then
  for tool in cmake python3 curl tar; do
    command -v "$tool" >/dev/null || { echo "Missing $tool. On Ubuntu: sudo apt-get install -y cmake g++ python3 curl bzip2"; exit 1; }
  done
  command -v g++ >/dev/null || command -v clang++ >/dev/null || { echo "Missing a C++ compiler (g++ or clang++)"; exit 1; }
  echo "NS-3 not found. Downloading ns-allinone-$NS3_VERSION into $NS3_INSTALL_DIR ..."
  mkdir -p "$NS3_INSTALL_DIR"
  curl -fL --retry 3 -o "$NS3_INSTALL_DIR/ns3.tar.bz2" \
    "https://www.nsnam.org/releases/ns-allinone-$NS3_VERSION.tar.bz2"
  tar -xjf "$NS3_INSTALL_DIR/ns3.tar.bz2" -C "$NS3_INSTALL_DIR"
  rm "$NS3_INSTALL_DIR/ns3.tar.bz2"
  NS3_DIR="$NS3_INSTALL_DIR/ns-allinone-$NS3_VERSION/ns-$NS3_VERSION"
  FRESH_INSTALL=1
fi

echo "Using NS-3 at $NS3_DIR"
echo "$NS3_DIR" > "$REPO/.ns3-path"

# 3. Link each simulation folder into scratch/ (scratch/<name> -> sim/<name>).
for sim in "$REPO"/sim/*/; do
  name="$(basename "$sim")"
  target="$NS3_DIR/scratch/$name"
  if [ -e "$target" ] && [ ! -L "$target" ]; then
    echo "Skipping $name: $target exists and isn't a link from this repo"; continue
  fi
  ln -sfn "${sim%/}" "$target"
  echo "Linked scratch/$name -> sim/$name"
done

# 4. Configure (fresh installs only, so an existing setup is left alone) and build.
cd "$NS3_DIR"
if [ "$FRESH_INSTALL" = 1 ]; then
  ./ns3 configure --build-profile=optimized --disable-examples --disable-tests \
    --enable-modules="core;network;internet;wifi;mobility;propagation;applications;aodv;olsr;dsdv;flow-monitor;energy"
fi
# On an existing install its options are left untouched; the build re-scans scratch/ by itself.
for sim in "$REPO"/sim/*/; do
  ./ns3 build "$(basename "$sim")"
done
echo "Setup done. Try: scripts/run.sh diamond --protocol=aodv"
