#!/usr/bin/env bash
# Server + casting bot + ARPG client on the test port; saves one client frame to demo/out/<name>.png.
# Usage: tools/arpg_capture.sh [name] [exit_frame]   (ARPG_CAM_DISTANCE etc. pass through)
set -e
cd "$(dirname "$0")/.."
NAME=${1:-arpg_look}
EXIT_FRAME=${2:-420}
# Tests and captures run muted; set ARPG_AUDIO=1 to hear them.
export ARPG_AUDIO=${ARPG_AUDIO:-0}
export NET_PORT=${NET_PORT:-47410}
export CARBON_FRAME_MS=${CARBON_FRAME_MS:-16}
export ARPG_MODE=${ARPG_MODE:-sandbox}
ROOT="$(cygpath -w "$PWD")"
mkdir -p .run/arpg demo/out
ENEMIES=${ENEMIES:-40} SERVER_RUN_SECONDS=40 pwsh -NoProfile -File run_demo.ps1 -Script "$ROOT\demo\arpg_server.py" \
    -RunName test_server -TimeoutSec 48 > .run/arpg/capture_server.log 2>&1 &
sleep 3
BOT_CAST=1 BOT_GOTO_RANGE=15 BOT_RUN_SECONDS=34 pwsh -NoProfile -File run_demo.ps1 -Script "$ROOT\demo\net_bot.py" \
    -RunName test_bot1 -TimeoutSec 44 > .run/arpg/capture_bot.log 2>&1 &
sleep 1
rm -f demo/out/trinity_viewer.bmp demo/out/trinity_viewer.png
VIEWER_AUTOGOTO_FRAME=${VIEWER_AUTOGOTO_FRAME:-90} VIEWER_EXIT_AFTER=$EXIT_FRAME pwsh -NoProfile -File run_demo.ps1 \
    -Script "$ROOT\demo\arpg_client.py" -RunName test_viewer1 -TimeoutSec 44 2>&1 | grep -E "frames|\[predict\]|Traceback|Error" || true
wait
py -3.12 -c "import glob; from PIL import Image; Image.open(glob.glob('demo/out/trinity_viewer.*')[0]).convert('RGB').save(r'demo/out/$NAME.png')"
echo "saved demo/out/$NAME.png"
