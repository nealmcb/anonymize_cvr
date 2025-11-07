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
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


def is_parquet_file(file_path: str) -> bool:
    """
    Check if a file is a Parquet file based on its extension.
    
    Args:
        file_path: Path to the file
    
    Returns:
        True if file appears to be a Parquet file, False otherwise
    """
    return file_path.lower().endswith('.parquet')


def convert_parquet_to_csv_format(parquet_file: str, csv_output: str) -> None:
    """
    Convert a Parquet format CVR file to CSV format expected by this tool.
    
    The Parquet file is in long format (one row per candidate per contest per voter),
    while the CSV format is in wide format (one row per voter with columns for each candidate).
    
    Args:
        parquet_file: Path to input Parquet file
        csv_output: Path to output CSV file
    
    Raises:
        ImportError: If pandas is not available
        ValueError: If the Parquet file doesn't have expected columns
    """
    if not PANDAS_AVAILABLE:
        raise ImportError(
            "pandas is required to read Parquet files. "
            "Install with: pip install pandas pyarrow"
        )
    
    # Read the Parquet file
    df = pd.read_parquet(parquet_file)
    
    # Verify required columns exist
    required_cols = ['voter_id', 'contest', 'candidate', 'isVote', 'precinctPortionId']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Parquet file missing required columns: {missing_cols}. "
            f"Found columns: {list(df.columns)}"
        )
    
    # Filter to only actual votes (isVote=True)
    votes_df = df[df['isVote'] == True].copy()
    
    # Get unique voters and contests
    voters = sorted(votes_df['voter_id'].unique())
    contests = sorted(votes_df['contest'].unique())
    
    # Build a mapping of contest -> candidates
    contest_candidates: Dict[str, List[str]] = {}
    for contest in contests:
        candidates = sorted(votes_df[votes_df['contest'] == contest]['candidate'].unique())
        contest_candidates[contest] = candidates
    
    # Create column headers for CSV format
    # Line 1: Version/Election name
    version_row = ["Parquet CVR", "V1"] + [""] * 6
    
    # Line 2: Contest names (repeated for each candidate)
    contests_row = [""] * 8  # Header columns
    for contest in contests:
        contests_row.extend([contest] * len(contest_candidates[contest]))
    
    # Line 3: Candidate names
    choices_row = [""] * 8
    for contest in contests:
        choices_row.extend(contest_candidates[contest])
    
    # Line 4: Column headers
    headers_row = ["CvrNumber", "TabulatorNum", "BatchId", "RecordId", "ImprintedId",
                   "CountingGroup", "PrecinctPortion", "BallotType"]
    for contest in contests:
        headers_row.extend(contest_candidates[contest])
    
    # Create ballot rows
    ballot_rows = []
    for idx, voter_id in enumerate(voters, 1):
        voter_votes = votes_df[votes_df['voter_id'] == voter_id]
        
        # Get precinct portion (style) from first row for this voter
        precinct_portion = str(int(voter_votes['precinctPortionId'].iloc[0]))
        
        # Initialize row with headers
        row = [
            str(idx),  # CvrNumber
            "1",  # TabulatorNum
            "1",  # BatchId
            str(idx),  # RecordId
            voter_id,  # ImprintedId (use voter_id)
            "1",  # CountingGroup
            precinct_portion,  # PrecinctPortion
            ""  # BallotType
        ]
        
        # Add vote columns
        for contest in contests:
            contest_votes = voter_votes[voter_votes['contest'] == contest]
            for candidate in contest_candidates[contest]:
                # Check if this voter voted for this candidate in this contest
                if len(contest_votes) > 0 and candidate in contest_votes['candidate'].values:
                    row.append("1")
                elif len(contest_votes) > 0:
                    # Contest was on ballot but voter didn't vote for this candidate
                    row.append("0")
                else:
                    # Contest not on voter's ballot
                    row.append("")
        
        ballot_rows.append(row)
    
    # Write CSV file
    with open(csv_output, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(version_row)
        writer.writerow(contests_row)
        writer.writerow(choices_row)
        writer.writerow(headers_row)
        for row in ballot_rows:
            writer.writerow(row)


def pull_style_signature(row: List[str], headerlen: int = 8, stylecol: int = 6) -> str:
    """
    Convert a CVR row into a style signature string.
    
    The signature includes:
    - First 3 characters of the ballot style (PrecinctPortion)
    - For each vote column: "1" if vote was allowed (non-empty), "0" if empty (contest not on ballot)
    
    This matches the approach in the anonymize_cvr.ipynb notebook.
    
    Args:
        row: List of strings representing a CVR row
        headerlen: Number of header columns before vote data starts (default 8)
        stylecol: Index of the style column (default 6 for PrecinctPortion)
    
    Returns:
        Style signature string
    """
    if len(row) <= stylecol:
        style_str = ""
    else:
        style_val = row[stylecol].strip()
        # Extract first 3 characters (handles both "P1" and "105 (105-3)" formats)
        # Take up to 3 characters, no padding
        style_str = style_val[:3]
    
    # For each vote column, indicate if contest appeared on ballot (1) or not (0)
    vote_indicators = ["1" if vote.strip() != '' else "0" for vote in row[headerlen:]]
    return style_str + ''.join(vote_indicators)


def aggregate_votes(rows: List[List[str]], headerlen: int = 8, aggregate_id: str = "") -> List[str]:
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
        aggregated[0] = f"AGG-{len(rows)}"  # Indicate this is an aggregate with count
    
    # CountingGroup (index 5) - set to indicate aggregated
    if len(aggregated) > 5:
        aggregated[5] = "AGGREGATED"
    
    # PrecinctPortion/BallotType (indices 6-7) will be set by caller
    
    # Aggregate vote columns (sum numeric values)
    num_cols = max(len(row) for row in rows)
    for col_idx in range(headerlen, num_cols):
        total = 0
        for row in rows:
            if col_idx < len(row):
                val = row[col_idx].strip()
                if val and val.replace('.', '').replace('-', '').isdigit():
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
    pattern1 = pattern1.ljust(max_len, '0')
    pattern2 = pattern2.ljust(max_len, '0')
    
    # Count overlapping contests (both have the contest)
    intersection = sum(1 for a, b in zip(pattern1, pattern2) if a == '1' and b == '1')
    union = sum(1 for a, b in zip(pattern1, pattern2) if a == '1' or b == '1')
    
    if union == 0:
        return 1.0 if pattern1 == pattern2 else 0.0
    
    return intersection / union


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
            col_idx < len(row) and row[col_idx].strip() != ''
            for col_idx in col_indices
        )
        contest_pattern.append('1' if contest_appears else '0')
    
    return ''.join(contest_pattern)

