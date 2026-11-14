#!/usr/bin/env python3
"""
verify_redaction.py

Verifies that a redacted CVR file is equivalent to its original:

  1. Every non-redacted ballot row has vote columns identical to the original.
  2. Total vote counts across all contests are preserved:
     original totals == (non-redacted rows) + (aggregate row).

A column whose entry in the aggregation line says "Redacted" belongs to a
contest too rare to protect: anonymize_cvr empties it on every ballot row.
Its total is unknown, never zero, so it is left out of both checks; the check
instead confirms that every ballot row has it empty, and the columns are
reported.

The redacted file has fewer header columns than the original (CountingGroup and
possibly PrecinctPortion are removed entirely).  Both files have the same vote
columns in the same order; only the column offset (headerlen) differs.

Usage:
    python verify_redaction.py original.csv redacted.csv
"""

import csv
import sys
from typing import List, Optional, Set

from anonymize_cvr import CvrDatabase

PROGRESS_INTERVAL = 100_000


def _is_redacted_row(row: List[str], headerlen: int) -> bool:
    """Return True if this ballot row has been redacted (vote columns contain '*')."""
    for col_idx in range(headerlen, len(row)):
        if row[col_idx].strip() == "*":
            return True
    return False


def _is_aggregate_row(row: List[str]) -> bool:
    """Return True if this is the aggregate row appended at the end of the redacted file."""
    return bool(row) and row[0].strip() == "AGGREGATED"


REDACTED = "Redacted"


