#!/usr/bin/env python3
"""
generate_test_cvrs.py

Generates synthetic CVR CSV files for testing anonymize_cvr.py.
Each scenario targets specific code paths or command-line options.

Output files are written to testCases/generated/.

Usage:
    python generate_test_cvrs.py

Vote column encoding (matching the Parquet CVR format):
    ""   -- contest is absent from this ballot
    "0"  -- contest is present but this choice was not selected
    "1"  -- this choice was selected
"""

import csv
import os
from dataclasses import dataclass
from typing import Dict, List

OUTPUT_DIR = "testCases/generated"

STANDARD_HEADER_COLS = [
    "CvrNumber",
    "TabulatorNum",
    "BatchId",
    "RecordId",
    "ImprintedId",
    "PrecinctPortion",
    "BallotType",
]


@dataclass
class Contest:
    name: str
    choices: List[str]


@dataclass
class BallotSpec:
    """
    One group of identical ballots.

    contests:    contest names that appear on this ballot
    votes:       contest_name -> choice_name for each voted contest;
                 contests present but absent from votes are undervoted
    count:       number of identical ballots to generate
    precinct:    PrecinctPortion column value
    ballot_type: BallotType column value
    named_style: NamedStyle column value (only written if the scenario includes that column)
    """

    contests: List[str]
    votes: Dict[str, str]
    count: int
    precinct: str = "P1"
    ballot_type: str = ""
    named_style: str = ""


@dataclass
class Scenario:
    filename: str
    description: str
    election_name: str
    all_contests: List[Contest]
    ballots: List[BallotSpec]
    include_named_style_col: bool = False


def _write_cvr(scenario: Scenario) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, scenario.filename)

    # Build ordered (contest_name, choice_name) list for all vote columns.
    vote_columns = []
    for contest in scenario.all_contests:
        for choice in contest.choices:
            vote_columns.append((contest.name, choice))

    header_cols = list(STANDARD_HEADER_COLS)
    if scenario.include_named_style_col:
        header_cols.append("NamedStyle")

    headerlen = len(header_cols)
    total_cols = headerlen + len(vote_columns)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Row 1: election name, version string, empty for remaining columns.
        writer.writerow([scenario.election_name, "V1"] + [""] * (total_cols - 2))

        # Row 2: empty for header columns, contest name for each vote column.
        writer.writerow([""] * headerlen + [c[0] for c in vote_columns])

        # Row 3: empty for header columns, choice name for each vote column.
        writer.writerow([""] * headerlen + [c[1] for c in vote_columns])

        # Row 4: column header names, empty for vote columns.
        writer.writerow(header_cols + [""] * len(vote_columns))

        # Ballot rows.
        cvr_num = 1
        record_id = 1
        for spec in scenario.ballots:
            for _ in range(spec.count):
                row = [
                    str(cvr_num),
                    "1",
                    "1",
                    str(record_id),
                    f"1-1-{record_id}",
                    spec.precinct,
                    spec.ballot_type,
                ]
                if scenario.include_named_style_col:
                    row.append(spec.named_style)

                for contest_name, choice_name in vote_columns:
                    if contest_name not in spec.contests:
                        row.append("")  # contest absent
                    else:
                        voted = spec.votes.get(contest_name, "")
                        if voted == choice_name:
                            row.append("1")
                        else:
                            row.append("0")  # present but not this choice, or undervote

                writer.writerow(row)
                cvr_num += 1
                record_id += 1

    ballot_count = sum(s.count for s in scenario.ballots)
    print(f"  {scenario.filename}  ({ballot_count} ballots)")
    print(f"    {scenario.description}")


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------


