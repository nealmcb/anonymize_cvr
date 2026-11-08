#!/usr/bin/env python3
"""
Unit tests for batch matching functionality.

Tests compare batches from test_batch_matching_laplata.csv which contains:
- Batch 103:1 - original batch
- Batch 103:435 - exact duplicate of 103:1
- Batch 103:436 - modified version of 103:1 (2 ballots with votes removed)
- Batch 103:437 - missing 2 ballots from 103:1
- Batch 103:200 - duplicate of 103:2 with 1 style mismatch (24/25 styles match)
- Batch 103:240 - duplicate of 103:3 with 2 style mismatches (23/25 styles match)
- Batch 103:280 - duplicate of 103:4 with 3 style mismatches (22/25 styles match)
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import pytest
from anonymize_cvr.batch_matching import (
    compare_batches,
    compute_batch_signature,
    BatchComparisonResult,
)

# Test CVR file with known test cases
TEST_CVR_FILE = Path(__file__).parent.parent / "test_batch_matching_laplata.csv"


class TestExactDuplicate:
    """Test case: Batch 103:1 vs 103:435 (exact duplicate)."""

    def test_exact_duplicate_match(self):
        """Exact duplicate should have match score 1.0 and strict match."""
        result = compare_batches(
            str(TEST_CVR_FILE), "103", "1", "103", "435"
        )

        assert result.is_same_batch is True
        assert result.confidence == 1.0
        assert result.match_type == "strict"
        assert result.strict_hash_match is True
        assert result.cardinality_match is True
        assert result.style_histogram_match is True
        assert result.contest_schema_match is True

    def test_exact_duplicate_signatures(self):
        """Exact duplicate should have identical signatures."""
        sig_a = compute_batch_signature(str(TEST_CVR_FILE), "103", "1")
        sig_b = compute_batch_signature(str(TEST_CVR_FILE), "103", "435")

        assert sig_a.cardinality == sig_b.cardinality == 25
        assert sig_a.style_histogram == sig_b.style_histogram
        assert sig_a.contest_schema == sig_b.contest_schema
        assert sig_a.strict_hash_multiset == sig_b.strict_hash_multiset


class TestModifiedBallots:
    """Test case: Batch 103:1 vs 103:436 (2 ballots modified)."""

    def test_modified_ballots_match(self):
        """Modified ballots should have fuzzy match with score around 0.7."""
        result = compare_batches(
            str(TEST_CVR_FILE), "103", "1", "103", "436"
        )

        assert result.is_same_batch is True
        assert result.confidence == pytest.approx(0.7, abs=0.01)
        assert result.match_type == "fuzzy"
        assert result.strict_hash_match is False
        assert result.cardinality_match is True
        assert result.fuzzy_match_rate is not None
        assert result.fuzzy_match_rate == pytest.approx(0.92, abs=0.01)  # 23/25 matched
        # Penalty should be applied to all unmatched ballots (no tolerance)
        assert result.unmatched_count == 2
        assert result.penalty == pytest.approx(2.0 / 25.0, abs=0.001)  # 2/25 = 0.08
        assert result.adjusted_match_rate == pytest.approx(0.92 - 0.08, abs=0.01)  # 0.84

    def test_modified_ballots_metrics(self):
        """Modified ballots should have specific metrics."""
        result = compare_batches(
            str(TEST_CVR_FILE), "103", "1", "103", "436"
        )

        # Matched ballots should be identical (mean Hamming = 0.0)
        assert result.mean_hamming_distance == pytest.approx(0.0, abs=0.0001)

        # Sketch distance should be small but non-zero
        assert result.sketch_distance is not None
        assert 0.0 < result.sketch_distance < 0.1

        # LCS ratio should be less than 1.0 due to modifications
        assert result.lcs_ratio is not None
        assert result.lcs_ratio < 1.0


class TestMissingBallots:
    """Test case: Batch 103:1 vs 103:437 (2 ballots missing)."""

    def test_missing_ballots_elimination(self):
        """Missing ballots should be eliminated by cardinality check."""
        result = compare_batches(
            str(TEST_CVR_FILE), "103", "1", "103", "437"
        )

        assert result.is_same_batch is False
        assert result.confidence == 0.0
        assert result.match_type == "none"
        assert result.elimination_reason == "different_cardinality"
        assert result.cardinality_match is False

    def test_missing_ballots_cardinality(self):
        """Missing ballots should have different cardinalities."""
        sig_a = compute_batch_signature(str(TEST_CVR_FILE), "103", "1")
        sig_b = compute_batch_signature(str(TEST_CVR_FILE), "103", "437")

        assert sig_a.cardinality == 25
        assert sig_b.cardinality == 23
        assert sig_a.cardinality != sig_b.cardinality


class TestBatchSignatures:
    """Test batch signature computation."""

    def test_signature_cardinality(self):
        """Signatures should have correct cardinality."""
        sig = compute_batch_signature(str(TEST_CVR_FILE), "103", "1")
        assert sig.cardinality == 25
        assert len(sig.ballots) == 25

    def test_signature_contest_schema(self):
        """Signatures should capture contest schema."""
        sig = compute_batch_signature(str(TEST_CVR_FILE), "103", "1")
        assert len(sig.contest_schema) > 0
        assert isinstance(sig.contest_schema, set)

    def test_signature_cluster_histogram(self):
        """Signatures should have cluster histogram."""
        sig = compute_batch_signature(str(TEST_CVR_FILE), "103", "1")
        assert len(sig.cluster_histogram) > 0
        # Sum of histogram should equal cardinality
        assert sum(sig.cluster_histogram.values()) == sig.cardinality


class TestDifferentBatches:
    """Test comparing clearly different batches."""

    def test_different_batches_low_score(self):
        """Different batches should have low match scores."""
        # Compare batch 1 with a different batch (e.g., batch 2)
        # This may or may not match, but if it does, score should be low
        result = compare_batches(
            str(TEST_CVR_FILE), "103", "1", "103", "2"
        )

        # If not eliminated, score should be low
        if result.elimination_reason is None:
            assert result.confidence < 0.7
        else:
            # Or eliminated for good reason
            assert result.elimination_reason in [
                "different_cardinality",
                "different_styles",
                "different_contests",
            ]


class TestStyleMismatches:
    """Test cases with style mismatches (should still match if ballots are close)."""

    def test_one_style_mismatch(self):
        """Batch with 1 style mismatch (24/25 match) should still compare."""
        result = compare_batches(
            str(TEST_CVR_FILE), "103", "2", "103", "200"
        )

        # Should not be eliminated (allows up to 2 style mismatches)
        assert result.elimination_reason is None
        assert result.fuzzy_match_rate is not None
        # Close but not perfect match (has 1 vote change)
        assert result.fuzzy_match_rate >= 0.90  # Most ballots match
        assert result.adjusted_match_rate is not None
        assert result.unmatched_count is not None
        assert result.penalty is not None
        # Should be identified as same batch if close enough
        assert result.is_same_batch is True
        assert result.confidence >= 0.6

    def test_two_style_mismatches(self):
        """Batch with 2 style mismatches (23/25 match) should still compare."""
        result = compare_batches(
            str(TEST_CVR_FILE), "103", "3", "103", "240"
        )

        assert result.elimination_reason is None
        assert result.fuzzy_match_rate is not None
        # Close but not perfect match (has 2 vote changes)
        assert result.fuzzy_match_rate >= 0.85
        assert result.adjusted_match_rate is not None
        assert result.unmatched_count is not None
        assert result.penalty is not None
        # Should be identified as same batch if close enough
        assert result.is_same_batch is True
        assert result.confidence >= 0.6

    def test_three_style_mismatches(self):
        """Batch with 3 style mismatches (22/25 match) should be eliminated."""
        result = compare_batches(
            str(TEST_CVR_FILE), "103", "4", "103", "280"
        )

        # 3 style mismatches exceeds tolerance (2), so should be eliminated
        assert result.elimination_reason == "different_styles"
        assert result.is_same_batch is False
        assert result.confidence == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