def compute_descriptive_style_name(contest_pattern: str, ballot_count: int, style_number: int, min_ballots: int = 10) -> str:
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
    contest_count = contest_pattern.count('1')
    rarity = 'R' if ballot_count < min_ballots else 'S'
    return f"{contest_count}{rarity}{style_number}"

def analyze_styles(
    all_rows: List[List[str]],
    contests: List[str],
    choices: List[str],
    headerlen: int = 8,
    stylecol: int = 6,
    min_ballots: int = 10,
    summarize: bool = False
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
        descriptive_name = compute_descriptive_style_name(pattern, ballot_count, style_counter, min_ballots)
        pattern_to_descriptive[pattern] = descriptive_name
        style_counter += 1
    
    # Check for leakage: different CVR style names for same contest pattern
    leakage_warnings = []
    pattern_to_cvr_styles: Dict[str, set] = defaultdict(set)
    
    for row in all_rows:
        if len(row) <= headerlen or len(row) <= stylecol:
            continue
        
        contest_pattern = compute_contest_pattern(row, contests, headerlen)
        cvr_style = row[stylecol].strip()
        pattern_to_cvr_styles[contest_pattern].add(cvr_style)
    
    for pattern, cvr_styles in pattern_to_cvr_styles.items():
        if len(cvr_styles) > 1:
            descriptive_name = pattern_to_descriptive[pattern]
            leakage_warnings.append(
                f"Leakage detected: Contest pattern '{pattern}' (descriptive style '{descriptive_name}') "
                f"has {len(cvr_styles)} different CVR style names: {sorted(cvr_styles)}. "
                f"This may reveal additional information about voters."
            )
    
    # Build mapping from CVR style to descriptive style
    cvr_to_descriptive: Dict[str, str] = {}
    for cvr_style, rows in cvr_style_to_rows.items():
        if rows:
            pattern = compute_contest_pattern(rows[0], contests, headerlen)
            cvr_to_descriptive[cvr_style] = pattern_to_descriptive[pattern]
    
    result = {
        'pattern_to_descriptive': pattern_to_descriptive,
        'cvr_to_descriptive': cvr_to_descriptive,
        'leakage_warnings': leakage_warnings,
        'pattern_to_rows': pattern_to_rows
    }
    
    # Optional summary
    if summarize:
        summary = generate_summary(all_rows, contests, choices, pattern_to_rows, 
                                  pattern_to_descriptive, headerlen)
        result['summary'] = summary
    
    return result

def generate_summary(
    all_rows: List[List[str]],
    contests: List[str],
    choices: List[str],
    pattern_to_rows: Dict[str, List[List[str]]],
    pattern_to_descriptive: Dict[str, str],
    headerlen: int
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
                    if val and (val == '1' or val == '0'):
                        choice_name = choices[col_idx].strip() if col_idx < len(choices) else f"Choice{col_idx}"
                        if val == '1':
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
                    col_idx < len(row) and row[col_idx].strip() != ''
                    for col_idx in col_indices
                )
                
                if contest_appears:
                    eligible_voters[contest_name] += 1
                    for col_idx in col_indices:
                        if col_idx < len(row):
                            val = row[col_idx].strip()
                            choice_name = choices[col_idx].strip() if col_idx < len(choices) else f"Choice{col_idx}"
                            if val == '1':
                                choice_votes[choice_name] += 1
        
        # Calculate probabilities
        probabilities: Dict[str, Dict[str, float]] = {}
        for contest_name in contest_to_columns.keys():
            if contest_name in eligible_voters and eligible_voters[contest_name] > 0:
                prob_dict = {}
                for col_idx in contest_to_columns[contest_name]:
                    choice_name = choices[col_idx].strip() if col_idx < len(choices) else f"Choice{col_idx}"
                    votes = choice_votes.get(choice_name, 0)
                    prob = votes / eligible_voters[contest_name]
                    prob_dict[choice_name] = prob
                probabilities[contest_name] = prob_dict
        
        style_stats[descriptive_name] = {
            'ballot_count': len(rows),
            'contest_pattern': pattern,
            'probabilities': probabilities
        }
    
    return {
        'contest_totals': dict(contest_totals),
        'style_stats': style_stats
    }

def anonymize_cvr(
    input_file: str,
    output_file: str,
    min_ballots: int = 10,
    stylecol: int = 6,
    headerlen: int = 8,
    summarize: bool = False
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
    import tempfile
    import os
    
    stats = {
        'total_rows': 0,
        'rare_styles': 0,
        'aggregated_rows': 0,
        'original_styles': 0,
        'final_styles': 0
    }
    
    # Check if input is Parquet format and convert if needed
    temp_csv = None
    if is_parquet_file(input_file):
        # Create temporary CSV file
        temp_csv = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        temp_csv_path = temp_csv.name
        temp_csv.close()
        
        print(f"Converting Parquet file to CSV format...", file=sys.stderr)
        convert_parquet_to_csv_format(input_file, temp_csv_path)
        input_file = temp_csv_path
    
    try:
        # Detect line terminator from input file
        with open(input_file, 'rb') as f:
            first_chunk = f.read(1024)
            if b'\r\n' in first_chunk:
                lineterminator = '\r\n'
            elif b'\n' in first_chunk:
                lineterminator = '\n'
            elif b'\r' in first_chunk:
                lineterminator = '\r'
            else:
                lineterminator = '\n'  # Default
        
        # Read input file
        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            version = next(reader)
            contests = next(reader)
            choices = next(reader)
            headers = next(reader)
            
            # Read all data rows
            all_rows = list(reader)
            stats['total_rows'] = len(all_rows)
        
        # Analyze styles for leakage detection
        style_analysis = analyze_styles(all_rows, contests, choices, headerlen, stylecol, min_ballots, summarize)
    
        # Report leakage warnings
        if style_analysis['leakage_warnings']:
            print("Warning: Potential information leakage detected:", file=sys.stderr)
            for warning in style_analysis['leakage_warnings']:
                print(f"  {warning}", file=sys.stderr)
    
        # Print style mapping
        if style_analysis['cvr_to_descriptive']:
            print("\nStyle mapping (CVR style -> Descriptive style):")
            for cvr_style in sorted(style_analysis['cvr_to_descriptive'].keys()):
                descriptive = style_analysis['cvr_to_descriptive'][cvr_style]
                print(f"  {cvr_style} -> {descriptive}")
    
        # Print summary if requested
        if summarize and 'summary' in style_analysis:
            summary = style_analysis['summary']
            print("\n=== CVR Summary ===")
        
            print("\nTotals by contest:")
            for contest_name, choice_totals in summary['contest_totals'].items():
                print(f"  {contest_name}:")
                for choice_name, count in sorted(choice_totals.items()):
                    print(f"    {choice_name}: {count}")
        
            print("\nStyle statistics:")
            for style_name, style_info in sorted(summary['style_stats'].items()):
                print(f"  {style_name} ({style_info['ballot_count']} ballots, pattern: {style_info['contest_pattern']}):")
                for contest_name, probs in style_info['probabilities'].items():
                    print(f"    {contest_name}:")
                    for choice_name, prob in sorted(probs.items()):
                        print(f"      {choice_name}: {prob:.4f}")
    
        # Group rows by style signature
        style_groups: Dict[str, List[List[str]]] = defaultdict(list)
        for row in all_rows:
            if len(row) > headerlen:
                style_sig = pull_style_signature(row, headerlen, stylecol)
                style_groups[style_sig].append(row)
    
        stats['original_styles'] = len(style_groups)
    
        # Identify rare and common styles
        rare_styles: Dict[str, List[List[str]]] = {}
        common_styles: Dict[str, List[List[str]]] = {}
    
        for style_sig, rows in style_groups.items():
            if len(rows) < min_ballots:
                rare_styles[style_sig] = rows
                stats['rare_styles'] += len(rows)
            else:
                common_styles[style_sig] = rows
    
        # Aggregate rare styles into groups of at least min_ballots
        # Strategy: Group similar rare styles together, and combine with common styles if needed
        # Prefer combining with popular/common styles that share similar contests
    
        # Count total rare ballots
        total_rare_ballots = sum(len(rows) for rows in rare_styles.values())
    
        # No rare ballots - nothing to aggregate
        if total_rare_ballots == 0:
            row_groups = []
        else:
            # Build groups by combining rare styles, and with common styles if needed
            # We'll use a greedy algorithm: repeatedly find the best pair of groups to merge
        
            # Start with each rare style as its own group
            style_groups_list = [
                {
                    'styles': [style_sig],
                    'rows': rows.copy(),
                    'size': len(rows),
                    'is_rare': True  # Track if group contains rare styles (needs aggregation)
                }
                for style_sig, rows in rare_styles.items()
            ]
        
            # Also create groups for common styles (we may need to borrow ballots from them)
            # Sort common styles by size (most popular first) for preference
            common_style_list = sorted(
                [(style_sig, rows) for style_sig, rows in common_styles.items()],
                key=lambda x: len(x[1]),
                reverse=True
            )
        
            # Greedily merge groups until all rare groups have >= min_ballots
            # We can merge rare groups with each other or with common groups
            while True:
                # Find rare groups that need more ballots
                rare_groups = [g for g in style_groups_list if g['is_rare'] and g['size'] < min_ballots]
                if not rare_groups:
                    break  # All rare groups meet threshold
            
                # Find the best merge option
                best_merge = None
                best_score = -1
                merge_with_common = False
                common_style_to_use = None
            
                for rare_group in rare_groups:
                    needed = min_ballots - rare_group['size']
                
                    # Option 1: Merge with another rare/common group in style_groups_list
                    for j, other_group in enumerate(style_groups_list):
                        if other_group is rare_group:
                            continue
                    
                        combined_size = rare_group['size'] + other_group['size']
                    
                        # Calculate average similarity
                        similarities = []
                        for s1 in rare_group['styles']:
                            for s2 in other_group['styles']:
                                similarities.append(style_similarity(s1, s2))
                        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
                    
                        # Score: prioritize reaching threshold with similar styles
                        if combined_size >= min_ballots:
                            # High priority: reaches threshold
                            # If merging with common style, give bonus for popularity (size)
                            bonus = other_group['size'] if not other_group['is_rare'] else 0
                            score = 1000 + avg_similarity * 100 + bonus
                        else:
                            # Lower priority: doesn't reach threshold yet
                            score = combined_size + (avg_similarity * 10)
                    
                        if score > best_score:
                            best_score = score
                            best_merge = (rare_group, j, None)
                            merge_with_common = False
                
                    # Option 2: Borrow ballots from a common style
                    for style_sig, common_rows in common_style_list:
                        # Calculate how many we can borrow
                        # If borrowing would leave fewer than min_ballots, take all of them
                        # This avoids leaving behind what looks like a rare style
                        remaining_after_borrow = len(common_rows) - needed
                        if remaining_after_borrow < min_ballots and remaining_after_borrow > 0:
                            # Take all ballots to avoid leaving a rare-looking style
                            available = len(common_rows)
                        else:
                            # Borrow only what we need
                            available = min(needed, len(common_rows))
                    
                        if available <= 0:
                            continue  # Can't borrow from this style
                    
                        # Calculate similarity
                        similarities = [
                            style_similarity(rare_sig, style_sig)
                            for rare_sig in rare_group['styles']
                        ]
                        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
                    
                        # Score: prefer popular styles (large size) and similar styles
                        # High priority since we know we can reach threshold
                        score = 2000 + avg_similarity * 100 + len(common_rows)
                    
                        if score > best_score:
                            best_score = score
                            best_merge = (rare_group, None, (style_sig, available))
                            merge_with_common = True
                            common_style_to_use = (style_sig, common_rows)
            
                if best_merge is None:
                    # Cannot create aggregates meeting threshold
                    raise ValueError(
                        f"Cannot anonymize: {total_rare_ballots} rare ballot(s) found, "
                        f"but cannot create aggregate(s) with at least {min_ballots} ballots each. "
                        f"These ballots cannot be safely anonymized through aggregation. "
                        f"They may need to be handled as 'zombies' (not publicly accessible) "
                        f"or require alternative anonymization methods."
                    )
            
                rare_group, other_idx, borrow_info = best_merge
            
                if merge_with_common and borrow_info:
                    # Borrow ballots from common style
                    style_sig, needed_count = borrow_info
                    common_rows = common_style_to_use[1]
                
                    # Take ballots from the common style
                    borrowed_rows = common_rows[:needed_count]
                    common_style_rows_remaining = common_rows[needed_count:]
                
                    # Add to rare group
                    rare_group['styles'].append(style_sig)
                    rare_group['rows'].extend(borrowed_rows)
                    rare_group['size'] += needed_count
                
                    # Update common style (remove borrowed ballots)
                    # Find and update the common style group if it exists, or update the list
                    common_styles[style_sig] = common_style_rows_remaining
                    # Update the common_style_list for next iteration
                    common_style_list = [
                        (sig, rows) for sig, rows in common_style_list
                        if sig != style_sig or len(rows) > min_ballots
                    ]
                    if len(common_style_rows_remaining) >= min_ballots:
                        # Reinsert in sorted position
                        common_style_list.append((style_sig, common_style_rows_remaining))
                        common_style_list.sort(key=lambda x: len(x[1]), reverse=True)
                
                else:
                    # Merge two existing groups
                    other_group = style_groups_list[other_idx]
                
                    # Merge other_group into rare_group
                    rare_group['styles'].extend(other_group['styles'])
                    rare_group['rows'].extend(other_group['rows'])
                    rare_group['size'] += other_group['size']
                    rare_group['is_rare'] = rare_group['is_rare'] or other_group['is_rare']
                
                    # Remove other_group
                    style_groups_list.pop(other_idx)
        
            # Verify all rare groups meet threshold
            for g in style_groups_list:
                if g['is_rare'] and g['size'] < min_ballots:
                    raise RuntimeError(
                        f"Internal error: created aggregate with only {g['size']} ballots, "
                        f"which is below the {min_ballots}-ballot threshold. "
                        f"This should not happen."
                    )
        
            # Extract row groups (only rare groups need to be aggregated)
            row_groups = [g['rows'] for g in style_groups_list if g['is_rare']]
        
            # Update common_styles to reflect any borrowed ballots
            # (common_styles dict was updated during the merge process)
        
            # Optional: Verify that each contest appears at least min_ballots times across aggregates
            # This helps ensure that aggregated rows provide enough diversity for anonymity
            # Note: This is a best-effort check - if a contest only appears on a few rare ballots,
            # we can't enforce this without excluding ballots, which we don't do
            if row_groups and headerlen < len(contests):
                # Map contest names to the set of column indices that belong to that contest
                contest_to_columns = defaultdict(set)
                for col_idx in range(headerlen, len(contests)):
                    contest_name = contests[col_idx].strip()
                    if contest_name:
                        contest_to_columns[contest_name].add(col_idx)
            
                # Count how many individual ballots have each contest
                contest_ballot_counts = defaultdict(int)
                for group in row_groups:
                    for row in group:
                        for contest_name, col_indices in contest_to_columns.items():
                            # Check if any column for this contest is non-empty (contest appears on this ballot)
                            if any(col_idx < len(row) and row[col_idx].strip() for col_idx in col_indices):
                                contest_ballot_counts[contest_name] += 1
            
                # Warn if any contest appears on fewer than min_ballots ballots across aggregates
                low_contest_counts = {
                    contest_name: count
                    for contest_name, count in contest_ballot_counts.items()
                    if count < min_ballots
                }
                if low_contest_counts:
                    import warnings
                    for contest_name, count in low_contest_counts.items():
                        warnings.warn(
                            f"Contest '{contest_name[:60]}' appears on only {count} ballot(s) in aggregated rows, "
                            f"which is below the {min_ballots}-ballot threshold. "
                            f"This may reduce anonymity protection for this contest.",
                            UserWarning
                        )
    
        # Create aggregated rows from the row groups
        aggregated_groups = []
        for i, group in enumerate(row_groups):
            agg_id = f"AGGREGATED-{i + 1}"
            aggregated_row = aggregate_votes(group, headerlen, aggregate_id=agg_id)
            # Mark as aggregated in style field (PrecinctPortion)
            aggregated_row[stylecol] = agg_id
            aggregated_groups.append(aggregated_row)
    
        stats['aggregated_rows'] = len(aggregated_groups)
        stats['final_styles'] = len(common_styles) + len(aggregated_groups)
    
        # Build sets for tracking which rows to exclude (rare rows and borrowed common rows)
        rare_row_set = set()
        for rows in rare_styles.values():
            for row in rows:
                rare_row_set.add(tuple(row))
    
        # Also track rows that were borrowed from common styles for aggregation
        # We need to find which common style rows were used in aggregates
        borrowed_row_set = set()
        if row_groups:
            # Create a set of all rows that will be in aggregates
            for group in row_groups:
                for row in group:
                    row_tuple = tuple(row)
                    # If it's not a rare row, it must be a borrowed common row
                    if row_tuple not in rare_row_set:
                        borrowed_row_set.add(row_tuple)
    
        # Collect all output rows
        output_rows = []
    
        # Add common style rows (skip rare rows and borrowed rows)
        for row in all_rows:
            row_tuple = tuple(row)
            if row_tuple not in rare_row_set and row_tuple not in borrowed_row_set:
                output_rows.append(row)
    
        # Add aggregated rows
        output_rows.extend(aggregated_groups)
    
        # Sort rows numerically by CvrNumber (column 0)
        # Handle both numeric CvrNumbers and "AGGREGATED-N" strings
        def sort_key(row):
            if not row:
                return (1, '')  # Empty rows go to end
            cvr_num = row[0].strip()
            # Check if it's an aggregated row
            if cvr_num.startswith('AGGREGATED-'):
                # Extract number from "AGGREGATED-N" and put at very end
                try:
                    num = int(cvr_num.split('-')[1])
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
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, lineterminator=lineterminator)
            writer.writerow(version)
            writer.writerow(contests)
            writer.writerow(choices)
            writer.writerow(headers)
        
            # Write sorted rows
            for row in output_rows:
                writer.writerow(row)
    
            return stats
    
    finally:
        # Clean up temporary CSV file if we created one
        if temp_csv is not None:
            try:
                import os
                os.unlink(temp_csv_path)
            except Exception:
                pass  # Ignore cleanup errors


def main():
    """Command-line interface for CVR anonymization."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Anonymize CVR files by aggregating rare styles (supports CSV and Parquet formats)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python anonymize_cvr.py input.csv output.csv
  python anonymize_cvr.py input.parquet output.csv
  python anonymize_cvr.py input.csv output.csv --min-ballots 15
        """
    )
    parser.add_argument('input_file', help='Input CVR file path (CSV or Parquet format)')
    parser.add_argument('output_file', help='Output anonymized CVR file path')
    parser.add_argument('--min-ballots', type=int, default=10,
                       help='Minimum ballots required per style (default: 10)')
    parser.add_argument('--stylecol', type=int, default=6,
                       help='Index of style column (default: 6)')
    parser.add_argument('--headerlen', type=int, default=8,
                       help='Number of header columns (default: 8)')
    parser.add_argument('--summarize', '-s', action='store_true',
                       help='Print detailed summary of CVR statistics')
    
    args = parser.parse_args()
    
    try:
        stats = anonymize_cvr(
            args.input_file,
            args.output_file,
            args.min_ballots,
            args.stylecol,
            args.headerlen,
            args.summarize
        )
        
        print(f"Anonymization complete!")
        print(f"  Total rows processed: {stats['total_rows']}")
        print(f"  Original styles: {stats['original_styles']}")
        print(f"  Rare style ballots: {stats['rare_styles']}")
        print(f"  Aggregated rows created: {stats['aggregated_rows']}")
        print(f"  Final styles: {stats['final_styles']}")
        print(f"  Output written to: {args.output_file}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
