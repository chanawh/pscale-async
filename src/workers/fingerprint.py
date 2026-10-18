"""Content fingerprints for incident deduplication.

An incident's *fingerprint* answers "have we already recorded this exact
finding?" so that re-running a job — or ingesting the same file twice as a
new job — never duplicates incidents, while genuinely distinct findings are
never merged.

Composition
-----------
``sha256(pattern_id + \\x1f + node_key + \\x1f + line)``, hex-encoded
(64 chars), where ``node_key`` is ``str(node_id)`` (``""`` when the node is
unknown) and ``line`` is the stripped log line. ``\\x1f`` (unit separator)
delimits the fields so no two distinct triples can collide textually.

Why these three fields, and nothing else:

* ``pattern_id`` — the same log line matched by two different patterns is
  two different findings (different title, severity, runbook). Deduping
  across patterns would merge them.
* node identity — the same disk-failure line on node-3 and node-4 is two
  incidents an operator must triage separately. A fingerprint without the
  node would suppress the second one: the classic surprising merge.
* the log line itself — the evidence. Normalization is deliberately
  minimal (``strip()``, applied upstream): case variants are treated as
  distinct lines, the conservative choice against false merges.

Why NOT ``job_id``: the whole point is cross-job idempotency. Re-ingesting
the same file creates a *new* job; if the job id were in the fingerprint,
the second ingest would never dedup. The effective uniqueness scope is
therefore (pattern, node, line) — global across jobs, node-scoped.

Why NOT timestamps or severity: severity derives from the pattern, and any
timestamp would make every fingerprint unique, defeating dedup entirely.

Scope alternatives considered and rejected:

* Global (line + pattern, no node): merges the same finding across nodes
  and clusters — operationally wrong, an on-call engineer wants to know
  *which* node.
* Per-(job_id, fingerprint): adds nothing over the existing
  delete-then-recreate retry guard within a job, and kills the cross-job
  re-ingest goal outright.

NULL fingerprints: rows written before this column existed carry NULL and
never participate in dedup (NULL != NULL under unique indexes on both
PostgreSQL and SQLite). New code always sets the fingerprint.

node_id vs hostname: node_id is this schema's canonical node identity and
is already resolved once per job, so no extra lookup is needed. Trade-off:
it is DB-local — if the nodes table were ever rebuilt, old fingerprints
would not match new rows. Stated here so the choice is explicit.

This module is stdlib-only so the fingerprint logic is unit-testable
without the SQLAlchemy/Celery stack.
"""

import hashlib
from typing import Optional


def compute_fingerprint(
    pattern_id: int, node_id: Optional[int], line: str
) -> str:
    """Return the 64-char hex sha256 fingerprint for an incident.

    ``line`` must already be stripped (callers pass the same stripped line
    stored in ``Incident.raw_log``). ``node_id`` may be None for the legacy
    unknown-node path; it then contributes an empty node key.
    """
    node_key = "" if node_id is None else str(node_id)
    material = "\x1f".join((str(pattern_id), node_key, line))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
