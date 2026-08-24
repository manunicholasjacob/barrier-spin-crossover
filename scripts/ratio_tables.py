"""Core-count ratio tables, emitted by make_tables.py when the ratio sweep is present.

Round two only ever measured 1:1 mixes of fast and slow cores, where the
equal-share model always predicts a loss. This campaign varies the number of
slow cores against a fixed pair of fast ones, because the model makes a
counterintuitive prediction there:

    mixed / fast-only = ((nP + nE) / nP) * (vE / vP)

The ratio RISES with nE. So the model says adding more slow cores should help,
and past a threshold the mixed set should beat the fast cores on their own. That
is a sign change, which is a much sharper test than another loss.

Tags: M1_<set>_bt<blocktime>_r<round>
"""

from __future__ import annotations

import glob
import json
import os
import re
import statistics

# mixed label -> (fast-only set, nP, slow-only set, nE)
CASES = [
    ("P2E2", "P2", 2, "E2", 2),
    ("P2E4", "P2", 2, "E4", 4),
    ("P2E6", "P2", 2, "E6", 6),
    ("P2E8", "P2", 2, "E8", 8),
    ("P4E4", "P4", 4, "E4", 4),
]

# A cell whose scatter is this large a fraction of its mean cannot carry a
# conclusion, and the tables say so rather than letting a reader average by eye.
NOISY_FRACTION = 0.15


def _pool(directory, bench_samples, campaign="M1"):
    pooled = {}
    pattern = re.compile(rf"{campaign}_([A-Za-z0-9]+)_bt([a-z0-9]+)_r(\d+)\.json$")
    for path in sorted(glob.glob(os.path.join(directory, f"{campaign}_*.json"))):
        m = pattern.match(os.path.basename(path))
        if not m:
            continue
        for label, samples in bench_samples(path):
            pooled.setdefault((m.group(1), m.group(2), label), []).extend(samples)
    return pooled


def _stat(pooled, group, bt, test):
    vals = pooled.get((group, bt, test))
    if not vals:
        return None, 0.0
    return statistics.mean(vals), (statistics.pstdev(vals) if len(vals) > 1 else 0.0)


