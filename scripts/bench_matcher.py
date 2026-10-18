"""Benchmark: old O(P)-per-line loop vs the single-pass matching engine.

Stdlib-only. Uses the real 23-pattern default library from
``src.workers.log_processor.create_default_patterns`` and synthetic log
lines with a realistic match distribution (~18% of lines match at least
one pattern).

Methodology (also stated in the README):
  - OLD: each pattern pre-compiled once (generous to the old code — this
    measures scans, not ``re``'s internal compile cache), then one
    ``search()`` per pattern per line, exactly like the old loop.
  - NEW: ``compile_matcher()`` once, then one ``match_line()`` per line.
  - Compile time is reported separately and excluded from the per-line
    rate. Timings are machine-dependent; the speedup ratio is the
    headline, not the absolute lines/sec.

Usage:  python3 scripts/bench_matcher.py [--lines N] [--rounds R]
"""

import argparse
import random
import re
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, ".")

from src.workers.matcher import compile_matcher, match_line

# The real default library (name, regex, severity), copied verbatim from
# create_default_patterns in src/workers/log_processor.py.
PATTERNS = [
    ('Disk Failure', '(disk|drive).*fail|(error|critical).*disk', 'CRITICAL'),
    ('Network Timeout', 'network.*timeout|connection.*timeout', 'HIGH'),
    ('High CPU Usage', 'cpu.*high|processor.*load', 'MEDIUM'),
    ('Memory Pressure', 'memory.*pressure|out.*of.*memory', 'HIGH'),
    ('Authentication Failure', 'auth.*fail|login.*fail|authentication.*error', 'MEDIUM'),
    ('File System Error', 'filesystem.*error|fs.*error|inode.*error', 'HIGH'),
    ('OneFS System Alert', 'isilon_d.*critical|isi.*critical|system.*alert', 'CRITICAL'),
    ('OneFS Service Failure', 'isilon_d.*fail|daemon.*restart|service.*stop|isi_.*_d.*error', 'HIGH'),
    ('Cluster Quorum Issue', 'cluster.*quorum|node.*disconnect|cluster.*reform|gmp.*fail', 'CRITICAL'),
    ('SMART Disk Failure', 'smartd.*fail|smart.*error|disk.*predict.*fail|drive.*fail', 'CRITICAL'),
    ('Storage Pool Degraded', 'pool.*degraded|storage.*pool.*fail|flexpool.*error|diskpool.*unavail', 'HIGH'),
    ('File System Capacity', 'filesystem.*full|quota.*exceed|capacity.*critical|space.*low', 'HIGH'),
    ('Network Interface Down', 'interface.*down|iface.*fail|ip.*change|link.*down', 'HIGH'),
    ('NFS Timeout Error', 'nfs.*timeout|nfs.*error|nfs.*fail|rpc.*timeout', 'MEDIUM'),
    ('SMB/CIFS Error', 'smb.*error|cifs.*fail|samba.*error|winbind.*fail', 'MEDIUM'),
    ('Kerberos Authentication Failure', 'kerberos.*fail|krb5.*error|ticket.*expire|auth.*krb', 'MEDIUM'),
    ('LDAP/AD Connectivity', 'ldap.*timeout|ad.*connect|domain.*controller.*fail|sssd.*error', 'MEDIUM'),
    ('Security Audit Deny', 'audit.*deny|permission.*denied|access.*denied|security.*violation', 'MEDIUM'),
    ('Hardware Temperature Alert', 'temp.*critical|temperature.*high|thermal.*alert|fan.*fail', 'HIGH'),
    ('Power Supply Failure', 'power.*supply.*fail|ups.*fail|psu.*error|power.*loss', 'CRITICAL'),
    ('OneFS Upgrade Event', 'upgrade.*start|upgrade.*complete|patch.*install|isi.*upgrade', 'MEDIUM'),
    ('Snapshot Delete Error', 'snapshot.*fail|snap.*error|isi.*snapshot.*error', 'MEDIUM'),
    ('Job Engine Failure', 'job.*engine.*fail|backup.*error|replication.*fail|isi.*job.*error', 'MEDIUM'),
]