def _scenario_no_redaction() -> Scenario:
    """
    All ballot styles have >= 10 ballots.
    Expected: no redaction needed.
    Command: python anonymize_cvr.py --check testCases/generated/no_redaction.csv
    """
    contests = [
        Contest("President", ["Alice", "Bob"]),
        Contest("Senate", ["Carol", "Dave"]),
        Contest("Governor", ["Eve", "Frank"]),
    ]
    ballots = [
        # Style A: all three contests, 15 ballots, mixed votes.
        BallotSpec(
            ["President", "Senate", "Governor"],
            {"President": "Alice", "Senate": "Carol", "Governor": "Eve"},
            count=8,
        ),
        BallotSpec(
            ["President", "Senate", "Governor"],
            {"President": "Bob", "Senate": "Dave", "Governor": "Frank"},
            count=7,
        ),
        # Style B: President + Senate only, 12 ballots.
        BallotSpec(
            ["President", "Senate"], {"President": "Alice", "Senate": "Carol"}, count=6
        ),
        BallotSpec(
            ["President", "Senate"], {"President": "Bob", "Senate": "Dave"}, count=6
        ),
    ]
    return Scenario(
        filename="no_redaction.csv",
        description="All styles >= 10 ballots. Expected: no redaction needed.",
        election_name="Test: No Redaction Needed",
        all_contests=contests,
        ballots=ballots,
    )


def _scenario_needs_borrowing() -> Scenario:
    """
    One rare style (President+Senate, 6 ballots) borrows 4 from a common style
    (President+Senate+Governor) to reach min_ballots=10.
    The styles differ because the common style has an extra Governor contest.
    Expected: rare style (style #0) has 6 ballots; 4 borrowed from common style.
    Command: python anonymize_cvr.py testCases/generated/needs_borrowing.csv /tmp/out.csv
    """
    contests = [
        Contest("President", ["Alice", "Bob"]),
        Contest("Senate", ["Carol", "Dave"]),
        Contest("Governor", ["Eve", "Frank"]),
    ]
    ballots = [
        # Rare style: President + Senate only (style "110"), 6 ballots.
        BallotSpec(
            ["President", "Senate"], {"President": "Alice", "Senate": "Carol"}, count=3
        ),
        BallotSpec(
            ["President", "Senate"], {"President": "Bob", "Senate": "Dave"}, count=3
        ),
        # Common style: all three contests (style "111"), 20 ballots.
        # Donors from this style cover President and Senate for the rare aggregate.
        BallotSpec(
            ["President", "Senate", "Governor"],
            {"President": "Alice", "Senate": "Carol", "Governor": "Eve"},
            count=10,
        ),
        BallotSpec(
            ["President", "Senate", "Governor"],
            {"President": "Bob", "Senate": "Dave", "Governor": "Frank"},
            count=10,
        ),
    ]
    return Scenario(
        filename="needs_borrowing.csv",
        description="Rare style (P+S, 6 ballots) borrows 4 from common style (P+S+G) to reach 10.",
        election_name="Test: Needs Borrowing",
        all_contests=contests,
        ballots=ballots,
    )


def _scenario_rare_unique_contest() -> Scenario:
    """
    Rare style has a contest (LocalMeasure) that also appears on a second common
    style.  Donors for LocalMeasure must come from that second common style.
    Expected: rare style borrows donors covering all three contests.
    Command: python anonymize_cvr.py testCases/generated/rare_unique_contest.csv /tmp/out.csv
    """
    contests = [
        Contest("President", ["Alice", "Bob"]),
        Contest("Senate", ["Carol", "Dave"]),
        Contest("LocalMeasure", ["Yes", "No"]),
    ]
    ballots = [
        # Style A (common): President + Senate only, 25 ballots.
        BallotSpec(
            ["President", "Senate"], {"President": "Alice", "Senate": "Carol"}, count=13
        ),
        BallotSpec(
            ["President", "Senate"], {"President": "Bob", "Senate": "Dave"}, count=12
        ),
        # Style B (rare): all three contests, 6 ballots.
        BallotSpec(
            ["President", "Senate", "LocalMeasure"],
            {"President": "Alice", "Senate": "Carol", "LocalMeasure": "Yes"},
            count=4,
        ),
        BallotSpec(
            ["President", "Senate", "LocalMeasure"],
            {"President": "Bob", "Senate": "Dave", "LocalMeasure": "No"},
            count=2,
        ),
        # Style C (common): President + LocalMeasure, 20 ballots.
        # Provides donors that cover LocalMeasure for the rare style.
        BallotSpec(
            ["President", "LocalMeasure"],
            {"President": "Alice", "LocalMeasure": "Yes"},
            count=10,
        ),
        BallotSpec(
            ["President", "LocalMeasure"],
            {"President": "Bob", "LocalMeasure": "No"},
            count=10,
        ),
    ]
    return Scenario(
        filename="rare_unique_contest.csv",
        description="Rare style has LocalMeasure; donors for it come from a separate common style.",
        election_name="Test: Rare Unique Contest",
        all_contests=contests,
        ballots=ballots,
    )