def emit_ratio_tables(directory, bench_samples):
    """Print the core-count ratio tables."""
    pooled = _pool(directory, bench_samples)
    if not pooled:
        return

    print()
    print("---")
    print()
    print("# Core-count ratio: does the equal-share model predict a sign change?")
    print()
    print("Fast cores held at two Golden Cove; slow cores varied from two to eight")
    print("Gracemont. The model predicts `mixed / fast-only = ((nP + nE) / nP) * (vE / vP)`,")
    print("which RISES with the number of slow cores and crosses 1.0. `vP` comes from the")
    print("fast-only set and `vE` from the slow-only set at the SAME core count, so both")
    print("carry the same bandwidth contention.")

    tests = sorted({k[2] for k in pooled})
    bts = sorted({k[1] for k in pooled})

    for test in tests:
        for bt in bts:
            rows = []
            for mixed, fast, npc, slow, nec in CASES:
                mm, msd = _stat(pooled, mixed, bt, test)
                fm, fsd = _stat(pooled, fast, bt, test)
                sm, ssd = _stat(pooled, slow, bt, test)
                if not (mm and fm and sm):
                    continue
                v_fast, v_slow = fm / npc, sm / nec
                predicted = fm * ((npc + nec) / npc) * (v_slow / v_fast)
                noisy = max(msd / mm, ssd / sm) > NOISY_FRACTION
                rows.append(
                    (mixed, fast, npc, slow, nec, fm, fsd, sm, ssd, mm, msd,
                     v_fast / v_slow, predicted, noisy)
                )
            if not rows:
                continue

            print()
            print(f"## {test}, KMP_BLOCKTIME={bt}")
            print()
            print("| mixed set | fast-only | slow-only | mixed measured | per-core ratio | predicted | model / measured | |")
            print("|---|---:|---:|---:|---:|---:|---:|---|")
            for (mixed, fast, npc, slow, nec, fm, fsd, sm, ssd, mm, msd,
                 ratio, predicted, noisy) in rows:
                flag = "noisy" if noisy else ""
                print(
                    f"| {mixed} | {fm:.2f} +- {fsd:.2f} | {sm:.2f} +- {ssd:.2f} | "
                    f"{mm:.2f} +- {msd:.2f} | {ratio:.2f}x | {predicted:.2f} | "
                    f"{predicted / mm:.2f} | {flag} |"
                )

            print()
            print("The sign-change test, two fast cores throughout:")
            print()
            print("| slow cores | measured mixed/fast | predicted | crosses 1.0 | |")
            print("|---:|---:|---:|---|---|")
            for (mixed, fast, npc, slow, nec, fm, fsd, sm, ssd, mm, msd,
                 ratio, predicted, noisy) in rows:
                if fast != "P2":
                    continue
                measured_ratio = mm / fm
                pred_ratio = predicted / fm
                crossed = "yes" if measured_ratio > 1.0 else "no"
                flag = "noisy, not a verdict" if noisy else ""
                print(
                    f"| {nec} | {measured_ratio:.3f}x | {pred_ratio:.3f}x | "
                    f"{crossed} | {flag} |"
                )

            clean = [r for r in rows if r[1] == "P2" and not r[13]]
            if len(clean) >= 2:
                order = sorted(clean, key=lambda r: r[4])
                measured_seq = [r[9] / r[5] for r in order]
                rising = all(b >= a for a, b in zip(measured_seq, measured_seq[1:]))
                print()
                print(
                    f"Across the cells that are not flagged noisy, the measured ratio "
                    f"{'rises monotonically with the number of slow cores, as the model requires' if rising else 'does NOT rise monotonically, which the model requires'}: "
                    + ", ".join(f"{r[4]}E {r[9] / r[5]:.3f}x" for r in order)
                    + "."
                )

def emit_model_size_table(directory, bench_samples):
    """M3: the same core mix on a larger model, where the regime changes."""
    pooled = _pool(directory, bench_samples, campaign="M3")
    if not pooled:
        return

    print()
    print("## The same mix on a larger model, where the model stops holding")
    print()
    print("Everything above is qwen0.5b. Repeating the 2P+4E comparison on qwen1.5b,")
    print("whose working set is larger and whose work is correspondingly more")
    print("bandwidth-bound, inverts the result.")

    tests = sorted({k[2] for k in pooled})
    for test in tests:
        fm, fsd = _stat(pooled, "P2", "200", test)
        sm, ssd = _stat(pooled, "E4", "200", test)
        mm, msd = _stat(pooled, "P2E4", "200", test)
        if not (fm and sm and mm):
            continue
        v_fast, v_slow = fm / 2, sm / 4
        predicted = fm * (6 / 2) * (v_slow / v_fast)
        gap, noise = mm - fm, msd + fsd
        print()
        print(f"**{test}, qwen1.5b, KMP_BLOCKTIME=200**")
        print()
        print("| set | tok/s |")
        print("|---|---:|")
        print(f"| 2 Golden Cove | {fm:.2f} +- {fsd:.2f} |")
        print(f"| 4 Gracemont | {sm:.2f} +- {ssd:.2f} |")
        print(f"| 2 Golden Cove + 4 Gracemont | {mm:.2f} +- {msd:.2f} |")
        print()
        print(
            f"Measured mixed/fast-only {mm / fm:.3f}x against a predicted "
            f"{predicted / fm:.3f}x, so the model accounts for {predicted / mm:.2f} of it. "
            f"The mixed set beats the fast pair by {gap:.2f} tok/s against a combined "
            f"spread of {noise:.2f}, so "
            f"{'that gap is real' if gap > noise else 'that gap is inside the noise'}."
        )
