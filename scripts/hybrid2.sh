#!/usr/bin/env bash
# Second hybrid campaign. Tests the equal-share partitioning model at core-count
# ratios it has not seen, on a quieter machine than round two.
#
# The model: if work is split evenly by thread index and the barrier waits for
# the slowest thread, then for nP fast cores and nE slow ones,
#
#     mixed / fast-only  =  (nP + nE) / nP  *  (vE / vP)
#
# With the measured per-core ratio vP/vE around 3.5 that gives:
#     2P+2E -> 0.57      2P+4E -> 0.86      2P+6E -> 1.14      2P+8E -> 1.43
#
# So the model says adding MORE slow cores should help, and past about four of
# them the mixed set should beat the two fast cores outright. Round two only ever
# measured 1:1 ratios, where the prediction is always a loss. If the crossing
# happens where predicted, the model holds. If the curve stays flat or keeps
# falling, it does not, and that is the more interesting outcome.
#
# CPU 0-11 are the six Golden Cove cores (two SMT siblings each), 12-19 the eight
# Gracemont cores. Masks take one thread per physical core.
set -u

LOCK=/c/llmpc/hybrid2.lock
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "another hybrid2 run holds $LOCK, refusing to start" >&2
  exit 1
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

BIN=/c/llmpc/bin/llama-bench.exe
M05=/c/llmpc/models/qwen0.5b-q4km.gguf
M15=/c/llmpc/models/qwen1.5b-q4km.gguf
OUT=/c/llmpc/hybrid2_raw
mkdir -p "$OUT"

log() { echo "[$(date -u +%H:%M:%S)] $*" >&2; }

snap_load() {
  local pct
  pct=$(powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Processor).LoadPercentage" 2>/dev/null | tr -d '\r\n ')
  echo "{\"marker\":\"$1\",\"load_pct\":\"$pct\",\"at\":\"$(date -u +%FT%TZ)\"}" >> "$OUT/load.jsonl"
  log "load at $1: ${pct}%"
}

# run <tag> <model> <mask> <threads> <blocktime> <ngen> <reps>
run() {
  local tag=$1 model=$2 mask=$3 th=$4 bt=$5 ngen=$6 reps=$7
  local f="$OUT/${tag}.json"
  [ -s "$f" ] && { log "skip $tag"; return 0; }
  local t0 t1
  t0=$(date +%s)
  KMP_BLOCKTIME="$bt" "$BIN" -m "$model" -p 128 -n "$ngen" -t "$th" -r "$reps" \
      -C "$mask" --cpu-strict 1 -o json > "$f.tmp" 2>/dev/null
  local rc=$?
  t1=$(date +%s)
  if [ $rc -ne 0 ] || [ ! -s "$f.tmp" ]; then
    log "FAIL $tag rc=$rc"; rm -f "$f.tmp"; return 1
  fi
  mv "$f.tmp" "$f"
  echo "{\"tag\":\"$tag\",\"mask\":\"$mask\",\"threads\":$th,\"blocktime\":\"$bt\",\"n_gen\":$ngen,\"reps\":$reps,\"secs\":$((t1-t0))}" >> "$OUT/meta.jsonl"
  log "ok $tag ($((t1-t0))s)"
}

# label:mask:threads
# The 2P series is the point of this campaign. P4 and P4E4 repeat round two on a
# quieter machine so the two campaigns can be compared directly.
SETS="P2:0x5:2 E2:0x3000:2 E4:0xF000:4 E6:0x3F000:6 E8:0xFF000:8 \
P2E2:0x3005:4 P2E4:0xF005:6 P2E6:0x3F005:8 P2E8:0xFF005:10 \
P4:0x55:4 P4E4:0xF055:8"

log "=== M1: core-count ratio sweep, qwen0.5b ==="
for round in 1 2 3; do
  snap_load "M1_round${round}"
  for bt in 200 infinite; do
    for s in $(echo $SETS | tr ' ' '\n' | grep -v '^$' | shuf); do
      lbl=${s%%:*}; rest=${s#*:}; mask=${rest%%:*}; th=${rest##*:}
      run "M1_${lbl}_bt${bt}_r${round}" "$M05" "$mask" "$th" "$bt" 64 3
    done
  done
done

log "=== M2: does the threshold separate on a quieter machine? ==="
BTS="0 1 5 20 200 infinite"
for round in 1 2; do
  snap_load "M2_round${round}"
  for s in $(echo "P4:0x55:4 E4:0xF000:4 P2E4:0xF005:6" | tr ' ' '\n' | shuf); do
    lbl=${s%%:*}; rest=${s#*:}; mask=${rest%%:*}; th=${rest##*:}
    for bt in $(echo $BTS | tr ' ' '\n' | shuf); do
      run "M2_${lbl}_bt${bt}_r${round}" "$M05" "$mask" "$th" "$bt" 64 3
    done
  done
done

log "=== M3: second model size, does the ratio law hold at 1.5B? ==="
if [ -s "$M15" ]; then
  for round in 1 2; do
    snap_load "M3_round${round}"
    for s in $(echo "P2:0x5:2 E4:0xF000:4 P2E4:0xF005:6 P2E2:0x3005:4" | tr ' ' '\n' | shuf); do
      lbl=${s%%:*}; rest=${s#*:}; mask=${rest%%:*}; th=${rest##*:}
      run "M3_${lbl}_bt200_r${round}" "$M15" "$mask" "$th" 200 32 2
    done
  done
else
  log "qwen1.5b not present, skipping M3"
fi

snap_load "end"
log "=== DONE hybrid2 ==="
