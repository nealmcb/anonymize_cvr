#!/usr/bin/env python3
"""
Anonymize Cast Vote Records (CVR) by aggregating rare styles.

This module addresses the requirement from Colorado Election Rule that CVRs
with fewer than 10 ballots per style must be anonymized to protect voter privacy.
Rare styles are aggregated together to meet the minimum threshold.

Based on:
- Colorado Risk-Limiting Tabulation Audit: Preserving Anonymity of Cast Vote Record
  (Branscomb et al., March 9, 2018)
- Election Rule 21 (CVR definition)
- C.R.S. 24-72-205.5 (Open Records Act requirement for < 10 ballots per style)
"""

import csv
import sys
from collections import defaultdict
from typing import List, Dict, Tuple, Any, Optional, Iterable

from cvr_utils import TempCVRFile, is_parquet_file


def pull_style_signature(row: List[str], headerlen: int = 8, stylecol: int = 6) -> str:
    """
    Convert a CVR row into a style signature string based solely on contest pattern.

    The signature includes only the contest bitmap:
    - For each vote column: "1" if vote was allowed (non-empty), "0" if empty (contest not on ballot)

    PrecinctPortion is not used in the signature to avoid relying on geographic information.
    Styles are identified purely by which contests appear on the ballot.

    Args:
        row: List of strings representing a CVR row
        headerlen: Number of header columns before vote data starts (default 8)
        stylecol: Index of the style column (unused, kept for compatibility)

    Returns:
        Style signature string (contest bitmap only)
    """
    # For each vote column, indicate if contest appeared on ballot (1) or not (0)
    vote_indicators = ["1" if vote.strip() != "" else "0" for vote in row[headerlen:]]
    return "".join(vote_indicators)


def aggregate_votes(
    rows: List[List[str]],
    headerlen: int = 8,
    aggregate_id: str = "",
    ballot_type_idx: Optional[int] = None,
) -> List[str]:
    """
    Aggregate multiple CVR rows into a single aggregated row.

    Sums vote counts for each choice column, anonymizing header information.

    Args:
        rows: List of CVR rows to aggregate
        headerlen: Number of header columns before vote data starts
        aggregate_id: Identifier for this aggregate (e.g., "AGGREGATED-1")

    Returns:
        Single aggregated row as a list of strings
    """
    if not rows:
        return []

    # Create header with anonymized identifiers
    # Format: [CvrNumber, TabulatorNum, BatchId, RecordId, ImprintedId,
    #          CountingGroup, PrecinctPortion, BallotType, ...vote columns...]
    aggregated = rows[0][:headerlen].copy()

    # Anonymize identifying fields (indices 0-4: CvrNumber, TabulatorNum, BatchId, RecordId, ImprintedId)
    if aggregate_id:
        aggregated[0] = aggregate_id  # CvrNumber
    else:
        aggregated[0] = f"AGG-{len(rows)}"  # Indicate this is an aggregate
    
    # Blank TabulatorNum, BatchId, RecordId, and ImprintedId to avoid revealing identifying information
    if len(aggregated) > 1:
        aggregated[1] = ""  # TabulatorNum
    if len(aggregated) > 2:
        aggregated[2] = ""  # BatchId
    if len(aggregated) > 3:
        aggregated[3] = ""  # RecordId
    if len(aggregated) > 4:
        aggregated[4] = ""  # ImprintedId

    # CountingGroup (index 5) - blank to avoid revealing additional information
    if len(aggregated) > 5:
        aggregated[5] = ""

    # PrecinctPortion (index 6) - blank to avoid revealing geographic/precinct information
    if len(aggregated) > 6:
        aggregated[6] = ""

    # BallotType - set to "AGGREGATED" for aggregated rows (if column exists)
    if ballot_type_idx is not None:
        if len(aggregated) > ballot_type_idx:
            aggregated[ballot_type_idx] = "AGGREGATED"
    elif len(aggregated) > 7:
        aggregated[7] = "AGGREGATED"

    # Aggregate vote columns (sum numeric values)
    num_cols = max(len(row) for row in rows)
    for col_idx in range(headerlen, num_cols):
        total = 0
        for row in rows:
            if col_idx < len(row):
                val = row[col_idx].strip()
                if val and val.replace(".", "").replace("-", "").isdigit():
                    try:
                        total += float(val)
                    except ValueError:
                        pass  # Skip non-numeric values
        aggregated.append(str(int(total)) if total == int(total) else str(total))

    return aggregated


def style_similarity(sig1: str, sig2: str) -> float:
    """
    Calculate similarity between two style signatures based on contest overlap.

    Returns Jaccard similarity of contest presence (the binary string after first 3 chars).
    Higher values indicate more similar styles (share more contests).

    Args:
        sig1: First style signature
        sig2: Second style signature

    Returns:
        Similarity score between 0.0 and 1.0
    """
    # Extract contest patterns (everything after first 3 characters)
    pattern1 = sig1[3:] if len(sig1) > 3 else ""
    pattern2 = sig2[3:] if len(sig2) > 3 else ""

    # Pad to same length
    max_len = max(len(pattern1), len(pattern2))
    pattern1 = pattern1.ljust(max_len, "0")
    pattern2 = pattern2.ljust(max_len, "0")

    # Count overlapping contests (both have the contest)
    intersection = sum(1 for a, b in zip(pattern1, pattern2) if a == "1" and b == "1")
    union = sum(1 for a, b in zip(pattern1, pattern2) if a == "1" or b == "1")

    if union == 0:
        return 1.0 if pattern1 == pattern2 else 0.0

    return intersection / union


def tally_cvr_votes(
    rows: List[List[str]],
    contests: List[str],
    choices: List[str],
    headerlen: int = 8,
) -> Dict[str, Dict[str, int]]:
    """
    Tally votes from CVR rows (handles both individual ballots and aggregated rows).

    Args:
        rows: List of CVR data rows (individual ballots or aggregated rows)
        contests: Contest names row from CVR header
        choices: Choice names row from CVR header
        headerlen: Number of header columns before vote data starts

    Returns:
        Dictionary mapping contest names to dictionaries of choice names to vote counts
    """
    # Map contest names to their column indices
    contest_to_columns: Dict[str, List[tuple]] = defaultdict(list)
    for col_idx in range(headerlen, len(contests)):
        contest_name = contests[col_idx].strip()
        if contest_name and col_idx < len(choices):
            choice_name = choices[col_idx].strip()
            contest_to_columns[contest_name].append((col_idx, choice_name))

    # Tally votes for each contest
    contest_totals: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        if len(row) <= headerlen:
            continue

        # Check if this is an aggregated row (CvrNumber starts with "AGGREGATED-")
        is_aggregated = len(row) > 0 and row[0].strip().startswith("AGGREGATED-")

        for contest_name, col_choice_pairs in contest_to_columns.items():
            for col_idx, choice_name in col_choice_pairs:
                if col_idx < len(row):
                    val = row[col_idx].strip()
                    if val:
                        try:
                            if is_aggregated:
                                # Aggregated row: value is already a count
                                vote_count = int(float(val))
                            else:
                                # Individual ballot: value is 0 or 1
                                vote_count = 1 if (val == "1" or val == 1) else 0

                            if vote_count > 0:
                                contest_totals[contest_name][choice_name] += vote_count
                        except (ValueError, TypeError):
                            pass

    return dict(contest_totals)


