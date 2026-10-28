#!/usr/bin/env python3
"""
Batch matching implementation for comparing batches of ballots.

This module provides functionality to:
- Extract batches from Dominion CVR files
- Compute batch signatures with ballot fingerprints
- Compare batches to determine if they contain the same physical ballots
"""

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from cvr_utils import TempCVRFile, is_parquet_file

from .fingerprint_utils import (
    build_ballot_bitstring,
    compute_strict_hash,
    find_vote_column_start,
    hamming_distance,
    normalized_hamming_distance,
)
from .simhash import get_simhash_bucket, simhash, simhash_distance, simhash_similarity


@dataclass
class BallotFingerprint:
    """Fingerprint for a single ballot."""

    cvr_number: str  # CvrNumber from CVR
    imprinted_id: str  # ImprintedId from CVR
    style_id: str  # PrecinctPortion or BallotType
    h0: str  # Strict hash (hex)
    simhash: int  # Fuzzy hash
    bitstring: bytes  # Original bitstring for Hamming distance
    sequence_index: Optional[int] = None  # Position within batch (from RecordId or ImprintedId)


@dataclass
class BatchSignature:
    """Signature for a batch of ballots."""

    tabulator_id: str
    batch_id: str
    cardinality: int
    style_histogram: Dict[str, int] = field(default_factory=dict)
    strict_hash_multiset: Counter[str] = field(default_factory=Counter)
    cluster_histogram: Dict[int, int] = field(default_factory=dict)  # SimHash bucket -> count
    contest_schema: Set[str] = field(default_factory=set)  # Contest names
    ballots: List[BallotFingerprint] = field(default_factory=list)


@dataclass
class BatchComparisonResult:
    """Result of comparing two batches."""

    batch_a: Tuple[str, str]  # (tabulator, batch)
    batch_b: Tuple[str, str]
    is_same_batch: bool
    confidence: float  # 0.0 to 1.0
    match_type: str  # "strict", "fuzzy", "none"
    elimination_reason: Optional[str] = None
    cardinality_match: bool = False
    style_histogram_match: bool = False
    contest_schema_match: bool = False
    strict_hash_match: bool = False
    fuzzy_match_rate: Optional[float] = None
    adjusted_match_rate: Optional[float] = None  # Match rate after penalty for unmatched ballots
    unmatched_count: Optional[int] = None  # Number of unmatched ballots
    penalty: Optional[float] = None  # Penalty applied for unmatched ballots beyond tolerance
    mean_hamming_distance: Optional[float] = None
    sketch_distance: Optional[float] = None
    lcs_length: Optional[int] = None
    lcs_ratio: Optional[float] = None  # lcs_length / min(|A|, |B|)


