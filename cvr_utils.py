#!/usr/bin/env python3
"""
Utility functions for reading CVR files in different formats.

Supports both CSV and Parquet formats, with automatic format detection
and conversion to the expected CSV format.
"""

import csv
import tempfile
import os
from typing import Dict, List

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


class TempCVRFile:
    """
    Context manager for handling CVR files that may need conversion from Parquet to CSV.
    
    If the input file is a Parquet file, it converts it to a temporary CSV file.
    The temporary file is automatically cleaned up when the context exits.
    
    Usage:
        with TempCVRFile(input_path) as csv_path:
            # Use csv_path to read the CVR data
            process_cvr(csv_path)
    """
    
    def __init__(self, input_path: str):
        """
        Initialize the context manager.
        
        Args:
            input_path: Path to input CVR file (CSV or Parquet)
        """
        self.input_path = input_path
        self.temp_file = None
        self.temp_path = None
        self.is_parquet = is_parquet_file(input_path)
    
    def __enter__(self) -> str:
        """
        Enter the context, converting Parquet to CSV if needed.
        
        Returns:
            Path to CSV file (either original or temporary converted file)
        """
        if self.is_parquet:
            # Create temporary CSV file
            self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
            self.temp_path = self.temp_file.name
            self.temp_file.close()
            
            # Convert Parquet to CSV
            convert_parquet_to_csv_format(self.input_path, self.temp_path)
            return self.temp_path
        else:
            # Already CSV, return original path
            return self.input_path
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context, cleaning up temporary file if created.
        """
        if self.temp_path is not None:
            try:
                os.unlink(self.temp_path)
            except Exception:
                pass  # Ignore cleanup errors
        return False  # Don't suppress exceptions
