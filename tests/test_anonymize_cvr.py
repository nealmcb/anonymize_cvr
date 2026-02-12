"""Tests for CVR anonymization functionality."""

import pytest
from anonymize_cvr import pull_style_signature, aggregate_votes


def test_pull_style_signature_basic() -> None:
    """Test basic style signature generation."""
    # Row with votes in first two contests
    row = ["1", "2", "3", "4", "5", "6", "7", "8", "Alice", "Bob", "", "", ""]
    signature = pull_style_signature(row, headerlen=8)
    assert signature == "11000"
    
    # Row with all contests voted
    row_all = ["1", "2", "3", "4", "5", "6", "7", "8", "Alice", "Bob", "Carol", "Dave", "Eve"]
    signature_all = pull_style_signature(row_all, headerlen=8)
    assert signature_all == "11111"
    
    # Row with no votes (all contests blank)
    row_none = ["1", "2", "3", "4", "5", "6", "7", "8", "", "", "", "", ""]
    signature_none = pull_style_signature(row_none, headerlen=8)
    assert signature_none == "00000"


def test_pull_style_signature_whitespace() -> None:
    """Test that whitespace is handled correctly in style signatures."""
    # Spaces should be treated as empty (no vote)
    row = ["1", "2", "3", "4", "5", "6", "7", "8", "Alice", "  ", "", "Dave", ""]
    signature = pull_style_signature(row, headerlen=8)
    assert signature == "10010"


def test_aggregate_votes_basic() -> None:
    """Test basic vote aggregation."""
    rows = [
        ["1", "2", "3", "4", "5", "6", "7", "8", "1", "0", "0"],
        ["2", "2", "3", "4", "5", "6", "7", "8", "0", "1", "0"],
        ["3", "2", "3", "4", "5", "6", "7", "8", "1", "0", "1"],
    ]
    
    aggregated = aggregate_votes(rows, headerlen=8, aggregate_id="AGG-1")
    
    # Check header fields
    assert aggregated[0] == "AGG-1"  # CvrNumber
    assert aggregated[1] == ""  # TabulatorNum
    assert aggregated[2] == ""  # BatchId
    assert aggregated[3] == ""  # RecordId
    assert aggregated[4] == ""  # ImprintedId
    
    # Check vote totals (columns 8, 9, 10)
    assert aggregated[8] == "2"  # Sum of 1 + 0 + 1
    assert aggregated[9] == "1"  # Sum of 0 + 1 + 0
    assert aggregated[10] == "1"  # Sum of 0 + 0 + 1


def test_aggregate_votes_empty() -> None:
    """Test aggregation with empty row list."""
    aggregated = aggregate_votes([], headerlen=8)
    assert aggregated == []


def test_aggregate_votes_single_row() -> None:
    """Test aggregation with single row."""
    rows = [
        ["1", "2", "3", "4", "5", "6", "7", "8", "5", "3", "2"],
    ]
    
    aggregated = aggregate_votes(rows, headerlen=8, aggregate_id="AGG-1")
    
    assert aggregated[0] == "AGG-1"
    assert aggregated[8] == "5"
    assert aggregated[9] == "3"
    assert aggregated[10] == "2"