def extract_batch_ballots_parquet(
    parquet_file: str, precinct_id: str
) -> Tuple[List[List[str]], List[str], List[str], int]:
    """
    Extract all ballots for a specific precinct (treated as batch) from a parquet file.

    Args:
        parquet_file: Path to parquet file
        precinct_id: Precinct identifier (precinct_medsl value)

    Returns:
        Tuple of (ballot_rows, contests, choices, vote_start)
        - ballot_rows: List of ballot row data in CSV format
        - contests: List of contest names
        - choices: List of candidate/choice names
        - vote_start: Column index where vote columns start (7 for standard format)
    """
    if not PANDAS_AVAILABLE:
        raise ImportError("pandas is required to read parquet files")

    # Read parquet file
    df = pd.read_parquet(parquet_file)

    # Verify required columns
    if "precinct_medsl" not in df.columns:
        raise ValueError(f"Parquet file missing 'precinct_medsl' column. Found: {list(df.columns)}")

    # Filter to ballots in this precinct (convert to string for comparison)
    precinct_df = df[df["precinct_medsl"].astype(str) == str(precinct_id)].copy()

    if len(precinct_df) == 0:
        return [], [], [], 7

    # Get unique voters (cvr_id) and contests (office)
    voters = sorted(precinct_df["cvr_id"].unique())
    contests_list = sorted(precinct_df["office"].unique())

    # Build contest -> candidates mapping
    contest_candidates: Dict[str, List[str]] = {}
    for contest in contests_list:
        candidates = sorted(
            precinct_df[precinct_df["office"] == contest]["candidate"].unique()
        )
        contest_candidates[contest] = candidates

    # Build header rows
    contests_row = [""] * 7  # Header columns: CvrNumber, TabulatorNum, BatchId, RecordId, ImprintedId, PrecinctPortion, BallotType
    choices_row = [""] * 7
    for contest in contests_list:
        contests_row.extend([contest] * len(contest_candidates[contest]))
        choices_row.extend(contest_candidates[contest])

    # Build ballot rows
    ballot_rows: List[List[str]] = []
    for idx, cvr_id in enumerate(voters, 1):
        voter_votes = precinct_df[precinct_df["cvr_id"] == cvr_id]

        # Get precinct portion (use precinct_medsl as style)
        precinct_portion = str(voter_votes["precinct_medsl"].iloc[0])

        # Build row: [CvrNumber, TabulatorNum, BatchId, RecordId, ImprintedId, PrecinctPortion, BallotType, ...votes...]
        row = [
            str(cvr_id),  # CvrNumber
            "PARQUET",  # TabulatorNum (dummy value for parquet files)
            str(precinct_id),  # BatchId (using precinct as batch)
            str(cvr_id),  # RecordId
            str(cvr_id),  # ImprintedId
            precinct_portion,  # PrecinctPortion
            "",  # BallotType
        ]

        # Add vote columns
        for contest in contests_list:
            contest_votes = voter_votes[voter_votes["office"] == contest]
            for candidate in contest_candidates[contest]:
                # Check if this voter voted for this candidate
                if len(contest_votes) > 0 and candidate in contest_votes["candidate"].values:
                    row.append("1")
                elif len(contest_votes) > 0:
                    # Contest was on ballot but voter didn't vote for this candidate
                    row.append("0")
                else:
                    # Contest not on voter's ballot
                    row.append("")

        ballot_rows.append(row)

    vote_start = 7  # Standard header length
    return ballot_rows, contests_row, choices_row, vote_start


def extract_batch_ballots(
    cvr_file: str, tabulator_id: str, batch_id: str
) -> Tuple[List[List[str]], List[str], List[str], int]:
    """
    Extract all ballots for a specific batch from a CVR file.

    Supports both CSV format (using TabulatorNum and BatchId) and parquet format
    (using precinct_medsl as batch_id).

    Args:
        cvr_file: Path to CVR file (CSV or parquet format)
        tabulator_id: Tabulator identifier (for CSV) or "PARQUET" (for parquet)
        batch_id: Batch identifier (for CSV) or precinct_medsl (for parquet)

    Returns:
        Tuple of (ballot_rows, contests, choices, vote_start)
        - ballot_rows: List of ballot row data
        - contests: List of contest names from header
        - choices: List of candidate/choice names from header
        - vote_start: Column index where vote columns start
    """
    # Handle parquet files
    if is_parquet_file(cvr_file):
        if tabulator_id == "PARQUET" or tabulator_id == "":
            return extract_batch_ballots_parquet(cvr_file, batch_id)
        else:
            raise ValueError(
                f"For parquet files, tabulator_id should be 'PARQUET' or empty, got '{tabulator_id}'"
            )

    # Handle CSV files
    ballot_rows: List[List[str]] = []

    with TempCVRFile(cvr_file) as csv_path:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            version = next(reader)
            contests = next(reader)
            choices = next(reader)
            headers = next(reader)

            # Find column indices
            tabulator_idx = None
            batch_idx = None
            cvr_number_idx = None

            for i, header in enumerate(headers):
                header_lower = header.strip().lower()
                if header_lower == "tabulatornum":
                    tabulator_idx = i
                elif header_lower == "batchid":
                    batch_idx = i
                elif header_lower == "cvrnumber":
                    cvr_number_idx = i

            if tabulator_idx is None or batch_idx is None:
                raise ValueError(
                    f"CVR file missing required columns: TabulatorNum={tabulator_idx is None}, "
                    f"BatchId={batch_idx is None}"
                )

            # Find where vote columns start
            vote_start = find_vote_column_start(contests)

            # Extract ballots for this batch
            for row in reader:
                if len(row) <= max(tabulator_idx, batch_idx, cvr_number_idx or 0):
                    continue

                # Skip aggregated rows
                if cvr_number_idx is not None and len(row) > cvr_number_idx:
                    cvr_number = row[cvr_number_idx].strip()
                    if cvr_number.startswith("AGGREGATED-"):
                        continue

                # Check if this ballot belongs to the batch
                row_tabulator = row[tabulator_idx].strip() if tabulator_idx < len(row) else ""
                row_batch = row[batch_idx].strip() if batch_idx < len(row) else ""

                if row_tabulator == tabulator_id and row_batch == batch_id:
                    ballot_rows.append(row)

    return ballot_rows, contests, choices, vote_start


