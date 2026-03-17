"""Graph building and file matching logic for lsrelated."""

from __future__ import annotations

from collections import Counter

from ccdata import Session


def build_undirected_graph(
    sessions: list[Session],
) -> tuple[dict[tuple[str, str], int], Counter[str]]:
    """Build undirected co-access graph from sessions.

    Returns (edges, node_counts) where edges maps (fileA, fileB) with fileA < fileB
    to the co-access count, and node_counts tracks total accesses per file.
    """
    edges: dict[tuple[str, str], int] = {}
    node_counts: Counter[str] = Counter()

    for s in sessions:
        for t in s.turns:
            files = []
            for tc in t.tool_calls:
                if tc.name in ("Read", "Write", "Edit"):
                    fp = tc.input.get("file_path", "")
                    if fp:
                        files.append(fp)
            # Dedupe consecutive repeats
            deduped = []
            for f in files:
                if not deduped or deduped[-1] != f:
                    deduped.append(f)

            # Count each file's appearances
            for f in deduped:
                node_counts[f] += 1

            # Undirected edges: canonical order is sorted pair
            seen_pairs: set[tuple[str, str]] = set()
            for i in range(len(deduped)):
                for j in range(i + 1, len(deduped)):
                    a, b = deduped[i], deduped[j]
                    if a == b:
                        continue
                    pair = (min(a, b), max(a, b))
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        edges[pair] = edges.get(pair, 0) + 1

    return edges, node_counts


def find_file(query: str, node_counts: Counter[str]) -> str | None:
    """Find the best matching file path for a query.

    Tries exact match, then suffix match, then substring match.
    If multiple matches, picks the one with highest access count.
    """
    # Exact match
    if query in node_counts:
        return query

    # Suffix match (e.g. "types.ts" matches "/foo/bar/types.ts")
    suffix_matches = [f for f in node_counts if f.endswith("/" + query) or f.endswith(query)]
    if len(suffix_matches) == 1:
        return suffix_matches[0]

    # Substring match
    substr_matches = [f for f in node_counts if query in f]
    if len(substr_matches) == 1:
        return substr_matches[0]

    # Multiple matches -- return the one with highest access count
    if suffix_matches:
        return max(suffix_matches, key=lambda f: node_counts[f])
    if substr_matches:
        return max(substr_matches, key=lambda f: node_counts[f])

    return None


def find_display_prefix(files: list[str]) -> str:
    """Find the longest directory prefix covering >50% of files.

    This is better than os.path.commonprefix because session data includes
    files outside the project (e.g. ~/.claude/plans/) which would make the
    common prefix empty.
    """
    if not files:
        return ""
    dir_counts: Counter[str] = Counter()
    for f in files:
        parts = f.split("/")
        for depth in range(3, min(len(parts), 7)):
            dir_counts["/".join(parts[:depth]) + "/"] += 1
    prefix = ""
    for candidate, count in dir_counts.most_common():
        if count > len(files) * 0.5 and len(candidate) > len(prefix):
            prefix = candidate
    return prefix


def strip_prefix(path: str, prefix: str) -> str:
    """Strip a common prefix from a path for display."""
    if path.startswith(prefix):
        return path[len(prefix):]
    return path
