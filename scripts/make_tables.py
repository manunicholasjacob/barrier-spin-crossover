#!/usr/bin/env python3
"""Regenerate every table in the README from the raw measurement files.

Nothing here is hard-coded from an earlier analysis pass. Run it and diff the
output against results/TABLES.md; they should be identical.

    python scripts/make_tables.py > results/TABLES.md
"""

from __future__ import annotations

import glob
import json
import os
import re
import statistics
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PI = os.path.join(REPO, "data", "pi-cortex-a76")
LAPTOP = os.path.join(REPO, "data", "laptop-alderlake")

IDLE = os.path.join(PI, "idle-sweep")
CONTENTION = os.path.join(PI, "contention-sweep")
ENERGY = os.path.join(PI, "energy-and-tightened")
DEFAULT = os.path.join(PI, "default-comparison")


def bench_samples(path):
    """Yield (test_label, [per-rep tok/s]) from one llama-bench JSON file."""
    with open(path) as fh:
        for rec in json.load(fh):
            label = f"pp{rec['n_prompt']}" if rec["n_gen"] == 0 else f"tg{rec['n_gen']}"
            yield label, rec["samples_ts"]


def collect(directory, pattern, key_from_name):
    """Pool per-rep samples across files into {(key, test): [samples]}."""
    pooled = {}
    for path in sorted(glob.glob(os.path.join(directory, pattern))):
        key = key_from_name(os.path.basename(path))
        if key is None:
            continue
        for label, samples in bench_samples(path):
            pooled.setdefault((key, label), []).extend(samples)
    return pooled


def mean_sd(values):
    return statistics.mean(values), (statistics.stdev(values) if len(values) > 1 else 0.0)


def rule(title):
    print()
    print("## " + title)
    print()


# --------------------------------------------------------------------------
# Table 1: idle spin sweep on four identical Cortex-A76 cores
# --------------------------------------------------------------------------
idle = collect(
    IDLE,
    "A_omp_sc*_t4_r*.json",
    lambda n: int(m.group(1)) if (m := re.match(r"A_omp_sc(\d+)_t4_r\d+\.json", n)) else None,
)
idle_spins = sorted({k[0] for k in idle})

rule("Table 1. Barrier spin threshold, four idle Cortex-A76 cores (Raspberry Pi 5)")
print("Six samples per cell, two rounds in randomized order.")
print()
print("| GOMP_SPINCOUNT | pp128 tok/s | tg64 tok/s |")
print("|---:|---:|---:|")
for sc in idle_spins:
    pp = mean_sd(idle[(sc, "pp128")])
    tg = mean_sd(idle[(sc, "tg64")])
    print(f"| {sc} | {pp[0]:.2f} +- {pp[1]:.2f} | {tg[0]:.2f} +- {tg[1]:.2f} |")

idle_pp = [statistics.mean(idle[(sc, "pp128")]) for sc in idle_spins]
idle_tg = [statistics.mean(idle[(sc, "tg64")]) for sc in idle_spins]
print()
print(f"Prefill spread across seven decades of spin count: {max(idle_pp)/min(idle_pp):.3f}x")
print(f"Decode spread across seven decades of spin count:  {max(idle_tg)/min(idle_tg):.3f}x")

# --------------------------------------------------------------------------
# Table 2: same sweep under external CPU contention
# --------------------------------------------------------------------------
cont = collect(
    ENERGY,
    "H_hog2_sc*_r*.json",
    lambda n: int(m.group(1)) if (m := re.match(r"H_hog2_sc(\d+)_r\d+\.json", n)) else None,
)
cont_spins = sorted({k[0] for k in cont})

rule("Table 2. Same sweep, four threads competing with two external CPU hogs")
print("Four samples per cell, two rounds.")
print()
print("| GOMP_SPINCOUNT | pp128 tok/s | tg32 tok/s |")
print("|---:|---:|---:|")
for sc in cont_spins:
    pp = mean_sd(cont[(sc, "pp128")])
    tg = mean_sd(cont[(sc, "tg32")])
    print(f"| {sc} | {pp[0]:.2f} +- {pp[1]:.2f} | {tg[0]:.2f} +- {tg[1]:.2f} |")

cont_tg = [statistics.mean(cont[(sc, "tg32")]) for sc in cont_spins]
print()
print(f"Decode spread under contention: {max(cont_tg)/min(cont_tg):.2f}x")

# --------------------------------------------------------------------------
# Table 3: the two regimes side by side, each normalized to its own best
# --------------------------------------------------------------------------
idle_by = dict(zip(idle_spins, idle_tg))
cont_by = dict(zip(cont_spins, cont_tg))
common = sorted(set(idle_by) & set(cont_by))
idle_best, cont_best = max(idle_by.values()), max(cont_by.values())

rule("Table 3. The loss is asymmetric (decode, each column relative to its own best)")
print("| GOMP_SPINCOUNT | idle | contended | worst case |")
print("|---:|---:|---:|---:|")
for sc in common:
    i, c = idle_by[sc] / idle_best, cont_by[sc] / cont_best
    print(f"| {sc} | {i:.3f}x | {c:.3f}x | {min(i, c):.3f}x |")

