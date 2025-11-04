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


def anonymize_cvr(
    input_file: str,
    output_file: str,
    min_ballots: int = 10,
    stylecol: int = 6,
    headerlen: int = 8
) -> Dict[str, int]:
    """
    Anonymize a CVR file by aggregating rare styles.
    
    Reads a CVR file, identifies styles with fewer than min_ballots,
    and aggregates them into one or more aggregated rows to meet the threshold.
    
    Args:
        input_file: Path to input CVR file
        output_file: Path to output anonymized CVR file
        min_ballots: Minimum number of ballots required per style (default 10)
        stylecol: Index of the style column (default 6 for PrecinctPortion)
        headerlen: Number of header columns before vote data starts (default 8)
    
    Returns:
        Dictionary with statistics about the anonymization process
    """
    stats = {
        'total_rows': 0,
        'rare_styles': 0,
        'aggregated_rows': 0,
        'original_styles': 0,
        'final_styles': 0
    }
    
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
    # Strategy: Group similar rare styles together, ensuring each aggregate has >= min_ballots
    
    # Count total rare ballots
    total_rare_ballots = sum(len(rows) for rows in rare_styles.values())
    
    # CRITICAL: Refuse to create aggregates below threshold
    if total_rare_ballots > 0 and total_rare_ballots < min_ballots:
        raise ValueError(
            f"Cannot anonymize: only {total_rare_ballots} rare ballot(s) found, "
            f"but {min_ballots} ballots are required per style/aggregate for anonymity. "
            f"These ballots cannot be safely anonymized through aggregation. "
            f"They may need to be handled as 'zombies' (not publicly accessible) "
            f"or require alternative anonymization methods."
        )
    
    # No rare ballots - nothing to aggregate
    if total_rare_ballots == 0:
        row_groups = []
    else:
        # Build groups by combining rare styles, preferring similar styles
        # We'll use a greedy algorithm: repeatedly find the best pair of groups to merge
        
        # Start with each rare style as its own group
        style_groups_list = [
            {
                'styles': [style_sig],
                'rows': rows.copy(),
                'size': len(rows)
            }
            for style_sig, rows in rare_styles.items()
        ]
        
        # Greedily merge groups until all groups have >= min_ballots
        # Prefer merging groups that are similar (share contests) and are small
        while True:
            # Check if all groups meet the threshold
            if all(g['size'] >= min_ballots for g in style_groups_list):
                break
            
            # Find the best pair of groups to merge
            # Priority: merge groups that together reach >= min_ballots
            # Among those, prefer merging similar styles (higher similarity)
            best_merge = None
            best_score = -1
            
            for i in range(len(style_groups_list)):
                for j in range(i + 1, len(style_groups_list)):
                    g1, g2 = style_groups_list[i], style_groups_list[j]
                    combined_size = g1['size'] + g2['size']
                    
                    # Calculate average similarity between styles in the two groups
                    similarities = []
                    for s1 in g1['styles']:
                        for s2 in g2['styles']:
                            similarities.append(style_similarity(s1, s2))
                    avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
                    
                    # Score: prioritize merges that reach threshold or are close to it
                    # and prefer similar styles
                    if combined_size >= min_ballots:
                        # High priority: reaches threshold, prefer similar
                        score = 1000 + avg_similarity
                    else:
                        # Lower priority: doesn't reach threshold yet, but prefer similar
                        # Also prefer larger combined sizes
                        score = combined_size + (avg_similarity * 10)
                    
                    if score > best_score:
                        best_score = score
                        best_merge = (i, j)
            
            if best_merge is None:
                # Shouldn't happen if we have >= min_ballots total
                break
            
            # Merge the two groups
            i, j = best_merge
            g1, g2 = style_groups_list[i], style_groups_list[j]
            
            # Merge g2 into g1
            g1['styles'].extend(g2['styles'])
            g1['rows'].extend(g2['rows'])
            g1['size'] = g1['size'] + g2['size']
            
            # Remove g2
            style_groups_list.pop(j)
        
        # Verify all groups meet threshold
        for g in style_groups_list:
            if g['size'] < min_ballots:
                raise RuntimeError(
                    f"Internal error: created aggregate with only {g['size']} ballots, "
                    f"which is below the {min_ballots}-ballot threshold. "
                    f"This should not happen."
                )
        
        # Extract row groups
        row_groups = [g['rows'] for g in style_groups_list]
        
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
    
    # Build a set of rare style rows for quick lookup
    # Use the full row as identifier since we need exact matches
    rare_row_set = set()
    for rows in rare_styles.values():
        for row in rows:
            # Store as tuple for set lookup
            rare_row_set.add(tuple(row))
    
    # Collect all output rows (common rows + aggregated rows)
    output_rows = []
    
    # Add common style rows (skip rare rows)
    for row in all_rows:
        if tuple(row) not in rare_row_set:
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


def main():
    """Command-line interface for CVR anonymization."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Anonymize CVR files by aggregating rare styles',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python anonymize_cvr.py input.csv output.csv
  python anonymize_cvr.py input.csv output.csv --min-ballots 15
        """
    )
    parser.add_argument('input_file', help='Input CVR file path')
    parser.add_argument('output_file', help='Output anonymized CVR file path')
    parser.add_argument('--min-ballots', type=int, default=10,
                       help='Minimum ballots required per style (default: 10)')
    parser.add_argument('--stylecol', type=int, default=6,
                       help='Index of style column (default: 6)')
    parser.add_argument('--headerlen', type=int, default=8,
                       help='Number of header columns (default: 8)')
    
    args = parser.parse_args()
    
    try:
        stats = anonymize_cvr(
            args.input_file,
            args.output_file,
            args.min_ballots,
            args.stylecol,
            args.headerlen
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
