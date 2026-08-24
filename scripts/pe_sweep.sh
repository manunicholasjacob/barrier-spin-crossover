#!/usr/bin/env bash
# Barrier spin-threshold sweep on a heterogeneous CPU (i7-12700H, Golden Cove + Gracemont).
#
# The Windows llama.cpp build links LLVM libomp, so the spin-then-sleep threshold is
# KMP_BLOCKTIME rather than GOMP_SPINCOUNT. Same mechanism family as the Pi campaign.
#
# Affinity is set with llama-bench's own -C/--cpu-mask plus --cpu-strict 1, which was
# verified to bite: 4 threads forced onto one logical CPU collapse ~2x versus 4 CPUs.
#
# Masks use one thread per PHYSICAL core. On this part CPU 0-11 are the six P cores
# (two SMT siblings each) and CPU 12-19 are the eight E cores (no SMT).
#   P4    CPU 0,2,4,6          0x55
#   P6    CPU 0,2,4,6,8,10     0x555
#   E4    CPU 12,13,14,15      0xF000
#   E8    CPU 12..19           0xFF000
#   MIX4  CPU 0,2 + 12,13      0x3005
#   MIX8  CPU 0,2,4,6 + 12-15  0xF055
set -u

# Single-instance guard. Two copies of a campaign started at once during round
# two and one deleted a model out from under the other one's benchmark. On the
# Pi an overlapping campaign once contaminated 43 runs and cost a full rerun.
LOCK=/c/llmpc/.pe_sweep.lock
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "another run of $(basename "$0") holds $LOCK, refusing to start" >&2
  exit 1
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

BIN=/c/llmpc/bin/llama-bench.exe
MODEL=/c/llmpc/models/qwen0.5b-q4km.gguf
OUT=/c/llmpc/pe_raw
mkdir -p "$OUT"

log() { echo "[$(date -u +%H:%M:%S)] $*" >&2; }

# run <tag> <mask> <threads> <blocktime> <ngen> <reps>
run() {
  local tag=$1 mask=$2 th=$3 bt=$4 ngen=$5 reps=$6
  local f="$OUT/${tag}.json"
  [ -s "$f" ] && { log "skip $tag"; return 0; }
  local t0 t1
  t0=$(date +%s)
  KMP_BLOCKTIME="$bt" "$BIN" -m "$MODEL" -p 128 -n "$ngen" -t "$th" -r "$reps" \
      -C "$mask" --cpu-strict 1 -o json > "$f.tmp" 2>"$OUT/${tag}.err"
  local rc=$?
  t1=$(date +%s)
  if [ $rc -ne 0 ] || [ ! -s "$f.tmp" ]; then
    log "FAIL $tag rc=$rc"; mv "$f.tmp" "$f.failed" 2>/dev/null; return 1
  fi
  mv "$f.tmp" "$f"
  echo "{\"tag\":\"$tag\",\"mask\":\"$mask\",\"threads\":$th,\"blocktime\":\"$bt\",\"n_gen\":$ngen,\"reps\":$reps,\"secs\":$((t1-t0))}" >> "$OUT/meta.jsonl"
  log "ok $tag ($((t1-t0))s)"
}

snapshot_load() {
  local label=$1
  local pct
  pct=$(powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Processor).LoadPercentage" 2>/dev/null | tr -d '\r\n ')
  echo "{\"marker\":\"$label\",\"load_pct\":\"$pct\",\"at\":\"$(date -u +%FT%TZ)\"}" >> "$OUT/load.jsonl"
  log "load at $label: ${pct}%"
}

BLOCKTIMES="0 1 5 20 200 infinite"
# label:mask:threads
SETS_T4="P4:0x55:4 E4:0xF000:4 MIX4:0x3005:4"
SETS_T8="P6:0x555:6 E8:0xFF000:8 MIX8:0xF055:8"

log "=== L1: KMP_BLOCKTIME x core type, 4 threads each ==="
for round in 1 2 3; do
  snapshot_load "L1_round${round}_start"
  for s in $(echo $SETS_T4 | tr ' ' '\n' | shuf); do
    lbl=${s%%:*}; rest=${s#*:}; mask=${rest%%:*}; th=${rest##*:}
    for bt in $(echo $BLOCKTIMES | tr ' ' '\n' | shuf); do
      run "L1_${lbl}_bt${bt}_r${round}" "$mask" "$th" "$bt" 64 3
    done
  done
done

log "=== L2: same sweep at each set's natural width ==="
for round in 1 2; do
  snapshot_load "L2_round${round}_start"
  for s in $(echo $SETS_T8 | tr ' ' '\n' | shuf); do
    lbl=${s%%:*}; rest=${s#*:}; mask=${rest%%:*}; th=${rest##*:}
    for bt in $(echo $BLOCKTIMES | tr ' ' '\n' | shuf); do
      run "L2_${lbl}_bt${bt}_r${round}" "$mask" "$th" "$bt" 64 3
    done
  done
done

log "=== L3: long-tail test. Does adding E cores to a P set help or hurt? ==="
# At the default blocktime and at infinite, compare P-only against P+E at the same
# and at greater total width. If barriers gate on the slowest thread, adding E cores
# to a P set should give back less than the E cores are individually worth.
for round in 1 2 3; do
  snapshot_load "L3_round${round}_start"
  for bt in 200 infinite; do
    for s in $(echo "P2:0x5:2 P4:0x55:4 E2:0x3000:2 E4:0xF000:4 P2E2:0x3005:4 P4E4:0xF055:8 P4E2:0x3055:6" | tr ' ' '\n' | shuf); do
      lbl=${s%%:*}; rest=${s#*:}; mask=${rest%%:*}; th=${rest##*:}
      run "L3_${lbl}_bt${bt}_r${round}" "$mask" "$th" "$bt" 64 3
    done
  done
done

snapshot_load "end"
log "=== DONE pe_sweep ==="