# Fragments that trigger specific patterns, plus neutral noise.
MATCHING_FRAGMENTS = [
    "disk drive fail on bay 3", "smartd reports disk predict fail",
    "network timeout after 30s", "cpu high load average 92",
    "memory pressure critical zone", "auth fail for user admin",
    "filesystem error inode 88121", "isilon_d critical alert raised",
    "node disconnect from cluster", "pool degraded on tier 1",
    "nfs timeout on export /data", "smb error session setup",
    "kerberos ticket expire soon", "temperature high on psu 2",
    "power supply failover engaged", "snapshot fail snap_20261017",
]
NOISE_FRAGMENTS = [
    "routine heartbeat ok", "gc completed in 12ms", "connection pool stats",
    "scheduled job started", "metrics flushed", "cache hit ratio 0.97",
    "worker idle", "checkpoint written", "dns resolve ok",
]


def make_corpus(n_lines, seed=20261017):
    rng = random.Random(seed)
    lines = []
    for _ in range(n_lines):
        r = rng.random()
        if r < 0.18:
            frag = rng.choice(MATCHING_FRAGMENTS)
        else:
            frag = rng.choice(NOISE_FRAGMENTS)
        host = f"node{rng.randint(1, 8)}"
        lines.append(f"Oct 17 12:{rng.randint(10, 59):02d}:{rng.randint(10, 59):02d} {host} {frag}")
    return lines


def bench_old(lines, compiled):
    """One search per pattern per line, like the old loop."""
    hits = 0
    t0 = time.perf_counter()
    for line in lines:
        for rx in compiled:
            if rx.search(line):
                hits += 1
    dt = time.perf_counter() - t0
    return dt, hits


def bench_new(lines, matcher):
    hits = 0
    t0 = time.perf_counter()
    for line in lines:
        if match_line(matcher, line) is not None:
            hits += 1
    dt = time.perf_counter() - t0
    return dt, hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", type=int, default=20000)
    ap.add_argument("--rounds", type=int, default=3)
    args = ap.parse_args()

    objs = [
        SimpleNamespace(id=i + 1, name=n, regex_pattern=rx, severity_level=sev)
        for i, (n, rx, sev) in enumerate(PATTERNS)
    ]
    lines = make_corpus(args.lines)
    matched = sum(
        1 for line in lines
        if any(w in line for w in ("fail", "timeout", "high", "error", "critical", "expire", "degraded"))
    )
    print(f"patterns={len(PATTERNS)} lines={len(lines)} "
          f"approx_matching_lines={matched} ({matched/len(lines):.0%})")

    old_compiled = [re.compile(rx, re.IGNORECASE) for _, rx, _ in PATTERNS]

    t0 = time.perf_counter()
    matcher = compile_matcher(objs)
    compile_s = time.perf_counter() - t0
    print(f"engine compile: {compile_s*1000:.1f} ms (one-time, per chunk)")

    old_times, new_times = [], []
    for r in range(args.rounds):
        dt_old, hits_old = bench_old(lines, old_compiled)
        dt_new, hits_new = bench_new(lines, matcher)
        old_times.append(dt_old)
        new_times.append(dt_new)
        print(f"round {r+1}: old={dt_old:.3f}s ({len(lines)/dt_old:,.0f} lines/s) "
              f"new={dt_new:.3f}s ({len(lines)/dt_new:,.0f} lines/s)")

    dt_old = min(old_times)
    dt_new = min(new_times)
    ratio = dt_old / dt_new
    print(f"\nbest-of-{args.rounds}: old {len(lines)/dt_old:,.0f} lines/s, "
          f"new {len(lines)/dt_new:,.0f} lines/s")
    print(f"RATIO (new/old): {ratio:.2f}x")
    print("Note: on mostly non-matching lines the old loop's per-pattern")
    print("literal-prefix fast search beats the alternation's branching cost;")
    print("the engine pulls ahead as match rate rises (it stops at first match).")


if __name__ == "__main__":
    main()
