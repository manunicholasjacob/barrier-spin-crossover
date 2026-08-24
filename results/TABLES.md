
## Table 1. Barrier spin threshold, four idle Cortex-A76 cores (Raspberry Pi 5)

Six samples per cell, two rounds in randomized order.

| GOMP_SPINCOUNT | pp128 tok/s | tg64 tok/s |
|---:|---:|---:|
| 0 | 91.64 +- 0.19 | 25.06 +- 0.08 |
| 1000 | 91.83 +- 0.05 | 25.24 +- 0.02 |
| 10000 | 91.75 +- 0.04 | 26.42 +- 0.03 |
| 100000 | 91.91 +- 0.04 | 27.04 +- 0.04 |
| 300000 | 91.91 +- 0.15 | 27.07 +- 0.02 |
| 1000000 | 91.96 +- 0.06 | 27.12 +- 0.02 |
| 10000000 | 91.88 +- 0.16 | 27.09 +- 0.03 |

Prefill spread across seven decades of spin count: 1.003x
Decode spread across seven decades of spin count:  1.082x

## Table 2. Same sweep, four threads competing with two external CPU hogs

Four samples per cell, two rounds.

| GOMP_SPINCOUNT | pp128 tok/s | tg32 tok/s |
|---:|---:|---:|
| 0 | 48.39 +- 0.49 | 20.60 +- 0.51 |
| 1000 | 48.59 +- 0.51 | 20.41 +- 0.25 |
| 10000 | 49.24 +- 0.83 | 19.18 +- 0.42 |
| 30000 | 49.65 +- 0.29 | 15.60 +- 0.31 |
| 100000 | 47.58 +- 0.26 | 8.99 +- 0.19 |
| 300000 | 45.30 +- 0.48 | 4.32 +- 0.05 |
| 1000000 | 40.31 +- 0.77 | 1.54 +- 0.00 |

Decode spread under contention: 13.34x

## Table 3. The loss is asymmetric (decode, each column relative to its own best)

| GOMP_SPINCOUNT | idle | contended | worst case |
|---:|---:|---:|---:|
| 0 | 0.924x | 1.000x | 0.924x |
| 1000 | 0.931x | 0.991x | 0.931x |
| 10000 | 0.974x | 0.931x | 0.931x |
| 100000 | 0.997x | 0.436x | 0.436x |
| 300000 | 0.998x | 0.210x | 0.210x |
| 1000000 | 1.000x | 0.075x | 0.075x |

Best single constant across both regimes: 10000, worst case 0.931x
Cost of spinning too little (spincount 0): idle 0.924x, contended 1.000x
Cost of spinning too much (spincount 1000000): idle 1.000x, contended 0.075x

## Table 4. Where the libgomp default sits (measured, not assumed)


**four threads, idle (tg64)**

| setting | tok/s | of best |
|---|---:|---:|
| UNSET | 27.04 +- 0.02 | 1.000x |
| sc300000 | 27.03 +- 0.02 | 1.000x |
| sc1000 | 25.22 +- 0.09 | 0.933x |

UNSET / sc300000 = 1.0003

**four threads plus two CPU hogs (tg32)**

| setting | tok/s | of best |
|---|---:|---:|
| sc0 | 20.62 +- 0.58 | 1.000x |
| passive | 20.54 +- 0.23 | 0.996x |
| UNSET | 4.31 +- 0.04 | 0.209x |
| sc300000 | 4.31 +- 0.03 | 0.209x |
| active | 1.96 +- 2.76 | 0.095x |

UNSET / sc300000 = 1.0007

## Table 5. Energy

Throughput comes from clean runs. Power comes from separate sampled runs at
10 Hz, because the PMIC sampler costs enough CPU on four cores to move the
throughput number. The two are never taken from the same run.

**four threads, idle**

| GOMP_SPINCOUNT | tok/s | board W | J/token | power samples |
|---:|---:|---:|---:|---:|
| 0 | 24.69 | 6.455 | 0.2614 | 233 |
| 10000 | 25.68 | 6.975 | 0.2716 | 224 |
| 100000 | 26.73 | 6.690 | 0.2502 | 216 |
| 1000000 | 26.78 | 6.849 | 0.2557 | 215 |

Energy per token spread: 1.09x
At the worst setting the board draws 6.975 W against 6.690 W at the best, so it draws more power and still costs 1.1x the energy per token.

**four threads plus two CPU hogs**

