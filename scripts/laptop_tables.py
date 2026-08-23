"""Heterogeneous-core tables, emitted by make_tables.py when the x86 data is present.

Tags look like:
    L1_<set>_bt<blocktime>_r<round>    core type at a fixed 4 threads
    L2_<set>_bt<blocktime>_r<round>    each set at its natural width
    L3_<set>_bt<blocktime>_r<round>    long-tail test, P-only against P plus E
"""

from __future__ import annotations

import glob
import os
import re
import statistics

# Ordered low to high so the sweep reads left to right. "infinite" sorts last.
BT_ORDER = ["0", "1", "5", "20", "200", "infinite"]

SET_NOTES = {
    "P4": "4 threads, one per Golden Cove core (CPU 0,2,4,6)",
    "E4": "4 threads, four Gracemont cores (CPU 12-15)",
    "MIX4": "4 threads, 2 Golden Cove + 2 Gracemont (CPU 0,2,12,13)",
    "P6": "6 threads, all six Golden Cove cores (CPU 0,2,4,6,8,10)",
    "E8": "8 threads, all eight Gracemont cores (CPU 12-19)",
    "MIX8": "8 threads, 4 Golden Cove + 4 Gracemont (CPU 0,2,4,6,12-15)",
    "P2": "2 threads, two Golden Cove cores",
    "E2": "2 threads, two Gracemont cores",
    "P2E2": "4 threads, 2 Golden Cove + 2 Gracemont",
    "P4E2": "6 threads, 4 Golden Cove + 2 Gracemont",
    "P4E4": "8 threads, 4 Golden Cove + 4 Gracemont",
}


def _bt_key(bt):
    return BT_ORDER.index(bt) if bt in BT_ORDER else len(BT_ORDER)


def _pool(directory, campaign, bench_samples):
    """{(set, blocktime, test): [samples]} for one campaign prefix."""
    pooled = {}
    pattern = re.compile(rf"{campaign}_([A-Za-z0-9]+)_bt([a-z0-9]+)_r(\d+)\.json$")
    for path in sorted(glob.glob(os.path.join(directory, f"{campaign}_*.json"))):
        m = pattern.match(os.path.basename(path))
        if not m:
            continue
        group, bt = m.group(1), m.group(2)
        for label, samples in bench_samples(path):
            pooled.setdefault((group, bt, label), []).extend(samples)
    return pooled


def _sweep_table(pooled, sets, tests, mean_sd, title, note):
    print()
    print("## " + title)
    print()
    print(note)
    for group in sets:
        bts = sorted({k[1] for k in pooled if k[0] == group}, key=_bt_key)
        if not bts:
            continue
        print()
        print(f"**{group}** ({SET_NOTES.get(group, group)})")
        print()
        header = " | ".join(f"{t} tok/s" for t in tests)
        print(f"| KMP_BLOCKTIME | {header} |")
        print("|---:|" + "---:|" * len(tests))
        means = {}
        for bt in bts:
            cells = []
            for t in tests:
                vals = pooled.get((group, bt, t))
                if not vals:
                    cells.append("")
                    continue
                m, sd = mean_sd(vals)
                cells.append(f"{m:.2f} +- {sd:.2f}")
                means.setdefault(t, {})[bt] = m
            print(f"| {bt} | " + " | ".join(cells) + " |")
        for t in tests:
            if t not in means or len(means[t]) < 2:
                continue
            best = max(means[t], key=means[t].get)
            worst = min(means[t], key=means[t].get)
            spread = means[t][best] / means[t][worst]
            print()
            print(
                f"{t}: best KMP_BLOCKTIME={best} ({means[t][best]:.2f}), "
                f"worst={worst} ({means[t][worst]:.2f}), spread {spread:.2f}x"
            )
            # This machine is noisy, so say plainly which comparisons the data
            # actually supports. A gap is only called separated when it clears
            # the combined spread of the two cells it is drawn between.
            b_sd = statistics.pstdev(pooled[(group, best, t)])
            w_sd = statistics.pstdev(pooled[(group, worst, t)])
            gap = means[t][best] - means[t][worst]
            noise = b_sd + w_sd
            verdict = "clears the noise" if gap > noise else "inside the noise"
            print(
                f"    best-worst gap {gap:.2f} against combined spread {noise:.2f}: {verdict}"
            )
            # And whether anything other than the worst setting is distinguishable.
            others = {k: v for k, v in means[t].items() if k != worst}
            if len(others) > 1:
                hi = max(others, key=others.get)
                lo = min(others, key=others.get)
                hi_sd = statistics.pstdev(pooled[(group, hi, t)])
                lo_sd = statistics.pstdev(pooled[(group, lo, t)])
                inner_gap = others[hi] - others[lo]
                inner_noise = hi_sd + lo_sd
                inner = "separated" if inner_gap > inner_noise else "not separated"
                print(
                    f"    excluding {worst}, the remaining settings span "
                    f"{others[lo]:.2f} to {others[hi]:.2f}, gap {inner_gap:.2f} "
                    f"against combined spread {inner_noise:.2f}: {inner}"
                )


