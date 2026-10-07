#!/usr/bin/env bash
# usage: tools/arpg_test.sh [bots]   (env passes through: TICK_MS, ENEMIES, SUSTAINED_CORRECT_EVERY, ...)
cd "$(dirname "$0")/.."
# Tests and captures run muted; set ARPG_AUDIO=1 to hear them.
export ARPG_AUDIO=${ARPG_AUDIO:-0}
export NET_PORT=${NET_PORT:-47410}
# Clients join the test server directly instead of showing the menu.
export ARPG_JOIN=127.0.0.1:$NET_PORT
export ARPG_MODE=${ARPG_MODE:-sandbox}
ROOT="$(cygpath -w "$PWD")"
BOTS=${1:-2}
mkdir -p .run/arpg
SERVER_RUN_SECONDS=24 pwsh -NoProfile -File run_demo.ps1 -Script "$ROOT\demo\arpg_server.py" -RunName test_server -TimeoutSec 35 > .run/arpg/server.log 2>&1 &
sleep 3
for b in $(seq 1 "$BOTS"); do
  BOT_CAST=1 BOT_GOTO_RANGE=25 BOT_RUN_SECONDS=15 BOT_SEED=$b pwsh -NoProfile -File run_demo.ps1 -Script "$ROOT\demo\net_bot.py" -RunName test_bot$b -TimeoutSec 30 > .run/arpg/bot$b.log 2>&1 &
done
wait
grep "^\[arpg\]" .run/arpg/server.log | sed -n 4p | sed -E 's/kills \{[^}]*\} //'
for b in $(seq 1 "$BOTS"); do grep "^\[bot" .run/arpg/bot$b.log | tail -1 | sed -E 's/.*rewinds ([0-9]+).*err ([0-9.]+) m.*client tick p50\/p99 ([0-9.\/]+) ms.*input latency p50 ([0-9.]+).*/  bot: rewinds \1  max err \2 m  client tick \3 ms  input p50 \4 ms/'; done
grep -il traceback .run/arpg/*.log
