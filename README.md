# CVR Anonymization Tool

Software to anonymize Cast Vote Records (CVR) files to meet Colorado's requirement that styles with fewer than 10 ballots per style must be anonymized to protect voter privacy.

## Background

This tool addresses the requirement from **Colorado Open Records Act (C.R.S. 24-72-205.5)** which requires counties to cover or redact before "making available for public inspection" a voted ballot if there are fewer than 10 instances of the ballot's style in the election.

The anonymization process aggregates rare styles (those with fewer than 10 ballots) together to meet the minimum threshold while preserving ballot anonymity for Risk-Limiting Tabulation Audits.

## Status

This is alpha-quality software. Use at your own risk.

### Legal and Research Foundation

- **Colorado Open Records Act (C.R.S. 24-72-205.5)**: Requires anonymization of ballots with fewer than 10 instances per style
- **Colorado Risk-Limiting Tabulation Audit**: CVRs must be available for public audit purposes while preserving ballot anonymity
- [Colorado Risk-Limiting Tabulation Audit: Preserving Anonymity of Cast Vote Record](http://www.sos.state.co.us/pubs/rule_making/hearings/2018/20180309BranscombEtAl.pdf) (Branscomb et al., March 9, 2018) - Endorsed by John McCarthy, Neal McBurnett, Harvie Branscomb, Ron Rivest, Philip Stark

## Documentation

- **specification.md**: Detailed specification of requirements, algorithms, and implementation details
- **AGENTS.md**: Guidelines for AI agent interactions with this codebase

## Tools

### anonymize_cvr.py

Anonymizes CVR files by aggregating rare styles to meet the 10-ballot minimum threshold. Supports both CSV and Parquet file formats.

**Usage:**
```bash
python3 anonymize_cvr.py input.csv output.csv
python3 anonymize_cvr.py input.parquet output.csv
python3 anonymize_cvr.py input.csv output.csv --min-ballots 15
python3 anonymize_cvr.py input.csv output.csv --summarize
```

**Features:**
- Supports CSV and Parquet file formats (auto-detected by file extension)
- Combines all rare styles (< 10 ballots) into a single aggregation
- Ensures at least 10 ballots per contest in the aggregation
- Adds contrasting votes to prevent unanimous/near-unanimous patterns
- **Anonymizes identifying fields**: CountingGroup and PrecinctPortion are dynamically detected from headers and blanked in all output rows to prevent revealing geographic or voting method information beyond the contest bitmap
- **Preserves BallotType**: BallotType is preserved in non-aggregated rows (set to "AGGREGATED" in aggregated rows). The tool warns if BallotType varies for ballots with the same contest pattern, which could indicate information leakage. BallotType values are displayed in the style mapping output
- Computes descriptive style names based on contest patterns
- Detects information leakage when different CVR style names map to the same contest pattern
- Automatic tally verification ensures vote totals match between original and anonymized CVR
- Comprehensive aggregation statistics showing:
  - Totals after including all rare styles (with ballot counts, vote counts, and undervotes)
  - Contests needing additional ballots (with reasons: had X, needed Y more to reach Z)
  - Contests needing balancing (unanimous/near-unanimous patterns)
  - Total extra CVRs added to aggregate
  - Final aggregate totals (with ballot counts, vote counts, and undervotes)
- Style mapping output includes BallotType information for each CVR style
- Optional summary statistics with `--summarize` flag

**Options:**
- `--min-ballots`: Minimum ballots required per style (default: 10)
- `--stylecol`: Index of style column (default: 6)
- `--headerlen`: Number of header columns (default: 8)
- `--summarize, -s`: Print detailed summary of CVR statistics

### guess_votes.py

Generates test cases and analyzes how anonymization affects vote guessing probabilities. Supports both CSV and Parquet file formats.

**Usage:**
```bash
# Generate test case with default settings
python3 guess_votes.py

# Analyze an existing CVR file
python3 guess_votes.py original_cvr.csv
python3 guess_votes.py original_cvr.parquet

# Compare original vs anonymized CVR
python3 guess_votes.py original_cvr.csv --anonymized-cvr anonymized_cvr.csv
```

**Features:**
- Supports CSV and Parquet file formats (auto-detected by file extension)
- Generates test CVR files with configurable ballot styles
- Calculates vote probabilities from:
  - Overall election results
  - Original CVR file (style-level probabilities)
  - Anonymized CVR file (aggregated probabilities)
- Generates three probability files for comparison:
  - `test_case_results_probabilities.csv`: Overall election results
  - `test_case_original_probabilities.csv`: Original CVR-refined probabilities
  - `test_case_anonymized_probabilities.csv`: Anonymized CVR-refined probabilities

**Options:**
- `original_cvr_file`: Path to original CVR file (CSV or Parquet format) (positional, optional)
- `--anonymized-cvr, -a`: Path to anonymized CVR file (CSV or Parquet format)
- `--election-name, -n`: Name of the election (default: "Test Election 2024")
- `--min-ballots, -m`: Minimum ballots per style to be considered common (default: 10)

### cvr_utils.py

Shared utility module for reading CVR files in different formats. This module provides:
- Automatic format detection (CSV vs Parquet)
- Conversion from Parquet to CSV format
- `TempCVRFile` context manager for seamless handling of both formats

## Example Workflow

1. **Anonymize a CVR file:**
   ```bash
   python3 anonymize_cvr.py original_cvr.csv anonymized_cvr.csv --summarize
   ```

2. **Generate probability analysis:**
   ```bash
   python3 guess_votes.py original_cvr.csv --anonymized-cvr anonymized_cvr.csv
   ```

3. **Compare the three probability files** to quantify how anonymization affects vote guessing accuracy.

## Aggregation Approach

The anonymization tool uses a balance-focused approach:

1. **Combine all rare styles**: All ballots from rare styles (< 10 ballots) are combined into a single aggregation
2. **Meet minimum thresholds**: If needed, ballots are borrowed from common styles to ensure:
   - At least 10 ballots total in the aggregation
   - At least 10 ballots per contest in the aggregation
3. **Balance votes**: The tool checks for unanimous or near-unanimous patterns (all but 2 votes for the same candidate) and adds contrasting votes from common styles to break these patterns
4. **Anonymize identifying fields**: CountingGroup and PrecinctPortion are blanked in all output rows to prevent revealing geographic or voting method information. BallotType is preserved in non-aggregated rows (it should only reflect contest pattern, not additional identifying information). Note that if this sort of information is visible on the printed ballot, that should be taken into account when procedures for releasing ballot images are designed.
5. **Verify tallies**: Before delivering the redacted CVR, vote tallies are automatically verified to match the original

This approach minimizes the number of ballots that need to be redacted while ensuring both anonymity and statistical balance.

## Style Analysis

The anonymization tool automatically:
- Computes descriptive style names based on contest patterns (format: `<n><R|S><m>` where n=contest count, R=rare/S=common, m=style number)
- Maps CVR style names to descriptive style names, including BallotType information for each style
- Detects information leakage when different CVR style names or BallotType values are used for ballots with the same contest pattern
- Provides optional summaries showing vote totals and probabilities by style
- Displays detailed aggregation statistics including totals (with ballot counts, vote counts, and undervotes), contests needing balancing, and extra CVRs added

## Requirements

- Python 3.12+
- Standard library only (csv, collections, typing) for CSV files
- Optional: `pandas` and `pyarrow` for Parquet file support
  - Install with: `pip install pandas pyarrow`
- Optional but recommended: `python-simhash` for faster batch matching
  - Install with: `pip install python-simhash`
  - The batch matching tool will use a local fallback if not installed, but the PyPI library is significantly faster (Rust-based implementation)

## Batch Matching Tool

The batch matching tool (`batch_cli.py`) compares batches of ballots to determine if they contain the same physical ballots. This is useful for detecting duplicate batches or verifying batch integrity.

**Usage:**
```bash
# Compare two specific batches
python3 batch_cli.py compare -f file.csv -a "103:1" -b "103:2"

# List all batches in a file
python3 batch_cli.py list-batches -f file.csv

# Find the closest matching pairs
python3 batch_cli.py find-closest -f file.csv --top-n 10

# Compare all pairs
python3 batch_cli.py compare-all-pairs -f file.csv
```

### Interpreting Comparison Metrics

#### Overall Match Score

The **match score** (0.0 to 1.0) is calculated as follows:

1. **1.0**: Strict hash match - all ballots have identical vote patterns (SHA-256 hashes match exactly)
2. **0.95**: Fuzzy match with sketch distance < 0.1 and LCS ratio > 0.9
3. **0.85**: Fuzzy match with sketch distance < 0.2 and LCS ratio > 0.8
4. **0.70**: Match rate > 0.9 and mean Hamming distance < 0.5
5. **Otherwise**: `max(0.0, match_rate - (mean_hamming * 0.5))`

The match score combines multiple similarity metrics into a single value. Higher scores indicate stronger similarity, but the score alone doesn't determine if batches are the same - use the `is_same_batch` field and individual metrics for interpretation.

#### Mean Hamming Distance

**Mean normalized Hamming distance** measures the average bit-level difference between matched ballot pairs. It's computed as the mean of normalized Hamming distances across all matched pairs from the fuzzy matching algorithm.

- **Range**: 0.0 to 1.0 (normalized by bitstring length)
- **0.000000**: All matched ballots are bitwise identical (no differences)
- **0.050000**: On average, 5% of bits differ between matched ballots

**Important note on sparse ballots**: In most elections, ballots are sparse - a typical ballot may have 40 contests with 100 total choices, but only ~100 bits set (votes cast). The remaining choices are either "0" (not voted) or "" (not on ballot). The bitstring encoding preserves this trinary nature ("1" = voted, "0" = not voted, "" = not on ballot) as UTF-8 bytes, and SimHash processes these bytes correctly.

**Example calculations** (for typical ballot: 40 contests, 100 total choices, ~100 bits set, ~4000 bytes total):
- Mean Hamming distance of **0.000000**: All matched ballots are identical (0 bits differ)
- Mean Hamming distance of **0.050000**: Average of ~200 bits differ per matched ballot (4000 bytes × 8 × 0.05 = 1600 bits)
  - For 25 ballots, that's approximately 40,000 total differing bits across all matched pairs
  - This represents significant differences in vote patterns
- Mean Hamming distance of **0.100000**: Average of ~3200 bits differ per matched ballot
- Mean Hamming distance of **0.200000**: Average of ~6400 bits differ per matched ballot

The normalized distance accounts for different ballot lengths by dividing the raw Hamming distance by the bitstring length. A mean Hamming distance of 0.05 represents a significant number of bit differences and should not be considered "small" - it indicates substantial differences in vote patterns.

**Trinary data handling**: The bitstring encoding uses UTF-8 to represent trinary vote values ("1" = voted, "0" = not voted, "" = not on ballot). SimHash processes these bytes directly and correctly handles the sparse nature of ballot data. The algorithm works on the byte representation regardless of the semantic meaning of the values.

#### Sketch Distance

**Sketch distance** measures the similarity of SimHash cluster distributions between batches using **Jensen-Shannon divergence** (not Earth Mover's Distance). It compares histograms of SimHash bucket counts, where each ballot's SimHash is assigned to a bucket based on its high-order 8 bits (256 possible buckets, numbered 0-255).

- **Range**: 0.0 to 1.0 (Jensen-Shannon divergence, divided by 2)
- **0.000000**: Identical cluster distributions
- **< 0.100000**: Very similar distributions
- **0.100000 - 0.200000**: Similar distributions
- **> 0.500000**: Very different distributions

**SimHash Buckets**: Each 64-bit SimHash value is assigned to a bucket using the high 8 bits, creating 256 possible buckets (0-255). In practice, a batch of 25 ballots typically uses 10-15 buckets.

**Real examples** (from test data with 25 ballots, 14 contests):
- **Exact duplicate** (batch 103:1 vs 103:435):
  - Sketch distance: **0.000000**
  - Both batches use 11 buckets with identical distributions: `{60: 5, 195: 1, 124: 4, 30: 2, 56: 1, 116: 4, 84: 4, 93: 1, 126: 1, 8: 1, 32: 1}`
- **Modified ballots** (batch 103:1 vs 103:436, 2 ballots modified):
  - Sketch distance: **0.049804**
  - Batch A uses 11 buckets, Batch B uses 12 buckets
  - Distribution changes: bucket 124 changes from 4 to 2, bucket 88 appears with 2 ballots

The metric uses Jensen-Shannon divergence, computed by:
1. Normalizing each batch's cluster histogram to probabilities
2. Computing the JS divergence between the two probability distributions
3. Dividing by 2 to get a value in [0, 1]

#### Match Rate

**Match rate** is the fraction of ballots in batch A that were successfully matched to ballots in batch B using the fuzzy matching algorithm. A ballot is considered matched if its SimHash distance is ≤ 8 and its normalized Hamming distance is ≤ 0.3.

- **Range**: 0.0 to 1.0
- **1.0**: All ballots matched
- **0.9**: 90% of ballots matched (e.g., 23 out of 25 ballots)

**Example variations**:
- Match rate of 1.0 with mean Hamming 0.0: All ballots matched exactly (strict match)
- Match rate of 0.92 with mean Hamming 0.0: 23 out of 25 ballots matched exactly, 2 unmatched
- Match rate of 0.88 with mean Hamming 0.05: 22 out of 25 ballots matched with small differences

#### LCS Ratio

**Longest Common Subsequence (LCS) ratio** measures how well the ballot sequences align when ordered by sequence index (RecordId or ImprintedId). It's the length of the LCS divided by the minimum batch size.

- **Range**: 0.0 to 1.0
- **1.0**: Ballots are in identical sequence order
- **0.6**: 60% of ballots appear in the same relative order (e.g., 15 out of 25 ballots in sequence)

**Example**: For batches of 25 ballots:
- LCS ratio of 1.0: All ballots in same order
- LCS ratio of 0.8: 20 ballots in same order, 5 out of order
- LCS ratio of 0.4: 10 ballots in same order, 15 out of order or missing

#### Example Scenarios (from test_batch_matching_laplata.csv)

**Exact duplicate batch** (batch 103:1 vs 103:435):
- Match score: **1.0000**
- Match rate: N/A (strict match)
- Mean Hamming: **0.000000** (all ballots identical)
- Sketch distance: **0.000000** (identical cluster distributions)
- LCS ratio: N/A
- Cardinality: 25 ballots each
- Ballot size: 44 bytes (352 bits), 14 contests

**Batch with 2 modified ballots** (batch 103:1 vs 103:436, votes removed to create undervotes):
- Match score: **0.7000**
- Match rate: **0.9200** (23 out of 25 ballots matched)
- Mean Hamming: **0.000000** (matched ballots are identical; 2 unmatched)
- Sketch distance: **0.049804** (slight distribution change: 11 vs 12 buckets used)
- LCS ratio: **0.4000** (10 ballots in sequence, 15 out of order)
- Cardinality: 25 ballots each

**Batch with 2 missing ballots** (batch 103:1 vs 103:437):
- Match score: **0.0000**
- Elimination reason: **different_cardinality**
- Cardinality: 25 vs 23 ballots
- Comparison stops at quick elimination check

**Different batches with similar ballots**:
- Match score: Typically **0.0-0.5** (depends on similarity)
- Match rate: **0.0-0.8** (some ballots may match by chance)
- Mean Hamming: **0.1-0.5** (matched ballots have significant differences)
- Sketch distance: **0.3-0.8** (very different cluster distributions)
- LCS ratio: **0.2-0.5** (different ordering)
