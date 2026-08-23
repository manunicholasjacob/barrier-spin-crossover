#!/usr/bin/env bash
# Does the optimal barrier spin threshold move when the cores are not free?
set -u
LLM=$HOME/llm
MODEL=$LLM/models/qwen0.5b-q4km.gguf
OMP_BIN=$LLM/llama.cpp/build/bin/llama-bench
NOMP_BIN=$LLM/llama.cpp/build-noomp/bin/llama-bench
OUT=$LLM/barrier2/raw2
mkdir -p "$OUT"
export LC_ALL=C
log() { echo "[$(date -u +%H:%M:%S)] $*" >&2; }

HOGPIDS=""
start_hogs() {
  local n=$1
  HOGPIDS=""
  for i in $(seq 1 "$n"); do
    taskset -c 0-3 sh -c 'while :; do :; done' &
    HOGPIDS="$HOGPIDS $!"
  done
  log "hogs started:$HOGPIDS"
}
stop_hogs() {
  for p in $HOGPIDS; do kill -9 "$p" 2>/dev/null; done
  wait 2>/dev/null
  HOGPIDS=""
  log "hogs stopped"
}
trap 'stop_hogs' EXIT

# run <tag> <bin> <threads> <ngen> <reps> [env...]
run() {
  local tag=$1 bin=$2 th=$3 ngen=$4 reps=$5; shift 5
  local f="$OUT/${tag}.json"
  [ -s "$f" ] && { log "skip $tag"; return 0; }
  local t0=$(date -u +%s)
  timeout 900 env "$@" taskset -c 0-3 "$bin" -m "$MODEL" -p 128 -n "$ngen" -t "$th" -r "$reps" -o json \
      > "$f.tmp" 2>"$OUT/${tag}.err"
  local rc=$?
  local t1=$(date -u +%s)
  if [ $rc -ne 0 ] || [ ! -s "$f.tmp" ]; then
    log "FAIL/TIMEOUT $tag rc=$rc ($((t1-t0))s)"; mv "$f.tmp" "$f.failed" 2>/dev/null; return 1
  fi
  mv "$f.tmp" "$f"
  echo "{\"tag\":\"$tag\",\"threads\":$th,\"n_gen\":$ngen,\"reps\":$reps,\"env\":\"$*\",\"secs\":$((t1-t0)),\"throttled\":\"$(vcgencmd get_throttled | sed s/throttled=//)\"}" >> "$OUT/meta.jsonl"
  log "ok $tag ($((t1-t0))s)"
}

SPINS="0 1000 10000 100000 300000 1000000 10000000"

log "=== E: 4 inference threads + 2 CPU hogs (6 runnable on 4 cores) ==="
start_hogs 2
for sc in $SPINS; do
  run "E_hog2_sc${sc}_t4" "$OMP_BIN" 4 32 2 "GOMP_SPINCOUNT=$sc"
done
run "E_hog2_noomp_t4" "$NOMP_BIN" 4 8 1 "IGNORE=1"
stop_hogs

log "=== F: 8 threads on 4 cores (2x oversubscribed) ==="
for sc in $SPINS; do
  run "F_over8_sc${sc}_t8" "$OMP_BIN" 8 32 2 "GOMP_SPINCOUNT=$sc"
done
run "F_over8_noomp_t8" "$NOMP_BIN" 8 8 1 "IGNORE=1"

log "=== DONE contention ==="
