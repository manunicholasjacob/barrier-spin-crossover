#!/usr/bin/env bash
# Energy cost of the barrier spin threshold, plus a tightened contention sweep.
#
# Throughput and power are NEVER read from the same run: the 10 Hz PMIC sampler
# still costs CPU on a 4-core board, so each condition is run twice, once clean
# for throughput and once sampled for power.
set -u
LLM=$HOME/llm
MODEL=$LLM/models/qwen0.5b-q4km.gguf
OMP_BIN=$LLM/llama.cpp/build/bin/llama-bench
OUT=$LLM/barrier2/raw3
mkdir -p "$OUT"
export LC_ALL=C
log() { echo "[$(date -u +%H:%M:%S)] $*" >&2; }

HOGPIDS=""
start_hogs() {
  HOGPIDS=""
  for i in $(seq 1 "$1"); do
    taskset -c 0-3 sh -c 'while :; do :; done' &
    HOGPIDS="$HOGPIDS $!"
  done
  log "hogs:$HOGPIDS"
}
stop_hogs() {
  for p in $HOGPIDS; do kill -9 "$p" 2>/dev/null; done
  wait 2>/dev/null; HOGPIDS=""
}
trap 'stop_hogs' EXIT

# clean_run <tag> <spincount> <ngen> <reps>
clean_run() {
  local tag=$1 sc=$2 ngen=$3 reps=$4
  local f="$OUT/${tag}.json"
  [ -s "$f" ] && { log "skip $tag"; return 0; }
  timeout 1200 env "GOMP_SPINCOUNT=$sc" taskset -c 0-3 "$OMP_BIN" \
      -m "$MODEL" -p 128 -n "$ngen" -t 4 -r "$reps" -o json > "$f.tmp" 2>/dev/null \
    && mv "$f.tmp" "$f" && log "ok $tag" || { log "FAIL $tag"; return 1; }
}

# power_run <tag> <spincount> <ngen> <reps>
power_run() {
  local tag=$1 sc=$2 ngen=$3 reps=$4
  local pf="$OUT/${tag}.power.jsonl"
  [ -s "$pf" ] && { log "skip $tag (power)"; return 0; }
  python3 "$LLM/barrier2/pmic_sampler.py" "$pf.tmp" 10 &
  local spid=$!
  sleep 2
  local t0=$(python3 -c 'import time;print(time.monotonic())')
  timeout 1200 env "GOMP_SPINCOUNT=$sc" taskset -c 0-3 "$OMP_BIN" \
      -m "$MODEL" -p 128 -n "$ngen" -t 4 -r "$reps" -o json \
      > "$OUT/${tag}.sampled.json" 2>/dev/null
  local rc=$?
  local t1=$(python3 -c 'import time;print(time.monotonic())')
  sleep 1
  kill -9 "$spid" 2>/dev/null; wait "$spid" 2>/dev/null
  mv "$pf.tmp" "$pf"
  echo "{\"tag\":\"$tag\",\"spincount\":$sc,\"bench_start\":$t0,\"bench_end\":$t1,\"rc\":$rc}" \
      >> "$OUT/windows.jsonl"
  log "ok $tag (power, $(python3 -c "print(round($t1-$t0,1))")s)"
}

SPINS_E="0 1000 10000 30000 100000 300000 1000000"

log "=== G1: energy, idle, 4 threads ==="
for sc in 0 10000 100000 1000000; do
  clean_run "G1_idle_sc${sc}_clean" "$sc" 256 2
  power_run "G1_idle_sc${sc}" "$sc" 256 2
done

log "=== G2: energy, 4 threads + 2 hogs ==="
start_hogs 2
for sc in 0 10000 100000 1000000; do
  clean_run "G2_hog2_sc${sc}_clean" "$sc" 64 2
  power_run "G2_hog2_sc${sc}" "$sc" 64 2
done
stop_hogs

log "=== H: tightened contention sweep, 4 reps, extra spin points ==="
start_hogs 2
for round in 1 2; do
  for sc in $SPINS_E; do
    clean_run "H_hog2_sc${sc}_r${round}" "$sc" 32 2
  done
done
stop_hogs

log "=== DONE energy ==="