| GOMP_SPINCOUNT | tok/s | board W | J/token | power samples |
|---:|---:|---:|---:|---:|
| 0 | 21.10 | 6.626 | 0.3140 | 123 |
| 10000 | 18.82 | 6.756 | 0.3590 | 126 |
| 100000 | 9.11 | 6.349 | 0.6970 | 199 |
| 1000000 | 1.53 | 5.434 | 3.5432 | 903 |

Energy per token spread: 11.29x
At the worst setting the board draws 5.434 W against 6.626 W at the best, so it draws less power and still costs 11.3x the energy per token.

---

# Heterogeneous cores: Intel i7-12700H

Golden Cove and Gracemont cores in the same package. The spin knob here is
`KMP_BLOCKTIME` (LLVM libomp, milliseconds) rather than `GOMP_SPINCOUNT`
(GNU libgomp, iterations), so the constants are not comparable with the Pi
tables. The shape and the direction of the optimum are.

Affinity is `llama-bench --cpu-mask` with `--cpu-strict 1`, one thread per
physical core. This machine was not idle during the sweep, so conditions were
shuffled within each round and the rounds repeated; treat these as directions
rather than precise magnitudes.

## Table 6. Spin threshold by core type, four threads throughout

Same thread count on each core type, so the only variable is which cores.

**P4** (4 threads, one per Golden Cove core (CPU 0,2,4,6))

| KMP_BLOCKTIME | pp128 tok/s | tg64 tok/s |
|---:|---:|---:|
| 0 | 182.48 +- 37.58 | 22.16 +- 3.90 |
| 1 | 208.33 +- 22.30 | 71.87 +- 5.89 |
| 5 | 196.44 +- 39.38 | 68.03 +- 15.16 |
| 20 | 177.63 +- 66.76 | 58.44 +- 24.14 |
| 200 | 193.85 +- 39.66 | 61.04 +- 23.13 |
| infinite | 214.22 +- 14.87 | 74.89 +- 4.42 |

pp128: best KMP_BLOCKTIME=infinite (214.22), worst=20 (177.63), spread 1.21x
    best-worst gap 36.59 against combined spread 76.95: inside the noise
    excluding 20, the remaining settings span 182.48 to 214.22, gap 31.74 against combined spread 49.45: not separated

tg64: best KMP_BLOCKTIME=infinite (74.89), worst=0 (22.16), spread 3.38x
    best-worst gap 52.73 against combined spread 7.84: clears the noise
    excluding 0, the remaining settings span 58.44 to 74.89, gap 16.45 against combined spread 26.92: not separated

**E4** (4 threads, four Gracemont cores (CPU 12-15))

| KMP_BLOCKTIME | pp128 tok/s | tg64 tok/s |
|---:|---:|---:|
| 0 | 64.53 +- 6.99 | 12.84 +- 1.21 |
| 1 | 58.36 +- 7.06 | 21.92 +- 2.11 |
| 5 | 53.31 +- 10.43 | 26.18 +- 9.39 |
| 20 | 55.73 +- 8.91 | 21.38 +- 5.65 |
| 200 | 58.86 +- 5.50 | 20.16 +- 3.15 |
| infinite | 59.30 +- 4.67 | 24.62 +- 6.12 |

pp128: best KMP_BLOCKTIME=0 (64.53), worst=5 (53.31), spread 1.21x
    best-worst gap 11.22 against combined spread 16.43: inside the noise
    excluding 5, the remaining settings span 55.73 to 64.53, gap 8.80 against combined spread 14.99: not separated

tg64: best KMP_BLOCKTIME=5 (26.18), worst=0 (12.84), spread 2.04x
    best-worst gap 13.33 against combined spread 9.99: clears the noise
    excluding 0, the remaining settings span 20.16 to 26.18, gap 6.02 against combined spread 11.81: not separated

**MIX4** (4 threads, 2 Golden Cove + 2 Gracemont (CPU 0,2,12,13))

| KMP_BLOCKTIME | pp128 tok/s | tg64 tok/s |
|---:|---:|---:|
| 0 | 72.08 +- 15.88 | 15.05 +- 3.99 |
| 1 | 66.29 +- 4.71 | 42.08 +- 5.81 |
| 5 | 70.94 +- 3.03 | 43.79 +- 4.07 |
| 20 | 69.82 +- 5.18 | 41.53 +- 3.41 |
| 200 | 68.93 +- 4.93 | 43.41 +- 1.28 |
| infinite | 72.71 +- 2.08 | 42.17 +- 3.23 |