def _scenario_near_unanimous_fixable() -> Scenario:
    """
    Rare style (President+JudgeRetention, 8 ballots all voting Alice/Yes) becomes
    near-unanimous in President after borrowing 2 Bob voters.  balance_unanimity()
    then borrows 1 more Bob to push other_votes above NEAR_UNANIMOUS_THRESHOLD.
    Judge Retention has only one choice (Yes) and must not be flagged.

    Styles differ: rare = {President, Judge Retention}, common = {President, Senate,
    Judge Retention}.  The extra Senate contest makes them distinct style strings.

    Expected: near-unanimous President detected then fixed; Judge Retention skipped.
    Command: python anonymize_cvr.py testCases/generated/near_unanimous_fixable.csv /tmp/out.csv
    """
    contests = [
        Contest("President", ["Alice", "Bob"]),
        Contest("Senate", ["Carol", "Dave"]),
        Contest("Judge Retention", ["Yes"]),  # one choice only -- must not be flagged
    ]
    ballots = [
        # Rare style: {President, Judge Retention} (style "101"), 8 ballots, all Alice/Yes.
        BallotSpec(
            ["President", "Judge Retention"],
            {"President": "Alice", "Judge Retention": "Yes"},
            count=8,
        ),
        # Common style: {President, Senate, Judge Retention} (style "111"), 20 ballots.
        # 14 Alice + 6 Bob for President.  build_aggregate borrows 2 Bob (to reduce
        # imbalance), giving 8 Alice + 2 Bob = other_votes=2 = NEAR_UNANIMOUS_THRESHOLD.
        # balance_unanimity then borrows 1 more Bob -> other_votes=3. Fixed.
        BallotSpec(
            ["President", "Senate", "Judge Retention"],
            {"President": "Alice", "Senate": "Carol", "Judge Retention": "Yes"},
            count=14,
        ),
        BallotSpec(
            ["President", "Senate", "Judge Retention"],
            {"President": "Bob", "Senate": "Dave", "Judge Retention": "Yes"},
            count=6,
        ),
    ]
    return Scenario(
        filename="near_unanimous_fixable.csv",
        description="Near-unanimous President fixed by balance_unanimity; one-choice Judge Retention not flagged.",
        election_name="Test: Near-Unanimous Fixable",
        all_contests=contests,
        ballots=ballots,
    )


def _scenario_near_unanimous_unavoidable() -> Scenario:
    """
    Rare style votes unanimously for Alice; all common ballots also vote Alice.
    No contrasting Bob donors exist anywhere.
    Expected: near-unanimous warning printed; not fixable.
    Command: python anonymize_cvr.py testCases/generated/near_unanimous_unavoidable.csv /tmp/out.csv
    """
    contests = [
        Contest("President", ["Alice", "Bob"]),
        Contest("Senate", ["Carol", "Dave"]),
    ]
    ballots = [
        # Rare style: {President} only (style "10"), 8 ballots, all Alice.
        BallotSpec(["President"], {"President": "Alice"}, count=8),
        # Common style: {President, Senate} (style "11"), 20 ballots, all Alice for President.
        # No Bob voters anywhere in the CVR, so near-unanimity cannot be fixed.
        BallotSpec(
            ["President", "Senate"], {"President": "Alice", "Senate": "Carol"}, count=20
        ),
    ]
    return Scenario(
        filename="near_unanimous_unavoidable.csv",
        description="All voters choose Alice; no contrasting donors. Near-unanimity cannot be resolved.",
        election_name="Test: Near-Unanimous Unavoidable",
        all_contests=contests,
        ballots=ballots,
    )