def compute_batch_signature(
    cvr_file: str, tabulator_id: str, batch_id: str
) -> BatchSignature:
    """
    Compute batch signature for a specific batch.

    Args:
        cvr_file: Path to CVR file (CSV format)
        tabulator_id: Tabulator identifier
        batch_id: Batch identifier

    Returns:
        BatchSignature object
    """
    # Extract ballots
    ballot_rows, contests, choices, vote_start = extract_batch_ballots(
        cvr_file, tabulator_id, batch_id
    )

    # Find column indices
    with TempCVRFile(cvr_file) as csv_path:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # version
            next(reader)  # contests
            next(reader)  # choices
            headers = next(reader)

            cvr_number_idx = None
            imprinted_id_idx = None
            precinct_portion_idx = None
            ballot_type_idx = None
            record_id_idx = None

            for i, header in enumerate(headers):
                header_lower = header.strip().lower()
                if header_lower == "cvrnumber":
                    cvr_number_idx = i
                elif header_lower == "imprintedid":
                    imprinted_id_idx = i
                elif header_lower == "precinctportion":
                    precinct_portion_idx = i
                elif header_lower == "ballottype":
                    ballot_type_idx = i
                elif header_lower == "recordid":
                    record_id_idx = i

    # Build contest to columns mapping
    from .fingerprint_utils import build_contest_to_columns

    contest_to_columns = build_contest_to_columns(contests, choices, vote_start)
    contest_schema = set(contest_to_columns.keys())

    # Process each ballot
    ballots: List[BallotFingerprint] = []
    style_histogram: Dict[str, int] = defaultdict(int)
    strict_hash_multiset: Counter[str] = Counter()
    cluster_histogram: Dict[int, int] = defaultdict(int)

    for idx, row in enumerate(ballot_rows):
        # Extract header fields
        cvr_number = row[cvr_number_idx].strip() if cvr_number_idx is not None and cvr_number_idx < len(row) else ""
        imprinted_id = (
            row[imprinted_id_idx].strip()
            if imprinted_id_idx is not None and imprinted_id_idx < len(row)
            else ""
        )
        precinct_portion = (
            row[precinct_portion_idx].strip()
            if precinct_portion_idx is not None and precinct_portion_idx < len(row)
            else ""
        )
        ballot_type = (
            row[ballot_type_idx].strip()
            if ballot_type_idx is not None and ballot_type_idx < len(row)
            else ""
        )
        record_id = (
            row[record_id_idx].strip()
            if record_id_idx is not None and record_id_idx < len(row)
            else ""
        )

        # Use PrecinctPortion as style_id, fallback to BallotType
        style_id = precinct_portion if precinct_portion else ballot_type

        # Build bitstring
        bitstring = build_ballot_bitstring(row, contests, choices, vote_start)

        # Compute fingerprints
        h0 = compute_strict_hash(bitstring)
        simhash_value = simhash(bitstring)

        # Extract sequence index from RecordId or ImprintedId
        sequence_index = None
        if record_id:
            try:
                sequence_index = int(record_id)
            except ValueError:
                pass
        elif imprinted_id:
            # Try to extract position from imprinted_id (format: tabulator-batch-position)
            parts = imprinted_id.split("-")
            if len(parts) >= 3:
                try:
                    sequence_index = int(parts[-1])
                except ValueError:
                    pass

        # Create fingerprint
        fingerprint = BallotFingerprint(
            cvr_number=cvr_number,
            imprinted_id=imprinted_id,
            style_id=style_id,
            h0=h0,
            simhash=simhash_value,
            bitstring=bitstring,
            sequence_index=sequence_index,
        )
        ballots.append(fingerprint)

        # Update statistics
        style_histogram[style_id] += 1
        strict_hash_multiset[h0] += 1
        bucket = get_simhash_bucket(simhash_value, k=8)
        cluster_histogram[bucket] += 1

    return BatchSignature(
        tabulator_id=tabulator_id,
        batch_id=batch_id,
        cardinality=len(ballots),
        style_histogram=dict(style_histogram),
        strict_hash_multiset=strict_hash_multiset,
        cluster_histogram=dict(cluster_histogram),
        contest_schema=contest_schema,
        ballots=ballots,
    )


