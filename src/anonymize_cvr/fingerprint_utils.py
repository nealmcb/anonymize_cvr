#!/usr/bin/env python3
"""
Utilities for building ballot bitstrings and computing fingerprints.

This module provides functions to:
- Build deterministic bitstrings from CVR ballot rows
- Compute strict hashes (SHA-256) for exact matching
- Compute Hamming distances between bitstrings
"""

import hashlib
from collections import defaultdict
from typing import List, Dict, Tuple, Optional


def find_vote_column_start(contests: List[str]) -> int:
    """
    Find the column index where vote data starts (first non-empty contest name).

    Args:
        contests: List of contest names from CVR header row 2

    Returns:
        Column index where vote columns start
    """
    for i, contest in enumerate(contests):
        if contest and contest.strip():
            return i
    return len(contests)


def build_contest_to_columns(
    contests: List[str], choices: List[str], vote_start: int
) -> Dict[str, List[Tuple[int, str]]]:
    """
    Build a mapping from contest names to their column indices and candidate names.

    Args:
        contests: List of contest names from CVR header row 2
        choices: List of candidate/choice names from CVR header row 3
        vote_start: Column index where vote columns start

    Returns:
        Dictionary mapping contest names to list of (column_index, candidate_name) tuples
    """
    contest_to_columns: Dict[str, List[Tuple[int, str]]] = defaultdict(list)
    for col_idx in range(vote_start, len(contests)):
        contest_name = contests[col_idx].strip()
        if contest_name:
            choice_name = choices[col_idx].strip() if col_idx < len(choices) else ""
            if not choice_name:
                choice_name = f"Choice{col_idx}"
            contest_to_columns[contest_name].append((col_idx, choice_name))
    return dict(contest_to_columns)


def build_ballot_bitstring(
    ballot_row: List[str],
    contests: List[str],
    choices: List[str],
    vote_start: int,
) -> bytes:
    """
    Build a deterministic bitstring representing all votes on a ballot.

    The bitstring is constructed by:
    1. Sorting contests by name
    2. For each contest, sorting candidates by name
    3. For each candidate, serializing vote value ("1", "0", or "")
    4. Separating contests with null byte delimiter

    Args:
        ballot_row: List of strings representing a CVR ballot row
        contests: List of contest names from CVR header row 2
        choices: List of candidate/choice names from CVR header row 3
        vote_start: Column index where vote columns start

    Returns:
        Deterministic byte sequence representing all votes
    """
    # Build mapping of contest to columns
    contest_to_columns = build_contest_to_columns(contests, choices, vote_start)

    # Sort contests by name for deterministic ordering
    sorted_contests = sorted(contest_to_columns.keys())

    # Build bitstring parts
    bitstring_parts: List[bytes] = []

    for contest_name in sorted_contests:
        # Get columns for this contest, sorted by candidate name
        col_candidate_pairs = contest_to_columns[contest_name]
        sorted_pairs = sorted(col_candidate_pairs, key=lambda x: x[1])  # Sort by candidate name

        # Serialize votes for this contest
        contest_votes: List[str] = []
        for col_idx, candidate_name in sorted_pairs:
            if col_idx < len(ballot_row):
                vote_value = ballot_row[col_idx].strip()
                # Normalize: "1" = voted, "0" = not voted, "" = contest not on ballot
                contest_votes.append(vote_value if vote_value in ("0", "1", "") else "")
            else:
                contest_votes.append("")  # Missing column = contest not on ballot

        # Join votes for this contest and add to bitstring
        contest_bytes = "|".join(contest_votes).encode("utf-8")
        bitstring_parts.append(contest_bytes)

    # Join contests with null byte delimiter
    return b"\x00".join(bitstring_parts)


def compute_strict_hash(bitstring: bytes) -> str:
    """
    Compute a strict hash (SHA-256) of a bitstring for exact matching.

    Args:
        bitstring: Byte sequence representing ballot votes

    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(bitstring).hexdigest()


def hamming_distance(bitstring_a: bytes, bitstring_b: bytes) -> int:
    """
    Compute Hamming distance (number of differing bits) between two bitstrings.

    Args:
        bitstring_a: First bitstring
        bitstring_b: Second bitstring

    Returns:
        Number of differing bits
    """
    # Ensure same length (pad shorter with zeros)
    max_len = max(len(bitstring_a), len(bitstring_b))
    a_padded = bitstring_a + b"\x00" * (max_len - len(bitstring_a))
    b_padded = bitstring_b + b"\x00" * (max_len - len(bitstring_b))

    # Count differing bytes
    diff_bytes = sum(1 for a, b in zip(a_padded, b_padded) if a != b)

    # For more precise bit-level distance, count differing bits
    # This is more expensive but more accurate
    diff_bits = 0
    for a, b in zip(a_padded, b_padded):
        diff_bits += bin(a ^ b).count("1")

    return diff_bits


def normalized_hamming_distance(bitstring_a: bytes, bitstring_b: bytes) -> float:
    """
    Compute normalized Hamming distance (0.0 to 1.0) between two bitstrings.

    Args:
        bitstring_a: First bitstring
        bitstring_b: Second bitstring

    Returns:
        Normalized distance (0.0 = identical, 1.0 = completely different)
    """
    max_len = max(len(bitstring_a), len(bitstring_b))
    if max_len == 0:
        return 0.0

    distance = hamming_distance(bitstring_a, bitstring_b)
    # Normalize by total number of bits
    total_bits = max_len * 8
    return distance / total_bits if total_bits > 0 else 0.0





