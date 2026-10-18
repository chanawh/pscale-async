"""Single-pass regex matching engine.

Replaces the O(P)-per-line loop (one ``re.search`` per pattern per line)
with a single compiled alternation: one ``search()`` per line.

Intended behavior changes (vs. the old loop):
  1. FIRST match wins, ordered by severity rank (CRITICAL > HIGH > MEDIUM
     > LOW, ties broken by lowest pattern id for determinism). One line
     yields one incident instead of one incident per matching pattern.
  2. Patterns that fail to compile are skipped at compile time with a
     logged warning. The old loop caught ``re.error`` per pattern per
     line — same resilience, moved earlier so a bad pattern can't poison
     a whole job.

User-pattern sanitization:
  User-supplied regexes may contain their own ``(?P<name>...)`` named
  groups. Those are rewritten to non-capturing ``(?:...)`` before the
  branch is wrapped in the engine's own named group ``(?P<p<id>>...)``.
  The rewrite is tokenizer-aware: backslash escapes and ``[...]``
  character classes are respected, so a literal ``(?P<`` inside a class
  or after a backslash is left alone. Honest consequences:
  - A named backreference ``(?P=name)`` pointing at a neutralized group
    no longer compiles -> the whole pattern is skipped with a warning.
  - Numbered backreferences (``\\1``) inside a user pattern are shifted
    by the wrapper group (the wrapper becomes group 1). Detection
    patterns in practice don't use backreferences; anything that breaks
    compilation is skipped loudly rather than silently misbehaving.

Matching semantics are otherwise identical to the old loop:
``re.IGNORECASE`` is applied, and ``match_line`` returns the winning
pattern object (or ``None``).

This module is stdlib-only (no celery/sqlalchemy/fastapi imports) so it
is fully unit-testable. Patterns are duck-typed: anything with ``.id``,
``.name``, ``.regex_pattern`` and ``.severity_level`` works.

Known limitation: like the old loop, there is no backtracking guard —
a pathological pattern can still burn CPU on adversarial input. Patterns
are admin-curated, so this is accepted, not solved, here.
"""

import logging
import re

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
_UNKNOWN_RANK = len(_SEVERITY_RANK)


def severity_rank(level) -> int:
    """Rank for match ordering; unknown levels sort after LOW."""
    return _SEVERITY_RANK.get(str(level or "").upper(), _UNKNOWN_RANK)


def sanitize_user_pattern(src: str) -> str:
    """Rewrite user ``(?P<name>...)`` groups as non-capturing ``(?:...)``.

    Tokenizer-aware: ``\\\\`` escapes are passed through untouched and
    ``[...]`` character classes are tracked, so a literal ``(?P<``
    inside a class (e.g. ``[(?P<x>]``) is left alone. A malformed
    ``(?P<`` with no closing ``>`` is left as-is — it will fail
    compilation and the pattern will be skipped with a warning.
    """
    out = []
    i, n = 0, len(src)
    in_class = False
    while i < n:
        c = src[i]
        if c == "\\" and i + 1 < n:
            out.append(src[i : i + 2])
            i += 2
            continue
        if in_class:
            if c == "]":
                in_class = False
            out.append(c)
            i += 1
            continue
        if c == "[":
            in_class = True
            out.append(c)
            i += 1
            continue
        if src.startswith("(?P<", i):
            end = src.find(">", i + 4)
            if end == -1:
                out.append(c)
                i += 1
                continue
            out.append("(?:")
            i = end + 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


class CompiledMatcher:
    """One combined regex plus the branch lookup.

    Attributes:
        regex: the compiled alternation (re.IGNORECASE).
        by_group: ``{'p<id>': pattern}`` for the surviving branches.
        patterns: surviving pattern objects, in match-priority order.
        skipped: names of patterns dropped at compile time.
    """

    def __init__(self, regex, by_group, patterns, skipped):
        self.regex = regex
        self.by_group = by_group
        self.patterns = patterns
        self.skipped = skipped

    def __len__(self):
        return len(self.patterns)


def compile_matcher(patterns) -> CompiledMatcher:
    """Compile one alternation over ``patterns``, CRITICAL-first.

    Each surviving branch is wrapped as ``(?P<p<id>>...)`` so the winner
    is identifiable via ``match.lastgroup``. Invalid patterns are
    skipped with a logged warning; an empty pattern list yields a
    never-matching matcher (not an exception).
    """
    ordered = sorted(
        patterns, key=lambda p: (severity_rank(p.severity_level), p.id)
    )
    branches = []
    by_group = {}
    skipped = []
    survivors = []
    for p in ordered:
        try:
            clean = sanitize_user_pattern(p.regex_pattern)
            re.compile(clean)  # validate the branch on its own first
        except re.error as exc:
            logger.warning(
                "Skipping pattern %r (id=%s): invalid regex (%s)",
                p.name,
                p.id,
                exc,
            )
            skipped.append(p.name)
            continue
        gname = f"p{p.id}"
        branches.append(f"(?P<{gname}>{clean})")
        by_group[gname] = p
        survivors.append(p)
    if not branches:
        # (?!) can never match: empty library => zero incidents, no crash.
        combined = re.compile(r"(?!)")
    else:
        # Safe: every branch validated individually above, and branch
        # group names are unique (pattern ids are unique).
        combined = re.compile("|".join(branches), re.IGNORECASE)
    return CompiledMatcher(combined, by_group, survivors, skipped)


def match_line(matcher: CompiledMatcher, line: str):
    """Return the winning pattern for ``line``, or ``None``.

    The combined alternation is ordered CRITICAL-first, so the first
    branch that matches at the leftmost position wins; ``lastgroup``
    identifies it because the branch wrappers are the only named groups
    left after sanitization.
    """
    m = matcher.regex.search(line)
    if not m:
        return None
    return matcher.by_group.get(m.lastgroup)
