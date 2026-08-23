#!/usr/bin/env bash
# Barrier spin-threshold sweep for llama.cpp PR #13079.
# Throughput only. Power is measured in a separate unperturbed pass (run_power.sh).
set -u

LLM=$HOME/llm
MODEL=$LLM/models/qwen0.5b-q4km.gguf
OMP_BIN=$LLM/llama.cpp/build/bin/llama-bench
NOMP_BIN=$LLM/llama.cpp/build-noomp/bin/llama-bench
OUT=$LLM/barrier2/raw
mkdir -p "$OUT"

export LC_ALL=C

log() { echo "[$(date -u +%H:%M:%S)] $*" >&2; }

throttled() { vcgencmd get_throttled | sed 's/throttled=//'; }
clockmhz()  { echo $(( $(vcgencmd measure_clock arm | cut -d= -f2) / 1000000 )); }

# run_one <tag> <binary> <threads> <n_gen> <reps> [env assignments...]
run_one() {
  local tag=$1 bin=$2 th=$3 ngen=$4 reps=$5; shift 5
  local f="$OUT/${tag}.json"
  if [ -s "$f" ]; then log "skip $tag (exists)"; return 0; fi
  local t0 t1 thr0 thr1 clk0 clk1
  thr0=$(throttled); clk0=$(clockmhz)
  t0=$(date -u +%s)
  env "$@" taskset -c 0-3 "$bin" -m "$MODEL" -p 128 -n "$ngen" -t "$th" -r "$reps" -o json \
      > "$f.tmp" 2>"$OUT/${tag}.err"
  local rc=$?
  t1=$(date -u +%s)
  thr1=$(throttled); clk1=$(clockmhz)
  if [ $rc -ne 0 ] || [ ! -s "$f.tmp" ]; then
    log "FAIL $tag rc=$rc"; mv "$f.tmp" "$f.failed" 2>/dev/null; return 1
  fi
  mv "$f.tmp" "$f"
  echo "{\"tag\":\"$tag\",\"threads\":$th,\"n_gen\":$ngen,\"reps\":$reps,\"env\":\"$*\",\"secs\":$((t1-t0)),\"throttled_before\":\"$thr0\",\"throttled_after\":\"$thr1\",\"clock_mhz_before\":$clk0,\"clock_mhz_after\":$clk1}" \
      >> "$OUT/meta.jsonl"
  log "ok $tag ($((t1-t0))s, throttled $thr0->$thr1, clk $clk0->$clk1)"
}

SPINS="0 1000 10000 100000 300000 1000000 10000000"
THREADS="1 2 4"

log "=== A: GOMP_SPINCOUNT sweep, idle, OpenMP build ==="
for round in 1 2; do
  for th in $THREADS; do
    for sc in $(echo $SPINS | tr ' ' '\n' | shuf); do
      run_one "A_omp_sc${sc}_t${th}_r${round}" "$OMP_BIN" "$th" 64 3 "GOMP_SPINCOUNT=$sc"
    done
  done
done

log "=== B: OMP_WAIT_POLICY reference, idle ==="
for th in $THREADS; do
  run_one "B_omp_passive_t${th}" "$OMP_BIN" "$th" 64 3 "OMP_WAIT_POLICY=passive"
  run_one "B_omp_active_t${th}"  "$OMP_BIN" "$th" 64 3 "OMP_WAIT_POLICY=active"
done

log "=== C: ggml unbounded-spin build (no OpenMP), idle, poll sweep ==="
for th in $THREADS; do
  run_one "C_noomp_polldef_t${th}" "$NOMP_BIN" "$th" 64 3 "IGNORE=1"
done
for p in 0 10 50 100; do
  f="$OUT/C_noomp_poll${p}_t4.json"
  if [ ! -s "$f" ]; then
    log "poll=$p t=4"
    taskset -c 0-3 "$NOMP_BIN" -m "$MODEL" -p 128 -n 64 -t 4 -r 3 --poll $p -o json > "$f.tmp" 2>/dev/null \
      && mv "$f.tmp" "$f" && log "ok C_noomp_poll${p}_t4"
  fi
done

log "=== DONE sweep ==="