pp128: best KMP_BLOCKTIME=infinite (72.71), worst=1 (66.29), spread 1.10x
    best-worst gap 6.42 against combined spread 6.40: clears the noise
    excluding 1, the remaining settings span 68.93 to 72.71, gap 3.78 against combined spread 6.61: not separated

tg64: best KMP_BLOCKTIME=5 (43.79), worst=0 (15.05), spread 2.91x
    best-worst gap 28.74 against combined spread 7.60: clears the noise
    excluding 0, the remaining settings span 41.53 to 43.79, gap 2.26 against combined spread 7.04: not separated

## Table 7. Spin threshold at each core set's natural width

Every core of that type in use, so thread count differs between rows.

**P6** (6 threads, all six Golden Cove cores (CPU 0,2,4,6,8,10))

| KMP_BLOCKTIME | pp128 tok/s | tg64 tok/s |
|---:|---:|---:|
| 0 | 175.92 +- 51.63 | 14.28 +- 3.04 |
| 1 | 297.77 +- 25.46 | 94.17 +- 6.38 |
| 5 | 322.49 +- 7.80 | 97.03 +- 2.34 |
| 20 | 327.25 +- 7.44 | 96.08 +- 2.56 |
| 200 | 295.09 +- 25.43 | 90.78 +- 4.81 |
| infinite | 313.19 +- 13.17 | 93.65 +- 6.79 |

pp128: best KMP_BLOCKTIME=20 (327.25), worst=0 (175.92), spread 1.86x
    best-worst gap 151.34 against combined spread 53.92: clears the noise
    excluding 0, the remaining settings span 295.09 to 327.25, gap 32.16 against combined spread 30.01: separated

tg64: best KMP_BLOCKTIME=5 (97.03), worst=0 (14.28), spread 6.79x
    best-worst gap 82.74 against combined spread 4.91: clears the noise
    excluding 0, the remaining settings span 90.78 to 97.03, gap 6.25 against combined spread 6.52: not separated

**E8** (8 threads, all eight Gracemont cores (CPU 12-19))

| KMP_BLOCKTIME | pp128 tok/s | tg64 tok/s |
|---:|---:|---:|
| 0 | 98.82 +- 13.65 | 7.01 +- 1.09 |
| 1 | 46.33 +- 30.37 | 15.75 +- 27.21 |
| 5 | 53.94 +- 2.98 | 19.02 +- 17.24 |
| 20 | 64.80 +- 13.35 | 20.05 +- 11.49 |
| 200 | 70.32 +- 11.87 | 14.15 +- 7.21 |
| infinite | 73.59 +- 18.58 | 22.22 +- 10.18 |

pp128: best KMP_BLOCKTIME=0 (98.82), worst=1 (46.33), spread 2.13x
    best-worst gap 52.49 against combined spread 40.19: clears the noise
    excluding 1, the remaining settings span 53.94 to 98.82, gap 44.88 against combined spread 15.18: separated

tg64: best KMP_BLOCKTIME=infinite (22.22), worst=0 (7.01), spread 3.17x
    best-worst gap 15.21 against combined spread 10.28: clears the noise
    excluding 0, the remaining settings span 14.15 to 22.22, gap 8.06 against combined spread 15.87: not separated

**MIX8** (8 threads, 4 Golden Cove + 4 Gracemont (CPU 0,2,4,6,12-15))

| KMP_BLOCKTIME | pp128 tok/s | tg64 tok/s |
|---:|---:|---:|
| 0 | 99.41 +- 5.02 | 4.89 +- 1.17 |
| 1 | 121.48 +- 9.08 | 64.82 +- 8.59 |
| 5 | 122.41 +- 5.83 | 69.17 +- 7.52 |
| 20 | 129.76 +- 19.78 | 56.20 +- 11.98 |
| 200 | 120.60 +- 12.24 | 51.25 +- 13.37 |
| infinite | 127.20 +- 14.23 | 65.55 +- 7.12 |

pp128: best KMP_BLOCKTIME=20 (129.76), worst=0 (99.41), spread 1.31x
    best-worst gap 30.35 against combined spread 22.64: clears the noise
    excluding 0, the remaining settings span 120.60 to 129.76, gap 9.15 against combined spread 29.23: not separated