def find_batches_in_cvr(cvr_file: str) -> List[Tuple[str, str]]:
    """
    Find all unique batch identifiers in a CVR file.

    For CSV files: finds (TabulatorNum, BatchId) pairs
    For parquet files: finds (PARQUET, precinct_medsl) pairs

    Args:
        cvr_file: Path to CVR file (CSV or parquet format)

    Returns:
        List of (tabulator_id, batch_id) tuples
    """
    batches: Set[Tuple[str, str]] = set()

    # Handle parquet files
    if is_parquet_file(cvr_file):
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas is required to read parquet files")

        df = pd.read_parquet(cvr_file)

        if "precinct_medsl" not in df.columns:
            return []

        # Get unique precincts (treat as batches)
        # Convert to string to ensure consistent format
        precincts = sorted(df["precinct_medsl"].astype(str).unique())
        for precinct in precincts:
            batches.add(("PARQUET", precinct))

        return sorted(batches)

    # Handle CSV files
    with TempCVRFile(cvr_file) as csv_path:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # version
            next(reader)  # contests
            next(reader)  # choices
            headers = next(reader)

            # Find column indices
            tabulator_idx = None
            batch_idx = None
            cvr_number_idx = None

            for i, header in enumerate(headers):
                header_lower = header.strip().lower()
                if header_lower == "tabulatornum":
                    tabulator_idx = i
                elif header_lower == "batchid":
                    batch_idx = i
                elif header_lower == "cvrnumber":
                    cvr_number_idx = i

            if tabulator_idx is None or batch_idx is None:
                return []

            # Extract unique batches
            for row in reader:
                if len(row) <= max(tabulator_idx, batch_idx):
                    continue

                # Skip aggregated rows
                if cvr_number_idx is not None and len(row) > cvr_number_idx:
                    cvr_number = row[cvr_number_idx].strip()
                    if cvr_number.startswith("AGGREGATED-"):
                        continue

                tabulator_id = row[tabulator_idx].strip() if tabulator_idx < len(row) else ""
                batch_id = row[batch_idx].strip() if batch_idx < len(row) else ""

                if tabulator_id and batch_id:
                    batches.add((tabulator_id, batch_id))

    return sorted(batches)


def quick_eliminate(sig_a: BatchSignature, sig_b: BatchSignature) -> Optional[str]:
    """
    Perform quick elimination checks to rule out matching batches.

    Allows up to 2 style mismatches (ballots with different styles) before eliminating.

    Args:
        sig_a: First batch signature
        sig_b: Second batch signature

    Returns:
        Elimination reason string if batches can be eliminated, None otherwise
    """
    # Check cardinality
    if sig_a.cardinality != sig_b.cardinality:
        return "different_cardinality"

    # Check style histogram - allow up to 2 style mismatches
    # Count number of ballots with mismatched styles
    # Each ballot that changes style contributes 2 to the total difference
    # (one decrease in old style, one increase in new style)
    # So we divide by 2 to get the actual number of ballots that changed
    style_mismatches = 0
    all_styles = set(sig_a.style_histogram.keys()) | set(sig_b.style_histogram.keys())
    
    for style in all_styles:
        count_a = sig_a.style_histogram.get(style, 0)
        count_b = sig_b.style_histogram.get(style, 0)
        style_mismatches += abs(count_a - count_b)
    
    # Divide by 2 because each ballot change affects two style counts
    ballots_with_different_styles = style_mismatches // 2
    
    # Allow up to 2 style mismatches (2 ballots can have different styles)
    if ballots_with_different_styles > 2:
        return "different_styles"

    # Check contest schema
    if sig_a.contest_schema != sig_b.contest_schema:
        return "different_contests"

    return None


def strict_match(sig_a: BatchSignature, sig_b: BatchSignature) -> bool:
    """
    Check if batches match exactly using strict hash multisets.

    Args:
        sig_a: First batch signature
        sig_b: Second batch signature

    Returns:
        True if multisets match exactly, False otherwise
    """
    return sig_a.strict_hash_multiset == sig_b.strict_hash_multiset