best_const = max(common, key=lambda s: min(idle_by[s] / idle_best, cont_by[s] / cont_best))
worst_case = min(idle_by[best_const] / idle_best, cont_by[best_const] / cont_best)
lo, hi = min(common), max(common)
print()
print(f"Best single constant across both regimes: {best_const}, worst case {worst_case:.3f}x")
print(f"Cost of spinning too little (spincount {lo}): idle {idle_by[lo]/idle_best:.3f}x, contended {cont_by[lo]/cont_best:.3f}x")
print(f"Cost of spinning too much (spincount {hi}): idle {idle_by[hi]/idle_best:.3f}x, contended {cont_by[hi]/cont_best:.3f}x")

# --------------------------------------------------------------------------
# Table 4: where the libgomp default actually sits, measured
# --------------------------------------------------------------------------
dflt = collect(
    DEFAULT,
    "D_*.json",
    lambda n: (m.group(1), m.group(2)) if (m := re.match(r"D_(idle|hog2)_(\w+?)_r\d+\.json", n)) else None,
)

rule("Table 4. Where the libgomp default sits (measured, not assumed)")
for cond, test, label in (
    ("idle", "tg64", "four threads, idle"),
    ("hog2", "tg32", "four threads plus two CPU hogs"),
):
    rows = {k[0][1]: v for k, v in dflt.items() if k[0][0] == cond and k[1] == test}
    if not rows:
        continue
    means = {s: statistics.mean(v) for s, v in rows.items()}
    best = max(means.values())
    print()
    print(f"**{label} ({test})**")
    print()
    print("| setting | tok/s | of best |")
    print("|---|---:|---:|")
    for s in sorted(means, key=lambda x: -means[x]):
        sd = statistics.stdev(rows[s]) if len(rows[s]) > 1 else 0.0
        print(f"| {s} | {means[s]:.2f} +- {sd:.2f} | {means[s]/best:.3f}x |")
    if "UNSET" in means and "sc300000" in means:
        print()
        print(f"UNSET / sc300000 = {means['UNSET']/means['sc300000']:.4f}")

# --------------------------------------------------------------------------
# Table 5: energy
# --------------------------------------------------------------------------
windows = {}
wpath = os.path.join(ENERGY, "windows.jsonl")
if os.path.exists(wpath):
    for line in open(wpath):
        rec = json.loads(line)
        windows[rec["tag"]] = rec


def mean_board_power(tag, head=2.0, tail=1.0):
    """Mean total board power over the bench window, trimming load-in and load-out."""
    win = windows.get(tag)
    path = os.path.join(ENERGY, f"{tag}.power.jsonl")
    if win is None or not os.path.exists(path):
        return None, 0
    lo, hi = win["bench_start"] + head, win["bench_end"] - tail
    vals = []
    for line in open(path):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if "total_w" in rec and lo <= rec["t"] <= hi:
            vals.append(rec["total_w"])
    return (statistics.mean(vals), len(vals)) if vals else (None, 0)


rule("Table 5. Energy")
print("Throughput comes from clean runs. Power comes from separate sampled runs at")
print("10 Hz, because the PMIC sampler costs enough CPU on four cores to move the")
print("throughput number. The two are never taken from the same run.")
for prefix, ngen, label in (
    ("G1_idle", 256, "four threads, idle"),
    ("G2_hog2", 64, "four threads plus two CPU hogs"),
):
    rows = []
    for path in sorted(glob.glob(os.path.join(ENERGY, f"{prefix}_sc*_clean.json"))):
        sc = int(re.search(r"_sc(\d+)_clean\.json$", path).group(1))
        tps = None
        for label_t, samples in bench_samples(path):
            if label_t == f"tg{ngen}":
                tps = statistics.mean(samples)
        watts, n = mean_board_power(f"{prefix}_sc{sc}")
        if tps and watts:
            rows.append((sc, tps, watts, watts / tps, n))
    if not rows:
        continue
    rows.sort()
    print()
    print(f"**{label}**")
    print()
    print("| GOMP_SPINCOUNT | tok/s | board W | J/token | power samples |")
    print("|---:|---:|---:|---:|---:|")
    for sc, tps, watts, jt, n in rows:
        print(f"| {sc} | {tps:.2f} | {watts:.3f} | {jt:.4f} | {n} |")
    best = min(rows, key=lambda r: r[3])
    worst = max(rows, key=lambda r: r[3])
    print()
    print(f"Energy per token spread: {worst[3]/best[3]:.2f}x")
    direction = "less" if worst[2] < best[2] else "more"
    print(
        f"At the worst setting the board draws {worst[2]:.3f} W against {best[2]:.3f} W "
        f"at the best, so it draws {direction} power and still costs "
        f"{worst[3]/best[3]:.1f}x the energy per token."
    )

# --------------------------------------------------------------------------
# Tables 6+: heterogeneous cores, if that data is present
# --------------------------------------------------------------------------
LAPTOP_RAW = os.path.join(LAPTOP, "spin-sweep")
RATIO_RAW = os.path.join(LAPTOP, "ratio-sweep")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if os.path.isdir(LAPTOP_RAW) and glob.glob(os.path.join(LAPTOP_RAW, "L1_*.json")):
    from laptop_tables import emit_laptop_tables  # noqa: E402

    emit_laptop_tables(LAPTOP_RAW, bench_samples, mean_sd)
else:
    print()
    print("_Heterogeneous-core tables are emitted when data/laptop-alderlake/spin-sweep is present._")

if os.path.isdir(RATIO_RAW) and glob.glob(os.path.join(RATIO_RAW, "M1_*.json")):
    from ratio_tables import emit_model_size_table, emit_ratio_tables  # noqa: E402

    emit_ratio_tables(RATIO_RAW, bench_samples)
    emit_model_size_table(RATIO_RAW, bench_samples)
