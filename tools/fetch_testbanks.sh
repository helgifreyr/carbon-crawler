#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
tmp="$(mktemp -d)"
git clone -q --depth 1 --filter=blob:none --sparse https://github.com/carbonengine/audio.git "$tmp/audio"
git -C "$tmp/audio" sparse-checkout set tests/python/audiotests/test/soundbanks
mkdir -p res/audio
rm -rf res/audio/testbanks
cp -r "$tmp/audio/tests/python/audiotests/test/soundbanks" res/audio/testbanks
rm -rf "$tmp"
echo "fetched res/audio/testbanks"