def fuzzy_match(
    sig_a: BatchSignature, sig_b: BatchSignature
) -> Tuple[bool, float, float]:
    """
    Perform fuzzy matching using SimHash and Hamming distance.

    Args:
        sig_a: First batch signature
        sig_b: Second batch signature

    Returns:
        Tuple of (is_match, match_rate, mean_hamming_distance)
    """
    if sig_a.cardinality == 0 or sig_b.cardinality == 0:
        return (False, 0.0, float("inf"))

    # Greedy bipartite matching
    matched_pairs: List[Tuple[BallotFingerprint, BallotFingerprint, float]] = []
    used_b = set()

    # For each ballot in A, find closest match in B
    for ballot_a in sig_a.ballots:
        best_match = None
        best_distance = float("inf")
        best_idx = -1

        for idx, ballot_b in enumerate(sig_b.ballots):
            if idx in used_b:
                continue

            # Compute SimHash distance
            simhash_dist = simhash_distance(ballot_a.simhash, ballot_b.simhash)

            if simhash_dist < best_distance:
                best_distance = simhash_dist
                best_match = ballot_b
                best_idx = idx

        # If we found a reasonable match (SimHash distance <= 8), verify with Hamming distance
        if best_match and best_distance <= 8:
            hamming_dist = normalized_hamming_distance(ballot_a.bitstring, best_match.bitstring)
            if hamming_dist <= 0.3:  # Threshold for considering a match
                matched_pairs.append((ballot_a, best_match, hamming_dist))
                used_b.add(best_idx)

    # Compute metrics
    match_rate = len(matched_pairs) / sig_a.cardinality if sig_a.cardinality > 0 else 0.0
    mean_hamming = (
        sum(dist for _, _, dist in matched_pairs) / len(matched_pairs)
        if matched_pairs
        else float("inf")
    )

    # Heuristic threshold
    is_match = match_rate >= 0.98 and mean_hamming <= 0.3

    return (is_match, match_rate, mean_hamming)


def sketch_consistency(sig_a: BatchSignature, sig_b: BatchSignature) -> float:
    """
    Compute sketch consistency (distance) between batch cluster histograms.

    Uses Jensen-Shannon divergence as a distance metric.

    Args:
        sig_a: First batch signature
        sig_b: Second batch signature

    Returns:
        Distance metric (lower = more similar)
    """
    import math

    # Get all buckets
    all_buckets = set(sig_a.cluster_histogram.keys()) | set(sig_b.cluster_histogram.keys())

    if not all_buckets:
        return 0.0

    # Normalize histograms to probabilities
    total_a = sum(sig_a.cluster_histogram.values())
    total_b = sum(sig_b.cluster_histogram.values())

    if total_a == 0 or total_b == 0:
        return 1.0

    # Compute Jensen-Shannon divergence
    js_divergence = 0.0
    for bucket in all_buckets:
        p_a = sig_a.cluster_histogram.get(bucket, 0) / total_a
        p_b = sig_b.cluster_histogram.get(bucket, 0) / total_b
        m = (p_a + p_b) / 2.0

        if m > 0:
            if p_a > 0:
                js_divergence += p_a * math.log2(p_a / m) if p_a > 0 else 0
            if p_b > 0:
                js_divergence += p_b * math.log2(p_b / m) if p_b > 0 else 0

    # JS divergence is in [0, 1], convert to distance
    return js_divergence / 2.0


