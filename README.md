# The Barrier Spin Crossover

Measurements of how the thread-barrier spin-wait threshold affects CPU LLM
inference throughput and energy.

Every table below is regenerated from the raw files by
`python scripts/make_tables.py`. Nothing is transcribed by hand.

## The short version

At a thread barrier a waiting thread can spin, or it can sleep. Spinning wastes
a core while it waits. Sleeping costs a futex round trip to wake up. Real
runtimes compromise: spin for a bounded number of iterations, then sleep.

That bound is the question. `llama.cpp` PR
[#13079](https://github.com/ggml-org/llama.cpp/pull/13079) has been open since
April 2025 on exactly this point, and the argument stalled on whether a good
constant exists. So the bound was swept across seven decades rather than
guessed at.

Four things came out of it.

**Prefill does not care and decode does.** Across the whole seven-decade sweep
on four idle Cortex-A76 cores, prefill throughput moves 0.3 percent, which is
inside the run-to-run noise. Decode moves 8.2 percent and saturates around
100k iterations.

**The optimum inverts under contention.** With two competing CPU-bound
processes on the same cores, the best setting moves from roughly 1e6 to zero,
and the worst setting costs 13.3x. No compile-time constant serves both an idle
machine and a busy one.

**The loss is asymmetric, which is the actionable part.** Spinning too little
costs at most 7.6 percent, and only when the cores are free. Spinning too much
costs 92.5 percent. Being wrong toward more spinning is about twelve times worse
than being wrong toward less.

**Lower power is not lower energy.** Under contention the longest spin setting
draws *less* board power than never spinning, 5.43 W against 6.63 W, and still
spends 11.3x the energy per token, because the run takes about fourteen times
longer.

`libgomp`'s own default sits at the bad end of this. It is about 300000
iterations, which was measured rather than assumed: leaving `GOMP_SPINCOUNT`
unset and setting it explicitly to 300000 agree to within 0.07 percent. At idle
that default is optimal. Under contention it gives up 79 percent of throughput.

## What the hybrid x86 part adds

Three more things, from the Golden Cove plus Gracemont machine.

**Going to sleep immediately is the worst setting on every core type, and it
gets worse the wider the thread team.** Decode at `KMP_BLOCKTIME=0` costs 3.4x
on four Golden Cove cores, 6.8x on six, and 14x on the eight-thread mixed set.
Above zero, this machine cannot separate the settings from each other; the
analysis says so per row rather than inviting you to read a trend into noise.

**Whether adding slow cores to a fast set helps or hurts depends on the model.**
Holding two Golden Cove cores fixed on qwen0.5b and adding Gracemont cores,
prefill goes 0.650x at two slow cores, 0.887x at four, and 1.095x at six,
relative to the fast pair alone. So a small mix costs 35 percent and a larger
one turns into a 10 percent gain. The curve rises with the number of slow cores
and crosses one around six.

**Equal-share partitioning predicts that curve, including the crossing.** Assume
work is split evenly by thread index and the barrier waits for the slowest
thread, and the mixed set should land at `((nP + nE) / nP) * (vE / vP)` of the
fast-only set. That predicts 0.576, 0.731 and 1.003 against the three measured
numbers, and puts the sign change at six slow cores, where it happened.

**And it stops holding on a larger model.** The same 2P+4E comparison on
qwen1.5b gives 1.305x rather than the 0.780x the model predicts, so the model
accounts for 0.60 of it. Same machine, same core mix. On the small model adding
four slow cores costs 11 percent; on the larger one it gains 31 percent, and
that gap is 16.82 tok/s against a combined spread of 6.82. The likely reason is
that the larger working set pushes the work toward bandwidth, where core speed
matters less, but that is inference from the numbers rather than something
measured here.

**None of it moves with the wait policy.** Switching between the default block
time and never-sleep changes none of these comparisons.

## What was measured

| | Raspberry Pi 5 | Intel i7-12700H |
|---|---|---|
| Cores | 4x Cortex-A76, homogeneous | 6x Golden Cove + 8x Gracemont, heterogeneous |
| RAM | 2 GB | 32 GB DDR5 |
| OS | Raspberry Pi OS (bookworm) | Windows 11 |
| llama.cpp | `d73c1d6`, Release | build 10154 |
| OpenMP runtime | GNU libgomp | LLVM libomp |
| Spin knob | `GOMP_SPINCOUNT` (iterations) | `KMP_BLOCKTIME` (milliseconds) |
| Energy | board PMIC, per-rail V*I at 10 Hz | not instrumented |
| Model | qwen0.5b Q4_K_M, CPU only | qwen0.5b Q4_K_M, CPU only |

The two spin knobs are not the same unit and they do not gate at quite the same
point. `GOMP_SPINCOUNT` is a number of spin iterations a libgomp thread burns
before it futex-waits. `KMP_BLOCKTIME` is how long a libomp thread stays hot
after finishing a parallel region before it sleeps. Both answer "how long do I
stay awake before paying for a sleep", which is the question this repository is
about, but their constants are not comparable across the two machines and
neither is a direct handle on ggml's own barrier. What is comparable is the
shape of each curve and the direction the optimum moves.

## Method

Things that were done deliberately, because each of them changes the answer:

- **Throughput and power were never read from the same run.** The 10 Hz PMIC
  sampler still costs CPU on a four-core board, so every energy condition was
  run twice, once clean for throughput and once sampled for power.
- **Randomized ordering, multiple rounds.** Conditions were shuffled within
  each round so that any slow drift in machine state hits all of them equally.
- **Throttle and clock recorded per run.** On the Pi campaign `get_throttled`
  stayed `0x0` and the ARM clock stayed at 2400 MHz on every run; both are
  recorded per run in the `meta.jsonl` files. Governor was `performance`.
- **Resume by skip-if-exists**, so an interrupted campaign does not
  half-overwrite its own results.
- **Processes killed by PID, never by pattern**, because `pkill -f` matches the
  shell's own command line and silently kills the wrong thing.
- **`llama-bench` throughout, never `llama-cli`**, which hangs when scripted.
  Prefill length is always given explicitly, because `-p 0` reports a bogus
  decode rate.
- Zero runs failed or were discarded across all campaigns, and no run wrote
  anything to stderr. The per-run stderr logs were therefore all empty and are
  not carried here.

## Limits

Read these before using any number here.

**The spin knobs are proxies for the mechanism in PR #13079, not that mechanism
itself.** `GOMP_SPINCOUNT` tunes libgomp's barrier and `KMP_BLOCKTIME` tunes
LLVM libomp's. Both are spin-then-futex-sleep, which is what the PR implements,
so the shape of the cost curve should carry over. The absolute constants will
not. Nobody should read a recommended spin count for ggml's own barrier out of
this repository.

**The two knobs can disagree, and where they do it is a difference in what they
gate rather than a contradiction in the hardware.** Under contention on the Pi,
`GOMP_SPINCOUNT=0` is the best setting: not spinning at the barrier hands the
core straight to the competing process. On x86, `KMP_BLOCKTIME=0` is the worst
setting on every core type by a factor of two to three. Those are not the same
experiment. Zeroing the libgomp spin count skips a spin before one futex wait.
Zeroing libomp's block time puts the whole team to sleep every time a parallel
region ends, and llama.cpp opens and closes parallel regions constantly, so it
buys thousands of sleep and wake cycles per token. Read each machine's table
against itself.

**The energy work is one board, one model, one quantization.** Cortex-A76 at
2.4 GHz with four identical cores and 2 GB of RAM. It says nothing directly
about server CPUs, and the Pi campaign says nothing about heterogeneous cores
because that board does not have any.

**The contention is synthetic.** Two busy-loop processes pinned to the same
cores. That is a cleaner and harsher signal than most real interference, which
tends to be bursty and partly IO-bound. The direction of the effect should hold;
the magnitude is an upper bound.

**Board-level energy includes everything.** The Pi PMIC total covers the
wireless, HDMI and IO rails as well as the SoC, so joules per token here are
board-level and are not comparable to a package-power number from RAPL. Within
one table the comparison is sound because the same rails are included in every
row.

**On this board `DDR_VDDQ` never populates its current channel**, even under a
streaming memcpy load, so the DRAM figure is carried by `DDR_VDD2` alone.

**The x86 machine was not idle.** It is a working laptop and other processes
were running during the sweep. Randomized interleaving and repeated rounds are
the mitigation, and per-round load is recorded, but the x86 numbers carry more
variance than the Pi numbers and should be read as a direction rather than a
precise magnitude.

**WSL2 does not pin faithfully to physical P and E cores.** A fixed-work loop
pinned to each of the twenty vCPUs in turn came back near-uniform, while the
same comparison run natively showed a clean 2x split. Every heterogeneous-core
measurement here was therefore taken natively on Windows with `llama-bench`'s
own `--cpu-mask` and `--cpu-strict`, which was verified to bite: four threads
forced onto one logical CPU collapse about 2x against four threads on four.

## Layout

```
data/pi-cortex-a76/
  idle-sweep/             spin sweep, 1/2/4 threads, idle, plus wait-policy references
  contention-sweep/       external CPU hogs and self-oversubscription
  energy-and-tightened/   PMIC power traces, and a denser contended sweep
  default-comparison/     unset versus explicit spin count, both regimes
data/laptop-alderlake/
  spin-sweep/             KMP_BLOCKTIME across P-only, E-only and mixed affinity
  ratio-sweep/            core-count ratios from 2P+2E to 2P+8E, and a second model size
scripts/
  make_tables.py          regenerates every table from the raw files
  pmic_sampler.py         10 Hz per-rail PMIC sampler
  run_sweep.sh            Pi: idle spin sweep
  run_contention.sh       Pi: contention and oversubscription
  run_energy.sh           Pi: energy plus tightened contention sweep
  run_default.sh          Pi: unset versus explicit
  pe_sweep.sh             x86: heterogeneous-core sweep
  hybrid2.sh              x86: core-count ratio sweep and the second model size
  ratio_tables.py         emits the ratio and model-size tables
results/
  TABLES.md               generated output, checked in so the repo reads without running anything
```

Each `*.json` file is one `llama-bench` invocation in its own `-o json` form,
including the per-repetition samples. Each `*.power.jsonl` is one PMIC trace,
one JSON object per sample, with a monotonic timestamp and per-rail watts.
`windows.jsonl` records the benchmark start and end timestamps so a power trace
can be trimmed to the run.

## Reproducing

```bash
python scripts/make_tables.py > results/TABLES.md
```

That needs only the standard library and the files already in this repository.

To re-run the measurements you need the hardware. The campaign scripts under
`scripts/` are the ones that actually produced these files, kept as they ran
rather than tidied afterwards, so they carry the original machines' paths
(`$HOME/llm/...` on the Pi, `/c/llmpc/...` on the laptop) and will need those
edited. Each states its own assumptions at the top.

## Relation to llama.cpp PR #13079

That PR proposes replacing ggml's unbounded spin barrier with a futex yield
barrier. The maintainer's objection is that it cannot ship behind a compile
flag and should adapt automatically, and the author's own assessment was that
the spin count is not tuned well. This repository is the measurement that was
missing from that discussion. It does not contain a patch.

ggml's barrier is an unbounded spin with no fallback. One level up, at graph
kickoff, ggml already does the bounded-spin-then-sleep thing this data argues
for, and the comment above that code says "Perhaps, we can adjust it dynamically
based on load and things."

## Citation

See `CITATION.cff`.

## License

MIT. See `LICENSE`.