tg64: best KMP_BLOCKTIME=5 (69.17), worst=0 (4.89), spread 14.15x
    best-worst gap 64.29 against combined spread 7.93: clears the noise
    excluding 0, the remaining settings span 51.25 to 69.17, gap 17.92 against combined spread 19.07: not separated

## Table 8. The long tail: does adding slow cores to a fast set help?

If a barrier gates on the slowest thread, adding Gracemont cores to a
Golden Cove set should return less than those cores are worth on their own.

**KMP_BLOCKTIME=200**

| set | pp128 tok/s | tg64 tok/s |
|---|---:|---:|
| P2 (2 threads, two Golden Cove cores) | 115.04 +- 1.30 | 45.26 +- 0.44 |
| E2 (2 threads, two Gracemont cores) | 33.25 +- 0.50 | 16.07 +- 0.35 |
| P2E2 (4 threads, 2 Golden Cove + 2 Gracemont) | 73.25 +- 1.83 | 43.03 +- 3.79 |
| P4 (4 threads, one per Golden Cove core (CPU 0,2,4,6)) | 224.99 +- 5.54 | 77.63 +- 3.22 |
| E4 (4 threads, four Gracemont cores (CPU 12-15)) | 63.24 +- 3.37 | 23.45 +- 2.11 |
| P4E2 (6 threads, 4 Golden Cove + 2 Gracemont) | 103.18 +- 8.59 | 63.55 +- 3.98 |
| P4E4 (8 threads, 4 Golden Cove + 4 Gracemont) | 140.43 +- 6.61 | 59.89 +- 16.48 |

pp128: P2 115.04 + E2 33.25 = 148.29 if perfectly additive; measured P2E2 = 73.25, which is 0.49x of that and 0.64x of P2 alone.
    per-core rate ratio 3.46x. Equal-share static partitioning predicts 66.50; measured 73.25, so the model accounts for 0.91 of it.

pp128: P4 224.99 + E4 63.24 = 288.23 if perfectly additive; measured P4E4 = 140.43, which is 0.49x of that and 0.62x of P4 alone.
    per-core rate ratio 3.56x. Equal-share static partitioning predicts 126.47; measured 140.43, so the model accounts for 0.90 of it.

tg64: P2 45.26 + E2 16.07 = 61.33 if perfectly additive; measured P2E2 = 43.03, which is 0.70x of that and 0.95x of P2 alone.
    per-core rate ratio 2.82x. Equal-share static partitioning predicts 32.14; measured 43.03, so the model accounts for 0.75 of it.

tg64: P4 77.63 + E4 23.45 = 101.09 if perfectly additive; measured P4E4 = 59.89, which is 0.59x of that and 0.77x of P4 alone.
    per-core rate ratio 3.31x. Equal-share static partitioning predicts 46.90; measured 59.89, so the model accounts for 0.78 of it.

**KMP_BLOCKTIME=infinite**

| set | pp128 tok/s | tg64 tok/s |
|---|---:|---:|
| P2 (2 threads, two Golden Cove cores) | 115.09 +- 0.44 | 44.94 +- 0.80 |
| E2 (2 threads, two Gracemont cores) | 32.84 +- 0.54 | 15.33 +- 0.52 |
| P2E2 (4 threads, 2 Golden Cove + 2 Gracemont) | 72.29 +- 2.51 | 43.59 +- 2.12 |
| P4 (4 threads, one per Golden Cove core (CPU 0,2,4,6)) | 224.72 +- 4.08 | 77.84 +- 3.10 |
| E4 (4 threads, four Gracemont cores (CPU 12-15)) | 58.51 +- 6.76 | 21.84 +- 3.18 |
| P4E2 (6 threads, 4 Golden Cove + 2 Gracemont) | 107.98 +- 3.66 | 65.50 +- 3.74 |
| P4E4 (8 threads, 4 Golden Cove + 4 Gracemont) | 123.42 +- 13.34 | 66.82 +- 7.39 |

pp128: P2 115.09 + E2 32.84 = 147.93 if perfectly additive; measured P2E2 = 72.29, which is 0.49x of that and 0.63x of P2 alone.
    per-core rate ratio 3.50x. Equal-share static partitioning predicts 65.69; measured 72.29, so the model accounts for 0.91 of it.

pp128: P4 224.72 + E4 58.51 = 283.23 if perfectly additive; measured P4E4 = 123.42, which is 0.44x of that and 0.55x of P4 alone.
    per-core rate ratio 3.84x. Equal-share static partitioning predicts 117.02; measured 123.42, so the model accounts for 0.95 of it.