def compute_lcs(sig_a: BatchSignature, sig_b: BatchSignature) -> Tuple[int, float]:
    """
    Compute Longest Common Subsequence (LCS) between matched ballot sequences.

    Args:
        sig_a: First batch signature
        sig_b: Second batch signature

    Returns:
        Tuple of (lcs_length, lcs_ratio)
    """
    # Sort ballots by sequence_index if available
    ballots_a = sorted(sig_a.ballots, key=lambda b: b.sequence_index or 0)
    ballots_b = sorted(sig_b.ballots, key=lambda b: b.sequence_index or 0)

    # Create sequences of H0 hashes
    seq_a = [b.h0 for b in ballots_a]
    seq_b = [b.h0 for b in ballots_b]

    # Compute LCS using dynamic programming
    m, n = len(seq_a), len(seq_b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq_a[i - 1] == seq_b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    lcs_length = dp[m][n]
    min_len = min(m, n)
    lcs_ratio = lcs_length / min_len if min_len > 0 else 0.0

    return (lcs_length, lcs_ratio)


def compare_batches(
    cvr_file: str, tabulator_a: str, batch_a: str, tabulator_b: str, batch_b: str
) -> BatchComparisonResult:
    """
    Compare two batches to determine if they contain the same physical ballots.

    Args:
        cvr_file: Path to CVR file (CSV format)
        tabulator_a: Tabulator ID for first batch
        batch_a: Batch ID for first batch
        tabulator_b: Tabulator ID for second batch
        batch_b: Batch ID for second batch

    Returns:
        BatchComparisonResult with comparison details
    """
    # Compute batch signatures
    sig_a = compute_batch_signature(cvr_file, tabulator_a, batch_a)
    sig_b = compute_batch_signature(cvr_file, tabulator_b, batch_b)

    # Quick elimination checks
    elimination_reason = quick_eliminate(sig_a, sig_b)
    if elimination_reason:
        return BatchComparisonResult(
            batch_a=(tabulator_a, batch_a),
            batch_b=(tabulator_b, batch_b),
            is_same_batch=False,
            confidence=0.0,
            match_type="none",
            elimination_reason=elimination_reason,
            cardinality_match=False,
            style_histogram_match=False,
            contest_schema_match=False,
            strict_hash_match=False,
        )

    # All quick checks passed
    cardinality_match = True
    # Check if style histograms match exactly or within tolerance
    style_histogram_match = sig_a.style_histogram == sig_b.style_histogram
    contest_schema_match = True

    # Strict hash match
    strict_hash_match = strict_match(sig_a, sig_b)
    if strict_hash_match:
        return BatchComparisonResult(
            batch_a=(tabulator_a, batch_a),
            batch_b=(tabulator_b, batch_b),
            is_same_batch=True,
            confidence=1.0,
            match_type="strict",
            elimination_reason=None,
            cardinality_match=cardinality_match,
            style_histogram_match=style_histogram_match,
            contest_schema_match=contest_schema_match,
            strict_hash_match=strict_hash_match,
        )

    # Fuzzy matching
    is_fuzzy_match, match_rate, mean_hamming = fuzzy_match(sig_a, sig_b)

    # Calculate penalty for unmatched ballots
    # Penalize EVERY unmatched ballot (no tolerance)
    unmatched_count = sig_a.cardinality - int(match_rate * sig_a.cardinality)
    penalty = unmatched_count / sig_a.cardinality if sig_a.cardinality > 0 else 0.0
    adjusted_match_rate = max(0.0, match_rate - penalty)

    # Sketch consistency
    sketch_dist = sketch_consistency(sig_a, sig_b)

    # LCS analysis
    lcs_length, lcs_ratio = compute_lcs(sig_a, sig_b)

    # Determine final result using adjusted match rate
    # With penalty applied, thresholds are based on adjusted_match_rate
    if is_fuzzy_match and adjusted_match_rate >= 0.98 and sketch_dist < 0.1 and lcs_ratio > 0.9:
        confidence = 0.95
        is_same = True
    elif is_fuzzy_match and adjusted_match_rate >= 0.95 and sketch_dist < 0.2 and lcs_ratio > 0.8:
        confidence = 0.85
        is_same = True
    elif adjusted_match_rate >= 0.8 and mean_hamming < 0.5:
        # Lower threshold to 0.8 to account for penalty
        confidence = 0.7
        is_same = True
    elif adjusted_match_rate >= 0.75 and mean_hamming < 0.5:
        confidence = max(0.0, adjusted_match_rate - (mean_hamming * 0.3))
        is_same = adjusted_match_rate >= 0.75
    else:
        confidence = max(0.0, adjusted_match_rate - (mean_hamming * 0.5))
        is_same = False

    return BatchComparisonResult(
        batch_a=(tabulator_a, batch_a),
        batch_b=(tabulator_b, batch_b),
        is_same_batch=is_same,
        confidence=confidence,
        match_type="fuzzy" if is_same else "none",
        elimination_reason=None,
        cardinality_match=cardinality_match,
        style_histogram_match=style_histogram_match,
        contest_schema_match=contest_schema_match,
        strict_hash_match=strict_hash_match,
        fuzzy_match_rate=match_rate,
        adjusted_match_rate=adjusted_match_rate,
        unmatched_count=unmatched_count,
        penalty=penalty,
        mean_hamming_distance=mean_hamming,
        sketch_distance=sketch_dist,
        lcs_length=lcs_length,
        lcs_ratio=lcs_ratio,
    )

