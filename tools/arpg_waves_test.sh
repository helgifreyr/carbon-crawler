#!/usr/bin/env bash
# Headless smoke test: server + N AI companions play generated acts (or ARPG_MODE=crawl|waves); prints the server's reports.
# usage: tools/arpg_waves_test.sh [companions] [seconds]   (ARPG_FIRST_WAVE, INTERMISSION_S, ... pass through)
cd "$(dirname "$0")/.."
# Tests and captures run muted; set ARPG_AUDIO=1 to hear them.
export ARPG_AUDIO=${ARPG_AUDIO:-0}
export NET_PORT=${NET_PORT:-47410}
export ARPG_MODE=${ARPG_MODE:-act}
export INTERMISSION_S=${INTERMISSION_S:-6}
export NET_HOST=127.0.0.1
ROOT="$(cygpath -w "$PWD")"
COMPANIONS=${1:-2}
SECONDS_=${2:-80}
mkdir -p .run/arpg
SERVER_RUN_SECONDS=$SECONDS_ pwsh -NoProfile -File run_demo.ps1 -Script "$ROOT\demo\arpg_server.py" -RunName test_server \
    -TimeoutSec $((SECONDS_ + 15)) > .run/arpg/waves_server.log 2>&1 &
sleep 3
for c in $(seq 1 "$COMPANIONS"); do
  COMPANION_SEED=$c pwsh -NoProfile -File run_demo.ps1 -Script "$ROOT\demo\arpg_companion.py" -RunName test_companion$c \
      -TimeoutSec $((SECONDS_ + 15)) > .run/arpg/waves_companion$c.log 2>&1 &
done
wait
grep -E "^\[arpg\]   (act|wave|shots|players)" .run/arpg/waves_server.log
grep -il traceback .run/arpg/waves_*.log
exit 0