def emit_laptop_tables(directory, bench_samples, mean_sd):
    """Print every heterogeneous-core table."""
    print()
    print("---")
    print()
    print("# Heterogeneous cores: Intel i7-12700H")
    print()
    print("Golden Cove and Gracemont cores in the same package. The spin knob here is")
    print("`KMP_BLOCKTIME` (LLVM libomp, milliseconds) rather than `GOMP_SPINCOUNT`")
    print("(GNU libgomp, iterations), so the constants are not comparable with the Pi")
    print("tables. The shape and the direction of the optimum are.")
    print()
    print("Affinity is `llama-bench --cpu-mask` with `--cpu-strict 1`, one thread per")
    print("physical core. This machine was not idle during the sweep, so conditions were")
    print("shuffled within each round and the rounds repeated; treat these as directions")
    print("rather than precise magnitudes.")

    l1 = _pool(directory, "L1", bench_samples)
    if l1:
        tests = sorted({k[2] for k in l1})
        _sweep_table(
            l1,
            ["P4", "E4", "MIX4"],
            tests,
            mean_sd,
            "Table 6. Spin threshold by core type, four threads throughout",
            "Same thread count on each core type, so the only variable is which cores.",
        )

    l2 = _pool(directory, "L2", bench_samples)
    if l2:
        tests = sorted({k[2] for k in l2})
        _sweep_table(
            l2,
            ["P6", "E8", "MIX8"],
            tests,
            mean_sd,
            "Table 7. Spin threshold at each core set's natural width",
            "Every core of that type in use, so thread count differs between rows.",
        )

    l3 = _pool(directory, "L3", bench_samples)
    if l3:
        print()
        print("## Table 8. The long tail: does adding slow cores to a fast set help?")
        print()
        print("If a barrier gates on the slowest thread, adding Gracemont cores to a")
        print("Golden Cove set should return less than those cores are worth on their own.")
        tests = sorted({k[2] for k in l3})
        for bt in sorted({k[1] for k in l3}, key=_bt_key):
            groups = [g for g in ["P2", "E2", "P2E2", "P4", "E4", "P4E2", "P4E4"] if any(k[0] == g and k[1] == bt for k in l3)]
            if not groups:
                continue
            print()
            print(f"**KMP_BLOCKTIME={bt}**")
            print()
            header = " | ".join(f"{t} tok/s" for t in tests)
            print(f"| set | {header} |")
            print("|---|" + "---:|" * len(tests))
            got = {}
            for g in groups:
                cells = []
                for t in tests:
                    vals = l3.get((g, bt, t))
                    if not vals:
                        cells.append("")
                        continue
                    m, sd = mean_sd(vals)
                    cells.append(f"{m:.2f} +- {sd:.2f}")
                    got.setdefault(t, {})[g] = m
                print(f"| {g} ({SET_NOTES.get(g, '')}) | " + " | ".join(cells) + " |")
            # The additivity check, where all three members were measured.
            for t in tests:
                d = got.get(t, {})
                for fast, slow, both, nf, ns in (
                    ("P2", "E2", "P2E2", 2, 2),
                    ("P4", "E4", "P4E4", 4, 4),
                ):
                    if not all(x in d for x in (fast, slow, both)):
                        continue
                    additive = d[fast] + d[slow]
                    print()
                    print(
                        f"{t}: {fast} {d[fast]:.2f} + {slow} {d[slow]:.2f} = {additive:.2f} if perfectly "
                        f"additive; measured {both} = {d[both]:.2f}, which is "
                        f"{d[both]/additive:.2f}x of that and "
                        f"{d[both]/d[fast]:.2f}x of {fast} alone."
                    )
                    # Equal-share prediction. If work is split evenly by thread
                    # index and the barrier waits for the slowest thread, the
                    # mixed set finishes when the slow cores finish their share.
                    v_fast = d[fast] / nf
                    v_slow = d[slow] / ns
                    n = nf + ns
                    t_mixed = (1.0 / n) / v_slow
                    t_fast_only = (1.0 / nf) / v_fast
                    predicted = d[fast] * (t_fast_only / t_mixed)
                    print(
                        f"    per-core rate ratio {v_fast/v_slow:.2f}x. Equal-share static "
                        f"partitioning predicts {predicted:.2f}; measured {d[both]:.2f}, so the "
                        f"model accounts for {predicted/d[both]:.2f} of it."
                    )