def _scenario_precinct_redaction() -> Scenario:
    """
    For --redact-on-precinct.
    Style A / Precinct P1 has only 5 ballots (rare pair).
    Style A / Precinct P2 and Style B / Precinct P1 are common.
    Expected: only (Style A, P1) is redacted.
    Command: python anonymize_cvr.py --redact-on-precinct
             testCases/generated/precinct_redaction.csv /tmp/out.csv
    """
    contests = [
        Contest("President", ["Alice", "Bob"]),
        Contest("Senate", ["Carol", "Dave"]),
    ]
    ballots = [
        # Style A, Precinct P1: 5 ballots (rare pair).
        BallotSpec(
            ["President", "Senate"],
            {"President": "Alice", "Senate": "Carol"},
            count=3,
            precinct="P1",
        ),
        BallotSpec(
            ["President", "Senate"],
            {"President": "Bob", "Senate": "Dave"},
            count=2,
            precinct="P1",
        ),
        # Style A, Precinct P2: 15 ballots (common pair).
        BallotSpec(
            ["President", "Senate"],
            {"President": "Alice", "Senate": "Carol"},
            count=8,
            precinct="P2",
        ),
        BallotSpec(
            ["President", "Senate"],
            {"President": "Bob", "Senate": "Dave"},
            count=7,
            precinct="P2",
        ),
        # Style B, Precinct P1: 15 ballots (common pair).
        BallotSpec(["President"], {"President": "Alice"}, count=8, precinct="P1"),
        BallotSpec(["President"], {"President": "Bob"}, count=7, precinct="P1"),
    ]
    return Scenario(
        filename="precinct_redaction.csv",
        description="(Style A, P1) is a rare precinct/style pair. Requires --redact-on-precinct.",
        election_name="Test: Precinct Redaction",
        all_contests=contests,
        ballots=ballots,
    )


def _scenario_ballot_type_present() -> Scenario:
    """
    BallotType column is populated.  The common style (President+Senate) has two
    different ballot type values ("1" and "2"), which triggers a leakage warning:
    multiple ballot types share the same contest pattern.
    The rare style (President only) has ballot type "1".

    Ballot type "2" is carried by only 8 ballots, so they are treated as rare too.

    Expected: leakage warning for ballot types [1, 2] on the President+Senate style;
    rare President-only style and the ballot type "2" ballots redacted.
    Command: python anonymize_cvr.py testCases/generated/ballot_type_present.csv /tmp/out.csv
    """
    contests = [
        Contest("President", ["Alice", "Bob"]),
        Contest("Senate", ["Carol", "Dave"]),
    ]
    ballots = [
        # Common style: President + Senate (style "11").
        # Two different ballot types on the same style -> leakage warning.
        BallotSpec(
            ["President", "Senate"],
            {"President": "Alice", "Senate": "Carol"},
            count=10,
            ballot_type="1",
        ),
        BallotSpec(
            ["President", "Senate"],
            {"President": "Bob", "Senate": "Dave"},
            count=8,
            ballot_type="2",
        ),
        # Rare style: President only (style "10"), 6 ballots.
        BallotSpec(["President"], {"President": "Alice"}, count=3, ballot_type="1"),
        BallotSpec(["President"], {"President": "Bob"}, count=3, ballot_type="1"),
    ]
    return Scenario(
        filename="ballot_type_present.csv",
        description="Common style has two ballot types -> leakage warning. Rare President-only style redacted.",
        election_name="Test: Ballot Type Present",
        all_contests=contests,
        ballots=ballots,
    )