tg64: P2 44.94 + E2 15.33 = 60.26 if perfectly additive; measured P2E2 = 43.59, which is 0.72x of that and 0.97x of P2 alone.
    per-core rate ratio 2.93x. Equal-share static partitioning predicts 30.65; measured 43.59, so the model accounts for 0.70 of it.

tg64: P4 77.84 + E4 21.84 = 99.69 if perfectly additive; measured P4E4 = 66.82, which is 0.67x of that and 0.86x of P4 alone.
    per-core rate ratio 3.56x. Equal-share static partitioning predicts 43.69; measured 66.82, so the model accounts for 0.65 of it.

---

# Core-count ratio: does the equal-share model predict a sign change?

Fast cores held at two Golden Cove; slow cores varied from two to eight
Gracemont. The model predicts `mixed / fast-only = ((nP + nE) / nP) * (vE / vP)`,
which RISES with the number of slow cores and crosses 1.0. `vP` comes from the
fast-only set and `vE` from the slow-only set at the SAME core count, so both
carry the same bandwidth contention.

## pp128, KMP_BLOCKTIME=200

| mixed set | fast-only | slow-only | mixed measured | per-core ratio | predicted | model / measured | |
|---|---:|---:|---:|---:|---:|---:|---|
| P2E2 | 112.80 +- 2.36 | 32.48 +- 2.04 | 73.33 +- 2.35 | 3.47x | 64.97 | 0.89 |  |
| P2E4 | 112.80 +- 2.36 | 54.97 +- 7.32 | 100.02 +- 10.02 | 4.10x | 82.46 | 0.82 |  |
| P2E6 | 112.80 +- 2.36 | 84.89 +- 7.33 | 123.47 +- 13.69 | 3.99x | 113.18 | 0.92 |  |
| P2E8 | 112.80 +- 2.36 | 78.96 +- 19.30 | 66.04 +- 13.48 | 5.71x | 98.70 | 1.49 | noisy |
| P4E4 | 218.49 +- 7.97 | 54.97 +- 7.32 | 136.22 +- 4.80 | 3.97x | 109.95 | 0.81 |  |

The sign-change test, two fast cores throughout:

| slow cores | measured mixed/fast | predicted | crosses 1.0 | |
|---:|---:|---:|---|---|
| 2 | 0.650x | 0.576x | no |  |
| 4 | 0.887x | 0.731x | no |  |
| 6 | 1.095x | 1.003x | yes |  |
| 8 | 0.585x | 0.875x | no | noisy, not a verdict |

Across the cells that are not flagged noisy, the measured ratio rises monotonically with the number of slow cores, as the model requires: 2E 0.650x, 4E 0.887x, 6E 1.095x.

## pp128, KMP_BLOCKTIME=infinite

| mixed set | fast-only | slow-only | mixed measured | per-core ratio | predicted | model / measured | |
|---|---:|---:|---:|---:|---:|---:|---|
| P2E2 | 111.54 +- 2.09 | 32.73 +- 1.07 | 70.76 +- 3.91 | 3.41x | 65.46 | 0.93 |  |
| P2E4 | 111.54 +- 2.09 | 63.22 +- 2.96 | 99.26 +- 7.03 | 3.53x | 94.83 | 0.96 |  |
| P2E6 | 111.54 +- 2.09 | 89.81 +- 8.03 | 110.61 +- 17.66 | 3.73x | 119.74 | 1.08 | noisy |
| P2E8 | 111.54 +- 2.09 | 61.87 +- 26.29 | 88.04 +- 31.28 | 7.21x | 77.33 | 0.88 | noisy |
| P4E4 | 216.07 +- 10.19 | 63.22 +- 2.96 | 137.50 +- 19.56 | 3.42x | 126.45 | 0.92 |  |

The sign-change test, two fast cores throughout:

| slow cores | measured mixed/fast | predicted | crosses 1.0 | |
|---:|---:|---:|---|---|
| 2 | 0.634x | 0.587x | no |  |
| 4 | 0.890x | 0.850x | no |  |
| 6 | 0.992x | 1.073x | no | noisy, not a verdict |
| 8 | 0.789x | 0.693x | no | noisy, not a verdict |

Across the cells that are not flagged noisy, the measured ratio rises monotonically with the number of slow cores, as the model requires: 2E 0.634x, 4E 0.890x.

## tg64, KMP_BLOCKTIME=200

