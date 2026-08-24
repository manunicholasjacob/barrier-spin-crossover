#!/usr/bin/env bash
# Where does libgomp's DEFAULT spin behaviour sit on the curve, under contention?
set -u

# Single-instance guard. Two copies of a campaign started at once during round
# two and one deleted a model out from under the other one's benchmark. On the
# Pi an overlapping campaign once contaminated 43 runs and cost a full rerun.
LOCK=$HOME/llm/barrier2/.default.lock
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "another run of $(basename "$0") holds $LOCK, refusing to start" >&2
  exit 1
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
LLM=$HOME/llm; MODEL=$LLM/models/qwen0.5b-q4km.gguf
BIN=$LLM/llama.cpp/build/bin/llama-bench
OUT=$LLM/barrier2/raw4; mkdir -p "$OUT"; export LC_ALL=C
log(){ echo "[$(date -u +%H:%M:%S)] $*" >&2; }
HOGPIDS=""
start_hogs(){ HOGPIDS=""; for i in $(seq 1 "$1"); do taskset -c 0-3 sh -c 'while :; do :; done' & HOGPIDS="$HOGPIDS $!"; done; }
stop_hogs(){ for p in $HOGPIDS; do kill -9 "$p" 2>/dev/null; done; wait 2>/dev/null; HOGPIDS=""; }
trap 'stop_hogs' EXIT

run(){ # tag, ngen, reps, env...
  local tag=$1 ngen=$2 reps=$3; shift 3
  local f="$OUT/${tag}.json"; [ -s "$f" ] && { log "skip $tag"; return 0; }
  timeout 900 env "$@" taskset -c 0-3 "$BIN" -m "$MODEL" -p 128 -n "$ngen" -t 4 -r "$reps" -o json \
    > "$f.tmp" 2>/dev/null && mv "$f.tmp" "$f" && log "ok $tag" || log "FAIL $tag"
}

log "=== contended: default vs explicit ==="
start_hogs 2
for round in 1 2; do
  run "D_hog2_UNSET_r${round}"      32 2 "PLACEHOLDER=1"
  run "D_hog2_sc300000_r${round}"   32 2 "GOMP_SPINCOUNT=300000"
  run "D_hog2_sc0_r${round}"        32 2 "GOMP_SPINCOUNT=0"
  run "D_hog2_active_r${round}"     32 2 "OMP_WAIT_POLICY=active"
  run "D_hog2_passive_r${round}"    32 2 "OMP_WAIT_POLICY=passive"
done
stop_hogs

log "=== idle: default vs explicit ==="
for round in 1 2; do
  run "D_idle_UNSET_r${round}"      64 3 "PLACEHOLDER=1"
  run "D_idle_sc300000_r${round}"   64 3 "GOMP_SPINCOUNT=300000"
  run "D_idle_sc1000_r${round}"     64 3 "GOMP_SPINCOUNT=1000"
done
log "=== DONE default ==="