def _scenario_named_style() -> Scenario:
    """
    Has a NamedStyle column (column index 7, 0-based).
    The common style (President+Senate) has two different named style values
    ("NS-A" and "NS-B"), which triggers a leakage warning: multiple named styles
    share the same contest pattern.
    The rare style (President only) has named style "NS-RARE".

    NS-B is carried by only 8 ballots, so they are treated as rare too.

    Expected: leakage warning for named styles [NS-A, NS-B] on the President+Senate
    style; rare President-only style and the NS-B ballots redacted.
    Command: python anonymize_cvr.py --stylecol 7
             testCases/generated/named_style.csv /tmp/out.csv
    """
    contests = [
        Contest("President", ["Alice", "Bob"]),
        Contest("Senate", ["Carol", "Dave"]),
    ]
    ballots = [
        # Common style: President + Senate (style "11").
        # Two different named styles on the same contest pattern -> leakage warning.
        BallotSpec(
            ["President", "Senate"],
            {"President": "Alice", "Senate": "Carol"},
            count=10,
            named_style="NS-A",
        ),
        BallotSpec(
            ["President", "Senate"],
            {"President": "Bob", "Senate": "Dave"},
            count=8,
            named_style="NS-B",
        ),
        # Rare style: President only (style "10"), 6 ballots.
        BallotSpec(
            ["President"], {"President": "Alice"}, count=3, named_style="NS-RARE"
        ),
        BallotSpec(["President"], {"President": "Bob"}, count=3, named_style="NS-RARE"),
    ]
    return Scenario(
        filename="named_style.csv",
        description="Common style has two named styles -> leakage warning. Rare President-only style redacted. Use --stylecol 7.",
        election_name="Test: Named Style Column",
        all_contests=contests,
        ballots=ballots,
        include_named_style_col=True,
    )


def _scenario_blocked_style() -> Scenario:
    """
    LocalMeasure contest appears on a rare style (4 ballots) and one common style.
    The common style with LocalMeasure has exactly min_ballots=10 rows (blocked):
    borrowing any single ballot would leave that style with < 10.  Regular borrowing
    fills President and Senate from a different common style, then stalls on
    LocalMeasure.  pull_blocked_style_for() must pull the entire blocked style into
    the aggregate to satisfy the LocalMeasure minimum.
    Expected: no WARNING, tally passes, aggregate includes all three style groups.
    Command: python anonymize_cvr.py testCases/generated/blocked_style.csv /tmp/out.csv
    """
    contests = [
        Contest("President", ["Alice", "Bob"]),
        Contest("Senate", ["Carol", "Dave"]),
        Contest("LocalMeasure", ["Yes", "No"]),
    ]
    ballots = [
        # Rare style: President + Senate + LocalMeasure (style "111"), 4 ballots.
        BallotSpec(
            ["President", "Senate", "LocalMeasure"],
            {"President": "Alice", "Senate": "Carol", "LocalMeasure": "Yes"},
            count=4,
        ),
        # Common style A: President + Senate only (style "110"), 20 ballots.
        # Covers President and Senate but not LocalMeasure.
        BallotSpec(
            ["President", "Senate"],
            {"President": "Alice", "Senate": "Carol"},
            count=10,
        ),
        BallotSpec(
            ["President", "Senate"],
            {"President": "Bob", "Senate": "Dave"},
            count=10,
        ),
        # Blocked style: President + LocalMeasure (style "101"), exactly 10 ballots.
        # Can't donate individual ballots without violating Rule d.
        # pull_blocked_style_for() must pull all 10 into the aggregate.
        BallotSpec(
            ["President", "LocalMeasure"],
            {"President": "Alice", "LocalMeasure": "Yes"},
            count=5,
        ),
        BallotSpec(
            ["President", "LocalMeasure"],
            {"President": "Bob", "LocalMeasure": "No"},
            count=5,
        ),
    ]
    return Scenario(
        filename="blocked_style.csv",
        description="LocalMeasure only on rare style + blocked style (10 ballots). Blocked style pulled whole.",
        election_name="Test: Blocked Style",
        all_contests=contests,
        ballots=ballots,
    )