| mixed set | fast-only | slow-only | mixed measured | per-core ratio | predicted | model / measured | |
|---|---:|---:|---:|---:|---:|---:|---|
| P2E2 | 42.79 +- 2.86 | 15.00 +- 0.52 | 44.36 +- 1.41 | 2.85x | 30.00 | 0.68 |  |
| P2E4 | 42.79 +- 2.86 | 24.67 +- 1.39 | 34.94 +- 13.80 | 3.47x | 37.01 | 1.06 | noisy |
| P2E6 | 42.79 +- 2.86 | 27.87 +- 6.29 | 43.55 +- 12.53 | 4.61x | 37.15 | 0.85 | noisy |
| P2E8 | 42.79 +- 2.86 | 18.12 +- 12.83 | 23.34 +- 19.37 | 9.45x | 22.65 | 0.97 | noisy |
| P4E4 | 74.58 +- 5.39 | 24.67 +- 1.39 | 62.12 +- 8.52 | 3.02x | 49.34 | 0.79 |  |

The sign-change test, two fast cores throughout:

| slow cores | measured mixed/fast | predicted | crosses 1.0 | |
|---:|---:|---:|---|---|
| 2 | 1.037x | 0.701x | yes |  |
| 4 | 0.816x | 0.865x | no | noisy, not a verdict |
| 6 | 1.018x | 0.868x | yes | noisy, not a verdict |
| 8 | 0.545x | 0.529x | no | noisy, not a verdict |

## tg64, KMP_BLOCKTIME=infinite

| mixed set | fast-only | slow-only | mixed measured | per-core ratio | predicted | model / measured | |
|---|---:|---:|---:|---:|---:|---:|---|
| P2E2 | 42.15 +- 0.97 | 15.93 +- 0.45 | 41.76 +- 2.81 | 2.65x | 31.86 | 0.76 |  |
| P2E4 | 42.15 +- 0.97 | 22.63 +- 2.77 | 47.79 +- 6.74 | 3.73x | 33.94 | 0.71 |  |
| P2E6 | 42.15 +- 0.97 | 29.14 +- 5.28 | 44.02 +- 13.06 | 4.34x | 38.85 | 0.88 | noisy |
| P2E8 | 42.15 +- 0.97 | 26.54 +- 12.08 | 25.93 +- 25.60 | 6.35x | 33.17 | 1.28 | noisy |
| P4E4 | 74.79 +- 3.18 | 22.63 +- 2.77 | 74.09 +- 11.05 | 3.31x | 45.25 | 0.61 |  |

The sign-change test, two fast cores throughout:

| slow cores | measured mixed/fast | predicted | crosses 1.0 | |
|---:|---:|---:|---|---|
| 2 | 0.991x | 0.756x | no |  |
| 4 | 1.134x | 0.805x | yes |  |
| 6 | 1.045x | 0.922x | yes | noisy, not a verdict |
| 8 | 0.615x | 0.787x | no | noisy, not a verdict |

Across the cells that are not flagged noisy, the measured ratio rises monotonically with the number of slow cores, as the model requires: 2E 0.991x, 4E 1.134x.

## The same mix on a larger model, where the model stops holding

Everything above is qwen0.5b. Repeating the 2P+4E comparison on qwen1.5b,
whose working set is larger and whose work is correspondingly more
bandwidth-bound, inverts the result.

**pp128, qwen1.5b, KMP_BLOCKTIME=200**

| set | tok/s |
|---|---:|
| 2 Golden Cove | 55.23 +- 2.90 |
| 4 Gracemont | 28.73 +- 0.53 |
| 2 Golden Cove + 4 Gracemont | 72.05 +- 3.92 |

Measured mixed/fast-only 1.305x against a predicted 0.780x, so the model accounts for 0.60 of it. The mixed set beats the fast pair by 16.82 tok/s against a combined spread of 6.82, so that gap is real.

**tg32, qwen1.5b, KMP_BLOCKTIME=200**

| set | tok/s |
|---|---:|
| 2 Golden Cove | 21.83 +- 0.25 |
| 4 Gracemont | 13.48 +- 0.65 |
| 2 Golden Cove + 4 Gracemont | 26.69 +- 1.25 |

Measured mixed/fast-only 1.222x against a predicted 0.926x, so the model accounts for 0.76 of it. The mixed set beats the fast pair by 4.86 tok/s against a combined spread of 1.51, so that gap is real.
