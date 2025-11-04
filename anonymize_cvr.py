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
    # Collect all rare style rows first, preserving their original order
    all_rare_rows = []
    for rows in rare_styles.values():
        all_rare_rows.extend(rows)
    
    # Track groups of rows that will be aggregated together
    # This allows us to merge the last group with remaining rows if needed
    row_groups = []
    current_group = []
    
    for row in all_rare_rows:
        current_group.append(row)
        
        # When we reach min_ballots, finalize this group
        if len(current_group) >= min_ballots:
            row_groups.append(current_group)
            current_group = []
    
    # Handle remaining rows: merge with last group if possible
    if current_group:
        if row_groups and len(current_group) < min_ballots:
            # Merge remaining rows into the last group to ensure anonymity
            row_groups[-1].extend(current_group)
        elif len(current_group) >= min_ballots:
            # Enough rows for a standalone group
            row_groups.append(current_group)
        else:
            # Few remaining rows - create a group anyway (may be below threshold)
            # This preserves all data but may need special handling in audit
            row_groups.append(current_group)
    
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