def _scenario_rare_contest() -> Scenario:
    """
    "Fringe District" is present on only 5 cards county-wide, fewer than
    min_ballots=10, so no aggregate can protect it: it is redacted (Feature A).

    - 2 ballots carry Senate + Fringe.  With Fringe set aside they are an
      2-ballot Senate-only style, still rare, so they are grouped as usual.
    - 3 ballots carry President + Senate + Fringe.  With Fringe set aside they
      join the common President + Senate style and stay visible (CvrNumbers
      48-50).

    Expected: Fringe columns empty on every ballot row, "Redacted" in the
    aggregation line; ballots 46-47 redacted; 48-50 visible.
    Command: python anonymize_cvr.py testCases/generated/rare_contest.csv /tmp/out.csv
    """
    contests = [
        Contest("President", ["Alice", "Bob"]),
        Contest("Senate", ["Carol", "Dave"]),
        Contest("Fringe District", ["Xavier", "Yolanda"]),
    ]
    ballots = [
        # Common style President + Senate, 30 ballots (CvrNumbers 1-30).
        BallotSpec(
            ["President", "Senate"], {"President": "Alice", "Senate": "Carol"}, count=15
        ),
        BallotSpec(
            ["President", "Senate"], {"President": "Bob", "Senate": "Dave"}, count=15
        ),
        # Common style President only, 15 ballots (31-45).
        BallotSpec(["President"], {"President": "Alice"}, count=8),
        BallotSpec(["President"], {"President": "Bob"}, count=7),
        # Senate + Fringe, 2 ballots (46-47): rare even without Fringe.
        BallotSpec(
            ["Senate", "Fringe District"],
            {"Senate": "Carol", "Fringe District": "Xavier"},
            count=1,
        ),
        BallotSpec(
            ["Senate", "Fringe District"],
            {"Senate": "Dave", "Fringe District": "Yolanda"},
            count=1,
        ),
        # President + Senate + Fringe, 3 ballots (48-50): rare only because of
        # Fringe, so they rejoin President + Senate and stay visible.
        BallotSpec(
            ["President", "Senate", "Fringe District"],
            {"President": "Alice", "Senate": "Carol", "Fringe District": "Xavier"},
            count=2,
        ),
        BallotSpec(
            ["President", "Senate", "Fringe District"],
            {"President": "Bob", "Senate": "Dave", "Fringe District": "Yolanda"},
            count=1,
        ),
    ]
    return Scenario(
        filename="rare_contest.csv",
        description="Fringe District on 5 cards: redacted; 3 of its ballots stay visible.",
        election_name="Test: Rare Contest",
        all_contests=contests,
        ballots=ballots,
    )


def _scenario_rare_contest_only() -> Scenario:
    """
    "Fringe District" is present on only 3 cards, and those cards are rare only
    because of it.  With Fringe set aside no ballot is rare, so there is no
    aggregation line to mark it in: the tool adds one that says "Redacted" in
    the Fringe columns and 0 in every other vote column.
    Command: python anonymize_cvr.py testCases/generated/rare_contest_only.csv /tmp/out.csv
    """
    contests = [
        Contest("President", ["Alice", "Bob"]),
        Contest("Senate", ["Carol", "Dave"]),
        Contest("Fringe District", ["Xavier", "Yolanda"]),
    ]
    ballots = [
        BallotSpec(
            ["President", "Senate"], {"President": "Alice", "Senate": "Carol"}, count=15
        ),
        BallotSpec(
            ["President", "Senate"], {"President": "Bob", "Senate": "Dave"}, count=15
        ),
        BallotSpec(["President"], {"President": "Alice"}, count=8),
        BallotSpec(["President"], {"President": "Bob"}, count=7),
        BallotSpec(
            ["President", "Senate", "Fringe District"],
            {"President": "Alice", "Senate": "Carol", "Fringe District": "Xavier"},
            count=2,
        ),
        BallotSpec(
            ["President", "Senate", "Fringe District"],
            {"President": "Bob", "Senate": "Dave", "Fringe District": "Yolanda"},
            count=1,
        ),
    ]
    return Scenario(
        filename="rare_contest_only.csv",
        description="Fringe District on 3 cards, no rare ballots otherwise: Redacted line added.",
        election_name="Test: Rare Contest Only",
        all_contests=contests,
        ballots=ballots,
    )


