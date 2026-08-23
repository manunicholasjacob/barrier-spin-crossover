#!/usr/bin/env python3
"""10 Hz Pi 5 PMIC power sampler.

Writes one JSON line per sample: monotonic timestamp plus per-rail power in W.
10 Hz is deliberate: at 50 Hz the sampler steals a core on this 4-core board
and slows decode by roughly 6x, so throughput must never be read from a
sampled run.
"""

import json
import re
import subprocess
import sys
import time

LINE = re.compile(
    r"^\s*(?P<rail>\S+?)_(?P<kind>[AV])\s+(?:current|volt)\(\d+\)=(?P<value>[\d.]+)[AV]\s*$"
)


def read_rails():
    out = subprocess.run(
        ["vcgencmd", "pmic_read_adc"], capture_output=True, text=True, timeout=5
    ).stdout
    amps, volts = {}, {}
    for line in out.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        if m.group("kind") == "A":
            amps[m.group("rail")] = float(m.group("value"))
        else:
            volts[m.group("rail")] = float(m.group("value"))
    return {r: amps[r] * volts[r] for r in amps.keys() & volts.keys()}


def main():
    out_path = sys.argv[1]
    hz = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    period = 1.0 / hz
    with open(out_path, "w") as fh:
        next_t = time.monotonic()
        while True:
            try:
                rails = read_rails()
            except Exception as exc:  # transient vcgencmd failure
                fh.write(json.dumps({"t": time.monotonic(), "error": str(exc)}) + "\n")
                fh.flush()
                next_t += period
                time.sleep(max(0.0, next_t - time.monotonic()))
                continue
            rec = {"t": time.monotonic(), "total_w": sum(rails.values())}
            rec.update({k: round(v, 6) for k, v in rails.items()})
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            next_t += period
            time.sleep(max(0.0, next_t - time.monotonic()))


if __name__ == "__main__":
    main()