def tally_aggregated_votes_by_contest(
    aggregated_row: List[str],
    contests: List[str],
    choices: List[str],
    headerlen: int = 8,
) -> Dict[str, Dict[str, int]]:
    """
    Tally votes from an aggregated row by contest and choice.

    Args:
        aggregated_row: Aggregated CVR row (with vote counts as integers)
        contests: Contest names row from CVR header
        choices: Choice names row from CVR header
        headerlen: Number of header columns before vote data starts

    Returns:
        Dictionary mapping contest names to dictionaries of choice names to vote counts
    """
    return tally_cvr_votes([aggregated_row], contests, choices, headerlen)


def verify_tally_match(
    original_file: str,
    anonymized_file: str,
    headerlen: int = 8,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Verify that vote tallies in anonymized CVR match the original CVR.

    Args:
        original_file: Path to original CVR file
        anonymized_file: Path to anonymized CVR file
        headerlen: Number of header columns before vote data starts

    Returns:
        Tuple of (match: bool, details: dict) where details contains mismatch information
    """
    from cvr_utils import TempCVRFile, is_parquet_file

    # Read original CVR
    with TempCVRFile(original_file) as orig_csv:
        with open(orig_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            orig_version = next(reader)
            orig_contests = next(reader)
            orig_choices = next(reader)
            orig_headers = next(reader)
            orig_rows = list(reader)

    # Read anonymized CVR
    with TempCVRFile(anonymized_file) as anon_csv:
        with open(anon_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            anon_version = next(reader)
            anon_contests = next(reader)
            anon_choices = next(reader)
            anon_headers = next(reader)
            anon_rows = list(reader)

    # Tally votes
    orig_totals = tally_cvr_votes(orig_rows, orig_contests, orig_choices, headerlen)
    anon_totals = tally_cvr_votes(anon_rows, anon_contests, anon_choices, headerlen)

    # Compare tallies
    all_contests = set(orig_totals.keys()) | set(anon_totals.keys())
    mismatches = []
    match = True

    for contest_name in sorted(all_contests):
        orig_choices_dict = orig_totals.get(contest_name, {})
        anon_choices_dict = anon_totals.get(contest_name, {})

        all_choices = set(orig_choices_dict.keys()) | set(anon_choices_dict.keys())
        for choice_name in sorted(all_choices):
            orig_count = orig_choices_dict.get(choice_name, 0)
            anon_count = anon_choices_dict.get(choice_name, 0)
            if orig_count != anon_count:
                match = False
                mismatches.append(
                    {
                        "contest": contest_name,
                        "choice": choice_name,
                        "original": orig_count,
                        "anonymized": anon_count,
                        "difference": anon_count - orig_count,
                    }
                )

    details = {
        "match": match,
        "mismatches": mismatches,
        "original_totals": orig_totals,
        "anonymized_totals": anon_totals,
    }

    return match, details


def check_unanimous_patterns(
    contest_totals: Dict[str, Dict[str, int]], total_ballots: int
) -> List[tuple]:
    """
    Check for unanimous or near-unanimous vote patterns in aggregated results.

    A pattern is considered near-unanimous if all but 2 votes (or fewer) are for the same candidate.

    Args:
        contest_totals: Dictionary mapping contest names to choice vote counts
        total_ballots: Total number of ballots in the aggregation

    Returns:
        List of tuples (contest_name, winning_choice, vote_count, total_votes) for unanimous/near-unanimous contests
    """
    problematic_contests = []
    for contest_name, choice_votes in contest_totals.items():
        if not choice_votes:
            continue

        total_votes = sum(choice_votes.values())
        if total_votes == 0:
            continue

        # Find the choice with the most votes
        max_choice = max(choice_votes.items(), key=lambda x: x[1])
        max_votes = max_choice[1]
        other_votes = total_votes - max_votes

        # Check if all but 2 or fewer votes are for the same candidate
        # (near-unanimous: at most 2 votes for other candidates)
        if other_votes <= 2:
            problematic_contests.append(
                (contest_name, max_choice[0], max_votes, total_votes)
            )

    return problematic_contests


def find_ballots_with_contest(
    contest_name: str,
    common_styles: Dict[str, List[List[str]]],
    contests: List[str],
    headerlen: int = 8,
    min_ballots: int = 10,
    needed_count: int = 10,
    exclude_cvr_numbers: set = None,
) -> List[List[str]]:
    """
    Find ballots from common styles that have a specific contest.

    Args:
        contest_name: Contest name to find ballots for
        common_styles: Dictionary of common style signatures to their ballot rows
        contests: Contest names row from CVR header
        headerlen: Number of header columns before vote data starts
        min_ballots: Minimum ballots per style (common styles must have > this)
        needed_count: Number of ballots needed
        exclude_cvr_numbers: Set of CvrNumbers to exclude (already used)

    Returns:
        List of ballot rows that have the specified contest
    """
    if exclude_cvr_numbers is None:
        exclude_cvr_numbers = set()

    # Find column indices for the contest
    contest_col_indices = []
    for col_idx in range(headerlen, len(contests)):
        if contests[col_idx].strip() == contest_name:
            contest_col_indices.append(col_idx)

    if not contest_col_indices:
        return []  # Contest not found

    found_ballots = []
    for style_sig, rows in common_styles.items():
        if len(rows) <= min_ballots:
            continue  # Only use styles with more than min_ballots

        for row in rows:
            if len(row) <= headerlen:
                continue

            # Check CvrNumber
            if len(row) > 0:
                cvr_num = row[0].strip()
                if cvr_num in exclude_cvr_numbers:
                    continue

            # Check if this ballot has the contest (any column for this contest is non-empty)
            has_contest = any(
                col_idx < len(row) and row[col_idx].strip() != ""
                for col_idx in contest_col_indices
            )

            if has_contest:
                found_ballots.append(row)
                if len(found_ballots) >= needed_count:
                    return found_ballots

    return found_ballots


def find_contrasting_ballots_multi(
    problematic_contests: List[tuple],
    common_styles: Dict[str, List[List[str]]],
    contests: List[str],
    choices: List[str],
    headerlen: int = 8,
    min_ballots: int = 10,
) -> List[List[str]]:
    """
    Find ballots from common styles that vote differently for multiple problematic contests.

    This minimizes the number of ballots needed by finding ballots that satisfy multiple
    contrasting vote requirements simultaneously.

    Args:
        problematic_contests: List of tuples (contest_name, winning_choice, vote_count, total_votes)
        common_styles: Dictionary of common style signatures to their ballot rows
        contests: Contest names row from CVR header
        choices: Choice names row from CVR header
        headerlen: Number of header columns before vote data starts
        min_ballots: Minimum ballots per style (common styles must have > this)

    Returns:
        List of ballot rows that vote differently in one or more problematic contests
    """
    if not problematic_contests:
        return []

    # Build mapping of contest to column indices and winning choice column
    contest_info = {}
    for contest_name, winning_choice, _, _ in problematic_contests:
        contest_col_indices = []
        for col_idx in range(headerlen, len(contests)):
            if contests[col_idx].strip() == contest_name:
                contest_col_indices.append(col_idx)

        if not contest_col_indices:
            continue

        # Find winning choice column index
        winning_col_idx = None
        for col_idx in contest_col_indices:
            if col_idx < len(choices) and choices[col_idx].strip() == winning_choice:
                winning_col_idx = col_idx
                break

        contest_info[contest_name] = {
            "col_indices": contest_col_indices,
            "winning_col_idx": winning_col_idx,
        }

    # Score each ballot by how many problematic contests it votes differently in
    ballot_scores = []
    for style_sig, rows in common_styles.items():
        if len(rows) <= min_ballots:
            continue  # Only use styles with more than min_ballots

        for row in rows:
            if len(row) <= headerlen:
                continue

            # Check which problematic contests this ballot votes differently in
            satisfied_contests = []
            for contest_name, _, _, _ in problematic_contests:
                if contest_name not in contest_info:
                    continue

                info = contest_info[contest_name]
                contest_col_indices = info["col_indices"]
                winning_col_idx = info["winning_col_idx"]

                # Check if ballot has this contest
                has_contest = any(
                    col_idx < len(row) and row[col_idx].strip() != ""
                    for col_idx in contest_col_indices
                )
                if not has_contest:
                    continue

                # Check if votes differently
                votes_differently = False
                if winning_col_idx is not None and winning_col_idx < len(row):
                    if row[winning_col_idx].strip() != "1":
                        # Check if voted for any other choice
                        for col_idx in contest_col_indices:
                            if col_idx != winning_col_idx and col_idx < len(row):
                                if row[col_idx].strip() == "1":
                                    votes_differently = True
                                    satisfied_contests.append(contest_name)
                                    break

            if satisfied_contests:
                # Score: number of contests satisfied, prefer ballots that satisfy more
                ballot_scores.append((len(satisfied_contests), satisfied_contests, row))

    # Sort by score (highest first) to prioritize ballots that satisfy multiple contests
    ballot_scores.sort(key=lambda x: x[0], reverse=True)

    # Greedily select ballots to cover all problematic contests
    # Track which contests still need contrasting votes
    contests_needed = {contest_name for contest_name, _, _, _ in problematic_contests}
    selected_ballots = []
    satisfied_contests_set = set()

    for score, satisfied, row in ballot_scores:
        # Check if this ballot helps with any remaining needed contests
        row_contests = set(satisfied)
        if row_contests & contests_needed:
            selected_ballots.append(row)
            satisfied_contests_set.update(row_contests)
            contests_needed -= row_contests

            # If we've satisfied all contests, we might still need a few more
            # to ensure we have at least 3 contrasting votes per contest
            if not contests_needed:
                # Count how many ballots we have for each contest
                contest_counts = {}
                for _, satisfied_list, _ in ballot_scores[: len(selected_ballots)]:
                    for c in satisfied_list:
                        contest_counts[c] = contest_counts.get(c, 0) + 1

                # Check if we need more for any contest (want at least 3)
                all_sufficient = True
                for contest_name, _, _, _ in problematic_contests:
                    if contest_counts.get(contest_name, 0) < 3:
                        all_sufficient = False
                        contests_needed.add(contest_name)

                if all_sufficient:
                    break

    return selected_ballots


def compute_contest_pattern(row: List[str], contests: List[str], headerlen: int = 8) -> str:
    """
    Compute contest pattern from a ballot row based solely on which contests have votes.

    Returns a binary string indicating which contests appear on the ballot (1) or not (0).
    A contest appears if any of its choice columns is non-empty.

    Args:
        row: List of strings representing a CVR row
        contests: Contest names row from CVR header
        headerlen: Number of header columns before vote data starts

    Returns:
        Binary string pattern (e.g., "110" means contests 1 and 2 appear, 3 doesn't)
    """
    # Group columns by contest
    contest_to_columns: Dict[str, List[int]] = defaultdict(list)
    for col_idx in range(headerlen, len(contests)):
        contest_name = contests[col_idx].strip()
        if contest_name:
            contest_to_columns[contest_name].append(col_idx)

    # Check if each contest appears (any column for that contest is non-empty)
    contest_pattern = []
    for contest_name in sorted(contest_to_columns.keys()):
        col_indices = contest_to_columns[contest_name]
        contest_appears = any(
            col_idx < len(row) and row[col_idx].strip() != "" for col_idx in col_indices
        )
        contest_pattern.append("1" if contest_appears else "0")

    return "".join(contest_pattern)


def compute_descriptive_style_name(
    contest_pattern: str, ballot_count: int, style_number: int, min_ballots: int = 10
) -> str:
    """
    Compute a descriptive style name based on contest pattern.

    Format: <n><R|S><m>
    - n: number of contests on the ballot
    - R: Rare (less than min_ballots) or S: Common (min_ballots or more)
    - m: unique style number

    Args:
        contest_pattern: Binary string indicating which contests appear
        ballot_count: Number of ballots with this pattern
        style_number: Unique sequential number for this style
        min_ballots: Minimum ballots to be considered common

    Returns:
        Descriptive style name (e.g., "1R1", "2S2", "1S3")
    """
    contest_count = contest_pattern.count("1")
    rarity = "R" if ballot_count < min_ballots else "S"
    return f"{contest_count}{rarity}{style_number}"


def update_choice_counts_from_row(
    row: List[str],
    contest_choice_counts: Dict[str, Dict[str, int]],
    contest_choice_meta: Dict[str, Dict[int, str]],
) -> None:
    """
    Update contest choice counts using the votes in a single row (ballot).
    """
    for contest_name, col_map in contest_choice_meta.items():
        if contest_name not in contest_choice_counts:
            contest_choice_counts[contest_name] = {}

        for col_idx, choice_name in col_map.items():
            if col_idx >= len(row):
                continue
            value = row[col_idx].strip()
            if not value or value == "0":
                continue
            try:
                increment = int(float(value))
            except ValueError:
                increment = 1
            contest_choice_counts[contest_name][choice_name] = (
                contest_choice_counts[contest_name].get(choice_name, 0) + increment
            )


def compute_imbalance_gain_for_ballot(
    contest_name: str,
    row: List[str],
    contest_choice_counts: Dict[str, Dict[str, int]],
    contest_choice_meta: Dict[str, Dict[int, str]],
) -> float:
    """
    Estimate how much a ballot will reduce vote imbalance for a contest.
    Imbalance metric: max_votes - sum(other_votes).
    """
    if contest_name not in contest_choice_meta:
        return 0.0

    choice_counts = contest_choice_counts.get(contest_name, {})
    total_votes = sum(choice_counts.values())
    current_max = max(choice_counts.values()) if choice_counts else 0
    current_others = total_votes - current_max
    current_gap = current_max - current_others

    contributions: Dict[str, int] = {}
    for col_idx, choice_name in contest_choice_meta[contest_name].items():
        if col_idx >= len(row):
            continue
        value = row[col_idx].strip()
        if not value or value == "0":
            continue
        contributions[choice_name] = contributions.get(choice_name, 0) + 1

    if not contributions:
        return 0.0

    new_counts = dict(choice_counts)
    for choice_name, inc in contributions.items():
        new_counts[choice_name] = new_counts.get(choice_name, 0) + inc

    new_total = total_votes + sum(contributions.values())
    new_max = max(new_counts.values()) if new_counts else 0
    new_others = new_total - new_max
    new_gap = new_max - new_others

    improvement = current_gap - new_gap
    return max(0.0, improvement)


def determine_contests_for_row(
    row: List[str],
    contest_names: List[str],
    contest_to_columns: Dict[str, Iterable[int]],
) -> List[str]:
    """
    Determine which contests appear on a ballot row.
    """
    contests_for_row: List[str] = []
    for contest_name in contest_names:
        col_indices = contest_to_columns.get(contest_name, [])
        if any(col_idx < len(row) and row[col_idx].strip() != "" for col_idx in col_indices):
            contests_for_row.append(contest_name)
    return contests_for_row


def update_contest_presence_counts(
    row: List[str],
    contest_names: List[str],
    contest_to_columns: Dict[str, Iterable[int]],
    ballot_counts: Dict[str, int],
    ballot_with_vote_counts: Dict[str, int],
) -> None:
    """
    Update contest presence counts (ballots containing contest and ballots casting votes).
    """
    for contest_name in contest_names:
        col_indices = contest_to_columns.get(contest_name, [])
        contest_present = False
        contest_has_vote = False
        for col_idx in col_indices:
            if col_idx >= len(row):
                continue
            val = row[col_idx].strip()
            if val != "":
                contest_present = True
                if val != "0":
                    contest_has_vote = True
        if contest_present:
            ballot_counts[contest_name] += 1
            if contest_has_vote:
                ballot_with_vote_counts[contest_name] += 1


def select_balancing_ballot(
    common_styles: Dict[str, List[List[str]]],
    contests_needing_ballots: Dict[str, int],
    contest_to_columns: Dict[str, List[int]],
    contest_choice_counts: Dict[str, Dict[str, int]],
    contest_choice_meta: Dict[str, Dict[int, str]],
    aggregation_cvr_numbers: set,
    min_ballots: int,
) -> Optional[Tuple[str, int, List[str], List[str], float]]:
    """
    Select the ballot that best improves contest coverage and vote balance.

    Returns:
        Tuple of (style_signature, row_index, row, contests_covered, imbalance_gain)
    """
    coverage_weight = 10.0
    best_candidate = None
    best_score = -1.0
    needed_contests = [contest for contest, need in contests_needing_ballots.items() if need > 0]

    if not needed_contests:
        return None

    for style_sig, rows in common_styles.items():
        # Avoid borrowing from styles that would become rare
        if len(rows) <= min_ballots:
            continue

        for idx, row in enumerate(rows):
            if not row:
                continue
            cvr_num = row[0].strip()
            if cvr_num and cvr_num in aggregation_cvr_numbers:
                continue

            contests_for_row = determine_contests_for_row(row, needed_contests, contest_to_columns)
            if not contests_for_row:
                continue

            coverage = len(contests_for_row)
            imbalance_gain = 0.0
            for contest_name in contests_for_row:
                imbalance_gain += compute_imbalance_gain_for_ballot(
                    contest_name, row, contest_choice_counts, contest_choice_meta
                )

            score = coverage_weight * coverage + imbalance_gain
            if score > best_score:
                best_score = score
                best_candidate = (style_sig, idx, row, contests_for_row, imbalance_gain)

    return best_candidate


def analyze_styles(
    all_rows: List[List[str]],
    contests: List[str],
    choices: List[str],
    headerlen: int = 8,
    stylecol: int = 6,
    min_ballots: int = 10,
    summarize: bool = False,
    ballot_type_idx: Optional[int] = None,
) -> Dict[str, any]:
    """
    Analyze styles in the CVR file.

    Computes descriptive style names based on contest patterns and checks for leakage.

    Args:
        all_rows: All data rows from CVR
        contests: Contest names row
        choices: Choice names row
        headerlen: Number of header columns
        stylecol: Index of style column
        min_ballots: Minimum ballots per style
        summarize: Whether to include detailed summaries

    Returns:
        Dictionary with analysis results including leakage warnings
    """
    # Group ballots by contest pattern (which contests appear)
    pattern_to_rows: Dict[str, List[List[str]]] = defaultdict(list)
    cvr_style_to_rows: Dict[str, List[List[str]]] = defaultdict(list)

    for row in all_rows:
        if len(row) <= headerlen:
            continue

        # Compute contest pattern
        contest_pattern = compute_contest_pattern(row, contests, headerlen)
        pattern_to_rows[contest_pattern].append(row)

        # Track CVR style name
        if len(row) > stylecol:
            cvr_style = row[stylecol].strip()
            cvr_style_to_rows[cvr_style].append(row)

    # Generate descriptive style names for each contest pattern
    pattern_to_descriptive: Dict[str, str] = {}
    style_counter = 1
    for pattern in sorted(pattern_to_rows.keys()):
        ballot_count = len(pattern_to_rows[pattern])
        descriptive_name = compute_descriptive_style_name(
            pattern, ballot_count, style_counter, min_ballots
        )
        pattern_to_descriptive[pattern] = descriptive_name
        style_counter += 1

    # Check for leakage: different CVR style names or BallotTypes for same contest pattern
    leakage_warnings = []
    pattern_to_cvr_styles: Dict[str, set] = defaultdict(set)
    pattern_to_ballot_types: Dict[str, set] = defaultdict(set)

    for row in all_rows:
        if len(row) <= headerlen or len(row) <= stylecol:
            continue

        contest_pattern = compute_contest_pattern(row, contests, headerlen)
        cvr_style = row[stylecol].strip()
        pattern_to_cvr_styles[contest_pattern].add(cvr_style)
        
        # Check BallotType column if known
        if ballot_type_idx is not None and len(row) > ballot_type_idx:
            ballot_type = row[ballot_type_idx].strip()
            if ballot_type:  # Only track non-empty BallotTypes
                pattern_to_ballot_types[contest_pattern].add(ballot_type)

    for pattern, cvr_styles in pattern_to_cvr_styles.items():
        if len(cvr_styles) > 1:
            descriptive_name = pattern_to_descriptive[pattern]
            leakage_warnings.append(
                f"Leakage detected: Contest pattern '{pattern}' (descriptive style '{descriptive_name}') "
                f"has {len(cvr_styles)} different CVR style names: {sorted(cvr_styles)}. "
                f"This may reveal additional information about voters."
            )
    
    # Check if BallotType varies for same contest pattern
    if ballot_type_idx is not None:
        for pattern, ballot_types in pattern_to_ballot_types.items():
            if len(ballot_types) > 1:
                descriptive_name = pattern_to_descriptive[pattern]
                leakage_warnings.append(
                    f"Warning: Contest pattern '{pattern}' (descriptive style '{descriptive_name}') "
                    f"has {len(ballot_types)} different BallotType values: {sorted(ballot_types)}. "
                    f"BallotType is preserved in output - ensure it doesn't reveal identifying information."
                )

    # Build mapping from CVR style to descriptive style
    cvr_to_descriptive: Dict[str, str] = {}
    for cvr_style, rows in cvr_style_to_rows.items():
        if rows:
            pattern = compute_contest_pattern(rows[0], contests, headerlen)
            cvr_to_descriptive[cvr_style] = pattern_to_descriptive[pattern]

    result = {
        "pattern_to_descriptive": pattern_to_descriptive,
        "cvr_to_descriptive": cvr_to_descriptive,
        "leakage_warnings": leakage_warnings,
        "pattern_to_rows": pattern_to_rows,
    }

    # Optional summary
    if summarize:
        summary = generate_summary(
            all_rows, contests, choices, pattern_to_rows, pattern_to_descriptive, headerlen
        )
        result["summary"] = summary

    return result


def generate_summary(
    all_rows: List[List[str]],
    contests: List[str],
    choices: List[str],
    pattern_to_rows: Dict[str, List[List[str]]],
    pattern_to_descriptive: Dict[str, str],
    headerlen: int,
) -> Dict[str, any]:
    """Generate summary statistics for the CVR."""
    # Map contest names to column indices
    contest_to_columns: Dict[str, List[int]] = defaultdict(list)
    for col_idx in range(headerlen, len(contests)):
        contest_name = contests[col_idx].strip()
        if contest_name:
            contest_to_columns[contest_name].append(col_idx)

    # Calculate totals by contest for each choice
    contest_totals: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in all_rows:
        for contest_name, col_indices in contest_to_columns.items():
            for col_idx in col_indices:
                if col_idx < len(row):
                    val = row[col_idx].strip()
                    if val and (val == "1" or val == "0"):
                        choice_name = (
                            choices[col_idx].strip()
                            if col_idx < len(choices)
                            else f"Choice{col_idx}"
                        )
                        if val == "1":
                            contest_totals[contest_name][choice_name] += 1

    # Calculate ballot counts and probabilities for each style
    style_stats: Dict[str, Dict[str, any]] = {}
    for pattern, rows in pattern_to_rows.items():
        descriptive_name = pattern_to_descriptive[pattern]

        # Count votes for each choice in this style
        choice_votes: Dict[str, int] = defaultdict(int)
        eligible_voters: Dict[str, int] = defaultdict(int)

        for row in rows:
            for contest_name, col_indices in contest_to_columns.items():
                # Check if any column for this contest is non-empty (contest appears)
                contest_appears = any(
                    col_idx < len(row) and row[col_idx].strip() != "" for col_idx in col_indices
                )

                if contest_appears:
                    eligible_voters[contest_name] += 1
                    for col_idx in col_indices:
                        if col_idx < len(row):
                            val = row[col_idx].strip()
                            choice_name = (
                                choices[col_idx].strip()
                                if col_idx < len(choices)
                                else f"Choice{col_idx}"
                            )
                            if val == "1":
                                choice_votes[choice_name] += 1

        # Calculate probabilities
        probabilities: Dict[str, Dict[str, float]] = {}
        for contest_name in contest_to_columns.keys():
            if contest_name in eligible_voters and eligible_voters[contest_name] > 0:
                prob_dict = {}
                for col_idx in contest_to_columns[contest_name]:
                    choice_name = (
                        choices[col_idx].strip() if col_idx < len(choices) else f"Choice{col_idx}"
                    )
                    votes = choice_votes.get(choice_name, 0)
                    prob = votes / eligible_voters[contest_name]
                    prob_dict[choice_name] = prob
                probabilities[contest_name] = prob_dict

        style_stats[descriptive_name] = {
            "ballot_count": len(rows),
            "contest_pattern": pattern,
            "probabilities": probabilities,
        }

    return {"contest_totals": dict(contest_totals), "style_stats": style_stats}


def anonymize_cvr(
    input_file: str,
    output_file: str,
    min_ballots: int = 10,
    stylecol: int = 6,
    headerlen: int = 8,
    summarize: bool = False,
) -> Dict[str, int]:
    """
    Anonymize a CVR file by aggregating rare styles.

    Reads a CVR file (CSV or Parquet format), identifies styles with fewer than min_ballots,
    and aggregates them into one or more aggregated rows to meet the threshold.

    Args:
        input_file: Path to input CVR file (CSV or Parquet format)
        output_file: Path to output anonymized CVR file
        min_ballots: Minimum number of ballots required per style (default 10)
        stylecol: Index of the style column (default 6 for PrecinctPortion)
        headerlen: Number of header columns before vote data starts (default 8)

    Returns:
        Dictionary with statistics about the anonymization process
    """
    stats = {
        "total_rows": 0,
        "rare_styles": 0,
        "aggregated_rows": 0,
        "original_styles": 0,
        "final_styles": 0,
        "rare_ballots_initial": 0,
        "ballots_borrowed_for_minimum": 0,
        "contests_needing_ballots": {},
        "ballots_added_for_contests": 0,
        "contests_needing_balancing": [],
        "ballots_added_for_balancing": 0,
        "final_aggregate_totals": {},
        "totals_after_rare_styles": {},
        "rare_style_counts": [],
        "contest_ballot_counts": {},
        "min_ballots": min_ballots,
        "style_counts": {},
    }

    # Use context manager to handle Parquet conversion if needed
    if is_parquet_file(input_file):
        print("Converting Parquet file to CSV format...", file=sys.stderr)

    ballot_type_idx: Optional[int] = None

    with TempCVRFile(input_file) as csv_file:
        # Detect line terminator from input file
        with open(csv_file, "rb") as f:
            first_chunk = f.read(1024)
            if b"\r\n" in first_chunk:
                lineterminator = "\r\n"
            elif b"\n" in first_chunk:
                lineterminator = "\n"
            elif b"\r" in first_chunk:
                lineterminator = "\r"
            else:
                lineterminator = "\n"  # Default

        # Read input file
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            version = next(reader)
            contests = next(reader)
            choices = next(reader)
            headers = next(reader)
            for idx, header_name in enumerate(headers):
                if header_name.strip().lower() == "ballottype":
                    ballot_type_idx = idx
                    break

            # Read all data rows
            all_rows = list(reader)
            stats["total_rows"] = len(all_rows)

    # Count ballots per original CVR style
    style_counts: Dict[str, int] = defaultdict(int)
    for row in all_rows:
        if len(row) > stylecol:
            style_value = row[stylecol].strip()
            if style_value:
                style_counts[style_value] += 1
    stats["style_counts"] = dict(style_counts)

    # Analyze styles for leakage detection
    style_analysis = analyze_styles(
        all_rows,
        contests,
        choices,
        headerlen,
        stylecol,
        min_ballots,
        summarize,
        ballot_type_idx=ballot_type_idx,
    )

    # Report leakage warnings
    if style_analysis["leakage_warnings"]:
        print("Warning: Potential information leakage detected:", file=sys.stderr)
        for warning in style_analysis["leakage_warnings"]:
            print(f"  {warning}", file=sys.stderr)

    # Print style mapping
    if style_analysis["cvr_to_descriptive"]:
        print("\nStyle mapping (CVR style -> Descriptive style):")
        for cvr_style in sorted(style_analysis["cvr_to_descriptive"].keys()):
            descriptive = style_analysis["cvr_to_descriptive"][cvr_style]
            count = style_counts.get(cvr_style, 0)
            ballot_label = "ballots" if count != 1 else "ballot"
            print(f"  {cvr_style} ({count} {ballot_label}) -> {descriptive}")

    # Print summary if requested
    if summarize and "summary" in style_analysis:
        summary = style_analysis["summary"]
        print("\n=== CVR Summary ===")

        print("\nTotals by contest:")
        for contest_name, choice_totals in summary["contest_totals"].items():
            print(f"  {contest_name}:")
            for choice_name, count in sorted(choice_totals.items()):
                print(f"    {choice_name}: {count}")

        print("\nStyle statistics:")
        for style_name, style_info in sorted(summary["style_stats"].items()):
            print(
                f"  {style_name} ({style_info['ballot_count']} ballots, pattern: {style_info['contest_pattern']}):"
            )
            for contest_name, probs in style_info["probabilities"].items():
                print(f"    {contest_name}:")
                for choice_name, prob in sorted(probs.items()):
                    print(f"      {choice_name}: {prob:.4f}")

    # Group rows by style signature
    style_groups: Dict[str, List[List[str]]] = defaultdict(list)
    for row in all_rows:
        if len(row) > headerlen:
            style_sig = pull_style_signature(row, headerlen, stylecol)
            style_groups[style_sig].append(row)

    stats["original_styles"] = len(style_groups)

    # Identify rare and common styles
    rare_styles: Dict[str, List[List[str]]] = {}
    common_styles: Dict[str, List[List[str]]] = {}
    pattern_to_descriptive = style_analysis.get("pattern_to_descriptive", {})

    for style_sig, rows in style_groups.items():
        if not rows:
            continue
        contest_pattern = compute_contest_pattern(rows[0], contests, headerlen)
        descriptive_name = pattern_to_descriptive.get(
            contest_pattern,
            compute_descriptive_style_name(
                contest_pattern, len(rows), len(stats["rare_style_counts"]) + 1, min_ballots
            ),
        )

        if len(rows) < min_ballots:
            rare_styles[style_sig] = rows
            stats["rare_styles"] += len(rows)
            style_name_counts: Dict[str, int] = defaultdict(int)
            for row in rows:
                if len(row) > stylecol:
                    style_value = row[stylecol].strip()
                    if style_value:
                        style_name_counts[style_value] += 1
            stats["rare_style_counts"].append(
                {
                    "descriptive_name": descriptive_name,
                    "ballot_count": len(rows),
                    "original_styles": sorted(style_name_counts.items()),
                }
            )
        else:
            common_styles[style_sig] = rows

    # NEW APPROACH: Combine all rare styles into one aggregation
    # Focus on balance (avoid unanimous patterns) and minimums per contest

    # Count total rare ballots
    total_rare_ballots = sum(len(rows) for rows in rare_styles.values())

    # No rare ballots - nothing to aggregate
    if total_rare_ballots == 0:
        row_groups = []
    else:
        # Step 1: Collect ALL rare ballots into one list
        all_rare_ballots = []
        for rows in rare_styles.values():
            all_rare_ballots.extend(rows)

        stats["rare_ballots_initial"] = len(all_rare_ballots)

        # Calculate totals after including all rare styles
        if headerlen < len(contests):
            temp_agg_after_rare = aggregate_votes(
                all_rare_ballots,
                headerlen,
                aggregate_id="TEMP",
                ballot_type_idx=ballot_type_idx,
            )
            stats["totals_after_rare_styles"] = tally_aggregated_votes_by_contest(
                temp_agg_after_rare, contests, choices, headerlen
            )

        # Step 2: If we don't have enough ballots, borrow from common styles to reach min_ballots
        if len(all_rare_ballots) < min_ballots:
            needed = min_ballots - len(all_rare_ballots)
            # Borrow ballots from the largest common style
            if common_styles:
                # Sort by size (largest first)
                sorted_common = sorted(
                    common_styles.items(), key=lambda x: len(x[1]), reverse=True
                )
                style_sig, common_rows = sorted_common[0]
                
                # Calculate how many we can borrow
                remaining_after_borrow = len(common_rows) - needed
                if remaining_after_borrow < min_ballots and remaining_after_borrow > 0:
                    # Take all ballots to avoid leaving a rare-looking style
                    borrowed = common_rows[:]
                    common_styles[style_sig] = []
                    if len(common_styles[style_sig]) == 0:
                        del common_styles[style_sig]
                else:
                    # Borrow only what we need
                    borrowed = common_rows[:needed]
                    common_styles[style_sig] = common_rows[needed:]
                    if len(common_styles[style_sig]) < min_ballots:
                        del common_styles[style_sig]
                
                all_rare_ballots.extend(borrowed)
                stats["ballots_borrowed_for_minimum"] = len(borrowed)
            else:
                # No common styles to borrow from
                raise ValueError(
                    f"Cannot anonymize: {total_rare_ballots} rare ballot(s) found, "
                    f"but cannot create aggregate with at least {min_ballots} ballots. "
                    f"No common styles available to borrow from."
                )

        # Step 3: Ensure at least min_ballots per contest in the aggregation
        if headerlen < len(contests):
            # Map contest names to column indices
            contest_to_columns = defaultdict(set)
            for col_idx in range(headerlen, len(contests)):
                contest_name = contests[col_idx].strip()
                if contest_name:
                    contest_to_columns[contest_name].add(col_idx)

            # Map contest names to choice names per column
            contest_choice_meta: Dict[str, Dict[int, str]] = {}
            for contest_name, col_indices in contest_to_columns.items():
                choice_map: Dict[int, str] = {}
                for col_idx in col_indices:
                    choice_name = ""
                    if col_idx < len(choices):
                        choice_name = choices[col_idx].strip()
                    if not choice_name:
                        choice_name = f"Choice{col_idx}"
                    choice_map[col_idx] = choice_name
                contest_choice_meta[contest_name] = choice_map

            contest_choice_counts: Dict[str, Dict[str, int]] = {
                contest_name: {} for contest_name in contest_choice_meta.keys()
            }
            for row in all_rare_ballots:
                update_choice_counts_from_row(row, contest_choice_counts, contest_choice_meta)

            contest_names_list = list(contest_to_columns.keys())
            contest_ballot_counts = defaultdict(int)
            contest_ballot_vote_counts = defaultdict(int)
            aggregation_cvr_numbers = set()
            for row in all_rare_ballots:
                if len(row) > 0:
                    cvr_num = row[0].strip()
                    if cvr_num:
                        aggregation_cvr_numbers.add(cvr_num)
                update_contest_presence_counts(
                    row,
                    contest_names_list,
                    contest_to_columns,
                    contest_ballot_counts,
                    contest_ballot_vote_counts,
                )

            # Find contests that need more ballots
            contests_needing_ballots = {}
            for contest_name, count in contest_ballot_counts.items():
                if count < min_ballots:
                    needed = min_ballots - count
                    contests_needing_ballots[contest_name] = needed

            stats["contest_ballot_counts_after_rare"] = dict(contest_ballot_counts)
            stats["contest_ballot_vote_counts_after_rare"] = dict(contest_ballot_vote_counts)

            stats["contest_ballot_counts"] = dict(contest_ballot_counts)

            stats["contests_needing_ballots"] = dict(contests_needing_ballots)

            # Add ballots for contests that need them, prioritizing multi-contest coverage and balance
            additional_ballots: List[List[str]] = []

            while contests_needing_ballots:
                candidate = select_balancing_ballot(
                    common_styles,
                    contests_needing_ballots,
                    contest_to_columns,
                    contest_choice_counts,
                    contest_choice_meta,
                    aggregation_cvr_numbers,
                    min_ballots,
                )
                if candidate is None:
                    break

                style_sig, row_idx, row, contests_for_row, _ = candidate
                additional_ballots.append(row)
                all_rare_ballots.append(row)
                if len(row) > 0:
                    cvr_num = row[0].strip()
                    if cvr_num:
                        aggregation_cvr_numbers.add(cvr_num)

                if headerlen < len(contests):
                    update_contest_presence_counts(
                        row,
                        contest_names_list,
                        contest_to_columns,
                        contest_ballot_counts,
                        contest_ballot_vote_counts,
                    )

                update_choice_counts_from_row(row, contest_choice_counts, contest_choice_meta)

                # Update remaining needs for contests we were targeting
                for contest_name in contests_for_row:
                    if contest_name in contests_needing_ballots:
                        contests_needing_ballots[contest_name] -= 1
                        if contests_needing_ballots[contest_name] <= 0:
                            del contests_needing_ballots[contest_name]

                # Remove the borrowed ballot from the common styles pool
                if style_sig in common_styles:
                    rows_list = common_styles[style_sig]
                    if 0 <= row_idx < len(rows_list):
                        rows_list.pop(row_idx)
                    if len(rows_list) < min_ballots:
                        del common_styles[style_sig]

            # Fallback: if contests still need ballots, use per-contest search
            if contests_needing_ballots:
                for contest_name, needed in list(contests_needing_ballots.items()):
                    if needed <= 0:
                        continue
                    found = find_ballots_with_contest(
                        contest_name,
                        common_styles,
                        contests,
                        headerlen,
                        min_ballots,
                        needed_count=needed,
                        exclude_cvr_numbers=aggregation_cvr_numbers,
                    )
                    if not found:
                        continue
                    for row in found:
                        additional_ballots.append(row)
                        all_rare_ballots.append(row)
                        update_choice_counts_from_row(row, contest_choice_counts, contest_choice_meta)
                        update_contest_presence_counts(
                            row,
                            contest_names_list,
                            contest_to_columns,
                            contest_ballot_counts,
                            contest_ballot_vote_counts,
                        )
                        if len(row) > 0:
                            cvr_num = row[0].strip()
                            if cvr_num:
                                aggregation_cvr_numbers.add(cvr_num)
                    contests_needing_ballots[contest_name] -= len(found)
                    if contests_needing_ballots[contest_name] <= 0:
                        del contests_needing_ballots[contest_name]

            stats["ballots_added_for_contests"] = len(additional_ballots)

            # Update common_styles to remove borrowed ballots
            if additional_ballots:
                additional_cvr_numbers = set()
                for row in additional_ballots:
                    if len(row) > 0:
                        cvr_num = row[0].strip()
                        if cvr_num:
                            additional_cvr_numbers.add(cvr_num)

                # Remove borrowed ballots from common_styles
                for style_sig in list(common_styles.keys()):
                    remaining_rows = [
                        row
                        for row in common_styles[style_sig]
                        if len(row) == 0 or row[0].strip() not in additional_cvr_numbers
                    ]
                    if len(remaining_rows) < min_ballots:
                        del common_styles[style_sig]
                    else:
                        common_styles[style_sig] = remaining_rows

        # Step 4: Aggregate all rare ballots into one row
        # Create a single row group
        row_groups = [all_rare_ballots]

        # Step 5: Check for unanimous/near-unanimous patterns and add contrasting votes
        # First, create a temporary aggregated row to analyze
        temp_aggregated = aggregate_votes(
            all_rare_ballots,
            headerlen,
            aggregate_id="TEMP",
            ballot_type_idx=ballot_type_idx,
        )
        contest_totals = tally_aggregated_votes_by_contest(
            temp_aggregated, contests, choices, headerlen
        )
        total_ballots_in_agg = len(all_rare_ballots)
        problematic_contests = check_unanimous_patterns(contest_totals, total_ballots_in_agg)

        # Track which contests needed balancing
        if problematic_contests:
            stats["contests_needing_balancing"] = [
                (contest_name, winning_choice) for contest_name, winning_choice, _, _ in problematic_contests
            ]

        # If we have problematic contests, add contrasting votes
        if problematic_contests:
            contrasting_ballots = find_contrasting_ballots_multi(
                problematic_contests,
                common_styles,
                contests,
                choices,
                headerlen,
                min_ballots,
            )
            if contrasting_ballots:
                all_rare_ballots.extend(contrasting_ballots)
                stats["ballots_added_for_balancing"] = len(contrasting_ballots)
                if headerlen < len(contests):
                    contest_names_list = list(contest_to_columns.keys())
                # Update common_styles to remove borrowed ballots
                contrasting_cvr_numbers = set()
                for row in contrasting_ballots:
                    if len(row) > 0:
                        cvr_num = row[0].strip()
                        if cvr_num:
                            contrasting_cvr_numbers.add(cvr_num)
                        if headerlen < len(contests):
                            update_choice_counts_from_row(
                                row, contest_choice_counts, contest_choice_meta
                            )
                            update_contest_presence_counts(
                                row,
                                contest_names_list,
                                contest_to_columns,
                                contest_ballot_counts,
                                contest_ballot_vote_counts,
                            )

                for style_sig in list(common_styles.keys()):
                    remaining_rows = [
                        row
                        for row in common_styles[style_sig]
                        if len(row) == 0 or row[0].strip() not in contrasting_cvr_numbers
                    ]
                    if len(remaining_rows) < min_ballots:
                        del common_styles[style_sig]
                    else:
                        common_styles[style_sig] = remaining_rows

                # Update row_groups with the new ballots
                row_groups[0] = all_rare_ballots

        if headerlen < len(contests):
            stats["final_contest_ballot_counts"] = dict(contest_ballot_counts)
            stats["final_contest_vote_counts"] = dict(contest_ballot_vote_counts)

    # Create aggregated rows from the row groups
    aggregated_groups = []
    for i, group in enumerate(row_groups):
        agg_id = f"AGGREGATED-{i + 1}"
        aggregated_row = aggregate_votes(
            group,
            headerlen,
            aggregate_id=agg_id,
            ballot_type_idx=ballot_type_idx,
        )
        # Note: CountingGroup and PrecinctPortion are already blanked in aggregate_votes
        # BallotType is set to "AGGREGATED" for aggregated rows
        aggregated_groups.append(aggregated_row)

        # Calculate final totals for this aggregate
        if headerlen < len(contests):
            stats["final_aggregate_totals"] = tally_aggregated_votes_by_contest(
                aggregated_row, contests, choices, headerlen
            )

    stats["aggregated_rows"] = len(aggregated_groups)
    stats["final_styles"] = len(common_styles) + len(aggregated_groups)

    # Build set of all CvrNumbers that are in aggregates (should be excluded from output)
    # Use CvrNumber (column 0) as the unique identifier for matching rows
    aggregated_cvr_numbers = set()
    if row_groups:
        # Create a set of all CvrNumbers that will be in aggregates
        for group in row_groups:
            for row in group:
                if len(row) > 0:
                    cvr_num = row[0].strip()
                    if cvr_num and not cvr_num.startswith("AGGREGATED-"):
                        aggregated_cvr_numbers.add(cvr_num)

    # Collect all output rows
    output_rows = []

    # Add rows that are NOT in any aggregation
    # Blank CountingGroup and PrecinctPortion to avoid revealing additional information
    # Preserve BallotType (it should only reflect contest pattern, not additional identifying info)
    for row in all_rows:
        if len(row) > 0:
            cvr_num = row[0].strip()
            # Skip if this row is in an aggregation
            if cvr_num not in aggregated_cvr_numbers:
                # Create a copy to avoid modifying the original
                output_row = row.copy()
                # Blank CountingGroup (index 5) and PrecinctPortion (index 6)
                # Preserve BallotType (index 7) - it should only reflect contest pattern
                if len(output_row) > 5:
                    output_row[5] = ""  # CountingGroup
                if len(output_row) > 6:
                    output_row[6] = ""  # PrecinctPortion
                # BallotType (index 7) is preserved as-is
                output_rows.append(output_row)

    # Add aggregated rows
    output_rows.extend(aggregated_groups)

    # Sort rows numerically by CvrNumber (column 0)
    # Handle both numeric CvrNumbers and "AGGREGATED-N" strings
    def sort_key(row):
        if not row:
            return (1, "")  # Empty rows go to end
        cvr_num = row[0].strip()
        # Check if it's an aggregated row
        if cvr_num.startswith("AGGREGATED-"):
            # Extract number from "AGGREGATED-N" and put at very end
            try:
                num = int(cvr_num.split("-")[1])
                return (2, num)  # 2 means aggregated, sort by number
            except (ValueError, IndexError):
                return (3, cvr_num)  # Invalid format goes last
        # Try to parse as integer
        try:
            return (0, int(cvr_num))  # 0 means numeric, sort numerically
        except ValueError:
            # Non-numeric, sort as string after numeric values
            return (1, cvr_num)

    output_rows.sort(key=sort_key)

    # Write output file with sorted rows, preserving original line terminator
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator=lineterminator)
        writer.writerow(version)
        writer.writerow(contests)
        writer.writerow(choices)
        writer.writerow(headers)

        # Write sorted rows
        for row in output_rows:
            writer.writerow(row)

    # Verify that tallies match (required check before delivering redacted CVR)
    match, details = verify_tally_match(input_file, output_file, headerlen)
    if not match:
        print(
            "ERROR: Vote tallies do not match between original and anonymized CVR!",
            file=sys.stderr,
        )
        print("Mismatches:", file=sys.stderr)
        for mismatch in details["mismatches"]:
            print(
                f"  Contest '{mismatch['contest']}', Choice '{mismatch['choice']}': "
                f"Original={mismatch['original']}, Anonymized={mismatch['anonymized']}, "
                f"Difference={mismatch['difference']}",
                file=sys.stderr,
            )
        raise ValueError(
            "Anonymization failed: vote tallies do not match. "
            "This indicates a bug in the aggregation logic. "
            "The redacted CVR cannot be delivered."
        )
    # Verification passed - tallies match

    return stats


def main():
    """Command-line interface for CVR anonymization."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Anonymize CVR files by aggregating rare styles (supports CSV and Parquet formats)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python anonymize_cvr.py input.csv output.csv
  python anonymize_cvr.py input.parquet output.csv
  python anonymize_cvr.py input.csv output.csv --min-ballots 15
        """,
    )
    parser.add_argument("input_file", help="Input CVR file path (CSV or Parquet format)")
    parser.add_argument("output_file", help="Output anonymized CVR file path")
    parser.add_argument(
        "--min-ballots",
        type=int,
        default=10,
        help="Minimum ballots required per style (default: 10)",
    )
    parser.add_argument(
        "--stylecol", type=int, default=6, help="Index of style column (default: 6)"
    )
    parser.add_argument(
        "--headerlen", type=int, default=8, help="Number of header columns (default: 8)"
    )
    parser.add_argument(
        "--summarize", "-s", action="store_true", help="Print detailed summary of CVR statistics"
    )

    args = parser.parse_args()

    try:
        stats = anonymize_cvr(
            args.input_file,
            args.output_file,
            args.min_ballots,
            args.stylecol,
            args.headerlen,
            args.summarize,
        )

        print("Anonymization complete!")
        print(f"  Total rows processed: {stats['total_rows']}")
        print(f"  Original styles: {stats['original_styles']}")
        if stats.get("rare_style_counts"):
            print(f"  Rare styles ({len(stats['rare_style_counts'])}):")
            for entry in sorted(stats["rare_style_counts"], key=lambda x: x["descriptive_name"]):
                orig_styles = entry.get("original_styles") or []
                if orig_styles:
                    orig_desc = ", ".join(f"{name} ({count})" for name, count in orig_styles)
                else:
                    orig_desc = "unknown CVR style(s)"
                print(
                    f"    {entry['descriptive_name']}: {entry['ballot_count']} ballot(s) from {orig_desc}"
                )
        print(f"  Aggregated rows created: {stats['aggregated_rows']}")
        print(f"  Final styles: {stats['final_styles']}")
        print(f"  Output written to: {args.output_file}")

        # Print aggregation statistics
        if stats.get("rare_ballots_initial", 0) > 0:
            print("\n=== Aggregation Statistics ===")
            print(f"  Initial rare ballots: {stats['rare_ballots_initial']}")
            
            if stats.get("ballots_borrowed_for_minimum", 0) > 0:
                print(f"  Ballots borrowed to reach minimum: {stats['ballots_borrowed_for_minimum']}")
            
            if stats.get("contests_needing_ballots"):
                print(
                    f"  Contests needing additional ballots ({len(stats['contests_needing_ballots'])}):"
                )
                contest_counts = stats.get("contest_ballot_counts", {})
                min_required = stats.get("min_ballots", 10)
                for contest, needed in sorted(stats["contests_needing_ballots"].items()):
                    current = contest_counts.get(contest, 0)
                    print(
                        f"    {contest[:60]}: had {current}, needed {needed} more to reach {min_required}"
                    )
                print(f"  Total ballots added for contests: {stats.get('ballots_added_for_contests', 0)}")
            
            if stats.get("contests_needing_balancing"):
                print(f"  Contests needing balancing ({len(stats['contests_needing_balancing'])}):")
                for contest, choice in stats["contests_needing_balancing"]:
                    print(f"    {contest[:60]}: {choice[:40]}")
                print(f"  Total ballots added for balancing: {stats.get('ballots_added_for_balancing', 0)}")
            
            total_extra = (
                stats.get("ballots_borrowed_for_minimum", 0)
                + stats.get("ballots_added_for_contests", 0)
                + stats.get("ballots_added_for_balancing", 0)
            )
            if total_extra > 0:
                print(f"  Total extra CVRs added to aggregate: {total_extra}")
            
            if stats.get("totals_after_rare_styles"):
                print("\n  Totals after including all rare styles:")
                eligible_counts_after_rare = stats.get("contest_ballot_counts_after_rare", {})
                ballots_with_votes_after_rare = stats.get(
                    "contest_ballot_vote_counts_after_rare", {}
                )
                for contest_name, choice_totals in sorted(stats["totals_after_rare_styles"].items()):
                    votes_cast = ballots_with_votes_after_rare.get(contest_name, 0)
                    eligible = eligible_counts_after_rare.get(contest_name, votes_cast)
                    undervotes = max(eligible - votes_cast, 0)
                    print(
                        f"    {contest_name[:60]}: {eligible} ballot(s) with contest, "
                        f"{votes_cast} ballot(s) with votes, {undervotes} undervote(s)"
                    )
                    for choice, count in sorted(choice_totals.items()):
                        if count > 0:
                            print(f"      {choice[:40]}: {count}")
            
            if stats.get("final_aggregate_totals"):
                print("\n  Final aggregate totals:")
                final_contest_counts = stats.get("final_contest_ballot_counts", {})
                final_contest_vote_counts = stats.get("final_contest_vote_counts", {})
                for contest_name, choice_totals in sorted(stats["final_aggregate_totals"].items()):
                    votes_cast = final_contest_vote_counts.get(contest_name, 0)
                    eligible = final_contest_counts.get(contest_name, votes_cast)
                    undervotes = max(eligible - votes_cast, 0)
                    print(
                        f"    {contest_name[:60]}: {eligible} ballot(s) with contest, "
                        f"{votes_cast} ballot(s) with votes, {undervotes} undervote(s)"
                    )
                    for choice, count in sorted(choice_totals.items()):
                        if count > 0:
                            print(f"      {choice[:40]}: {count}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