def _scenario_county_blanked_contest() -> Scenario:
    """
    "Blanked Measure" is in the header but present on no card, as when a county
    has emptied a rare contest itself.  It reveals nothing, so the tool leaves it
    alone: it is not reported, and the aggregation line has 0 in its columns,
    not "Redacted".  A rare Senate-only style makes the tool write an output.
    Command: python anonymize_cvr.py testCases/generated/county_blanked_contest.csv /tmp/out.csv
    """
    contests = [
        Contest("President", ["Alice", "Bob"]),
        Contest("Senate", ["Carol", "Dave"]),
        Contest("Blanked Measure", ["Yes", "No"]),
    ]
    ballots = [
        BallotSpec(
            ["President", "Senate"], {"President": "Alice", "Senate": "Carol"}, count=15
        ),
        BallotSpec(
            ["President", "Senate"], {"President": "Bob", "Senate": "Dave"}, count=15
        ),
        BallotSpec(["Senate"], {"Senate": "Carol"}, count=2),
        BallotSpec(["Senate"], {"Senate": "Dave"}, count=2),
    ]
    return Scenario(
        filename="county_blanked_contest.csv",
        description="Blanked Measure on no card: left alone, not marked Redacted.",
        election_name="Test: County-Blanked Contest",
        all_contests=contests,
        ballots=ballots,
    )


def _scenario_rare_ballot_type() -> Scenario:
    """
    BallotType "BT-9" is carried by only 3 ballots, which share the common
    President + Senate fingerprint with 22 "BT-1" ballots.  The fingerprint is
    common, so the rarity check on fingerprints alone would never group them,
    and they would ship with visible votes next to a label that picks them out
    (Feature B).  No style is rare.

    Expected: 'BT-9': 3 ballot(s) reported with the ballot-image warning, and
    redaction needed.  By default those ballots (CvrNumbers 23-25) are treated
    as rare and aggregated; with --drop-ballottype the BallotType column is
    dropped instead and they stay visible.
    Command: python anonymize_cvr.py testCases/generated/rare_ballot_type.csv /tmp/out.csv
    """
    contests = [
        Contest("President", ["Alice", "Bob"]),
        Contest("Senate", ["Carol", "Dave"]),
    ]
    ballots = [
        BallotSpec(
            ["President", "Senate"],
            {"President": "Alice", "Senate": "Carol"},
            count=12,
            ballot_type="BT-1",
        ),
        BallotSpec(
            ["President", "Senate"],
            {"President": "Bob", "Senate": "Dave"},
            count=10,
            ballot_type="BT-1",
        ),
        BallotSpec(
            ["President", "Senate"],
            {"President": "Alice", "Senate": "Dave"},
            count=3,
            ballot_type="BT-9",
        ),
        BallotSpec(["President"], {"President": "Alice"}, count=8, ballot_type="BT-2"),
        BallotSpec(["President"], {"President": "Bob"}, count=7, ballot_type="BT-2"),
    ]
    return Scenario(
        filename="rare_ballot_type.csv",
        description="BallotType BT-9 on 3 ballots of a common fingerprint: reported; dropped on request.",
        election_name="Test: Rare Ballot Type Label",
        all_contests=contests,
        ballots=ballots,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    scenarios = [
        _scenario_no_redaction(),
        _scenario_needs_borrowing(),
        _scenario_rare_unique_contest(),
        _scenario_near_unanimous_fixable(),
        _scenario_near_unanimous_unavoidable(),
        _scenario_precinct_redaction(),
        _scenario_ballot_type_present(),
        _scenario_named_style(),
        _scenario_blocked_style(),
        _scenario_rare_contest(),
        _scenario_rare_contest_only(),
        _scenario_county_blanked_contest(),
        _scenario_rare_ballot_type(),
    ]

    print(f"Writing test CVR files to {OUTPUT_DIR}/")
    for scenario in scenarios:
        _write_cvr(scenario)
    print(f"\nDone. {len(scenarios)} files written.")


if __name__ == "__main__":
    main()