def _redacted_vote_columns(redacted_path: str, headerlen: int) -> Set[int]:
    """
    Return the vote-column offsets (0 = first vote column) whose entry in the
    aggregation line says "Redacted", or an empty set if there is no such line.
    """
    aggregate_row: Optional[List[str]] = None
    with open(redacted_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for _ in range(4):
            next(reader)
        for row in reader:
            if _is_aggregate_row(row):
                aggregate_row = row
    if aggregate_row is None:
        return set()
    return {
        col_idx - headerlen
        for col_idx in range(headerlen, len(aggregate_row))
        if aggregate_row[col_idx].strip() == REDACTED
    }


def _add_vote_totals(
    tally: List[float],
    row: List[str],
    headerlen: int,
    skip: Optional[Set[int]] = None,
) -> None:
    """
    Add the numeric vote values from a row into the running tally, leaving out
    the vote-column offsets in skip (columns whose total is unknown).
    """
    for i in range(len(tally)):
        col_idx = headerlen + i
        if col_idx >= len(row):
            continue
        if skip and i in skip:
            continue
        val = row[col_idx].strip()
        if val and val != "*":
            try:
                tally[i] += float(val)
            except ValueError:
                pass


def verify(original_path: str, redacted_path: str) -> bool:
    """
    Compare a redacted CVR with its original; print the result and return True
    if it passes.
    """
    orig_db = CvrDatabase(original_path, headerlen=0, named_style_col=None)
    red_db = CvrDatabase(redacted_path, headerlen=0, named_style_col=None)

    orig_headerlen = orig_db.headerlen
    red_headerlen = red_db.headerlen
    orig_vote_cols = len(orig_db.contests) - orig_headerlen
    red_vote_cols = len(red_db.contests) - red_headerlen

    if orig_vote_cols != red_vote_cols:
        print(
            f"Error: original has {orig_vote_cols} vote columns but "
            f"redacted has {red_vote_cols}.",
            file=sys.stderr,
        )
        return False

    num_vote_cols = orig_vote_cols

    # Columns marked "Redacted" in the aggregation line: unknown totals.
    redacted_cols = _redacted_vote_columns(redacted_path, red_headerlen)
    if redacted_cols:
        redacted_contests: List[str] = []
        for i in sorted(redacted_cols):
            name = orig_db.contests[orig_headerlen + i].strip()
            if name not in redacted_contests:
                redacted_contests.append(name)
        print(
            f"{len(redacted_cols)} vote column(s) in {len(redacted_contests)} "
            'contest(s) say "Redacted" in the aggregation line; their totals are '
            "unknown and are not compared, and every ballot row must leave them empty:"
        )
        for name in redacted_contests:
            print(f"  {name!r}")

    orig_tally: List[float] = [0.0] * num_vote_cols
    redacted_tally: List[float] = [0.0] * num_vote_cols

    row_errors = 0
    MAX_ERRORS = 20
    row_idx = 0

    with open(original_path, "r", encoding="utf-8") as f_orig:
        with open(redacted_path, "r", encoding="utf-8") as f_red:
            orig_reader = csv.reader(f_orig)
            red_reader = csv.reader(f_red)

            for _ in range(4):
                next(orig_reader)
                next(red_reader)

            orig_rows = (r for r in orig_reader if r)
            red_rows = (r for r in red_reader if r)

            for orig_row in orig_rows:
                red_row = next(red_rows, None)
                if red_row is None:
                    print(
                        f"Error: redacted file ran out of rows at row {row_idx + 5} "
                        f"(original has more rows).",
                        file=sys.stderr,
                    )
                    return False

                if row_idx > 0 and row_idx % PROGRESS_INTERVAL == 0:
                    print(f"  {row_idx:,} rows checked...", flush=True)

                _add_vote_totals(orig_tally, orig_row, orig_headerlen, redacted_cols)

                if _is_aggregate_row(red_row):
                    print(
                        f"Error: aggregate row found at row {row_idx + 5}, "
                        f"before original file was exhausted.",
                        file=sys.stderr,
                    )
                    return False

                for vote_col in redacted_cols:
                    red_val = red_row[red_headerlen + vote_col].strip()
                    if red_val != "":
                        col_name = orig_db.contests[orig_headerlen + vote_col]
                        print(
                            f"Error: row {row_idx + 5}, contest {col_name!r} says "
                            f'"Redacted" in the aggregation line but this row '
                            f"has {red_val!r}",
                            file=sys.stderr,
                        )
                        row_errors += 1

                if _is_redacted_row(red_row, red_headerlen):
                    pass  # vote columns are intentionally replaced; nothing to compare
                else:
                    _add_vote_totals(
                        redacted_tally, red_row, red_headerlen, redacted_cols
                    )
                    for vote_col in range(num_vote_cols):
                        if vote_col in redacted_cols:
                            continue
                        orig_val = orig_row[orig_headerlen + vote_col].strip()
                        red_val = red_row[red_headerlen + vote_col].strip()
                        if orig_val != red_val:
                            col_name = orig_db.contests[orig_headerlen + vote_col]
                            print(
                                f"Error: row {row_idx + 5}, contest {col_name!r}: "
                                f"original={orig_val!r}, redacted={red_val!r}",
                                file=sys.stderr,
                            )
                            row_errors += 1
                            if row_errors >= MAX_ERRORS:
                                print(
                                    "Too many errors; stopping early.", file=sys.stderr
                                )
                                return False

                row_idx += 1

            # After all original rows, the redacted file may have one more row: the aggregate.
            extra_row = next(red_rows, None)
            if extra_row is not None:
                if _is_aggregate_row(extra_row):
                    _add_vote_totals(
                        redacted_tally, extra_row, red_headerlen, redacted_cols
                    )
                    unexpected = next(red_rows, None)
                    if unexpected is not None:
                        print(
                            "Error: redacted file has unexpected rows after the aggregate row.",
                            file=sys.stderr,
                        )
                        return False
                else:
                    print(
                        "Error: redacted file has an extra non-aggregate row after "
                        "the last original row.",
                        file=sys.stderr,
                    )
                    return False

    # Compare vote totals.
    tally_mismatches = 0
    for i in range(num_vote_cols):
        if abs(orig_tally[i] - redacted_tally[i]) > 0.001:
            col_name = orig_db.contests[orig_headerlen + i]
            print(
                f"Tally mismatch in contest {col_name!r}: "
                f"original={orig_tally[i]:.3f}, redacted={redacted_tally[i]:.3f}",
                file=sys.stderr,
            )
            tally_mismatches += 1

    if row_errors == 0 and tally_mismatches == 0:
        known = " known" if redacted_cols else ""
        print(
            f"Verification passed: {row_idx:,} rows checked, all{known} vote totals match."
        )
        return True
    else:
        print(
            f"Verification FAILED: {row_errors} row error(s), "
            f"{tally_mismatches} tally mismatch(es).",
            file=sys.stderr,
        )
        return False


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} original.csv redacted.csv", file=sys.stderr)
        sys.exit(1)
    ok = verify(sys.argv[1], sys.argv[2])
    sys.exit(0 if ok else 1)
