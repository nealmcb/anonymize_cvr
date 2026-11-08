# Batch Matching Implementation Plan

## Overview

Implement a robust check to determine if any two batches of ballots for a given county came from the same physical batch, based on Dominion Cast Vote Records (CVR) files.

## Important Notes on Data Format

**Parquet Files in `2020-cvrs/`**: The parquet files in the `2020-cvrs/` directory do **NOT** contain batch information. These files have columns like `cvr_id`, `precinct_medsl`, `precinct_cvr`, `office`, `district`, `candidate`, `magnitude`, `party`, `party_detailed` but no `TabulatorNum` or `BatchId` columns.

**Dominion CVR CSV Format**: This implementation works with Dominion CVR files in **CSV format** which include:
- `TabulatorNum` (column 1): Tabulator/scanner identifier
- `BatchId` (column 2): Batch identifier
- These columns are present in the standard Dominion CVR CSV export format

**If you need to work with parquet files**: Batch information would need to come from a separate source (e.g., a manifest file or database) and matched to ballots using `cvr_id` or another identifier.

## Goal

Given two batches (identified by `(tabulator_id, batch_number)`), determine if they contain the same physical ballots with high confidence, accounting for minor scanner variation.

## Summary

This implementation will:

1. **Extract ballot data** from Dominion CVR files (CSV format) for each batch, aggregating all contest choices per ballot
2. **Compute per-ballot fingerprints** using:
   - Strict hash (SHA-256) for exact matching
   - SimHash (fuzzy hash) for near-duplicate detection
3. **Build batch signatures** including:
   - Cardinality (ballot count)
   - Style histogram
   - Strict hash multiset
   - SimHash cluster histogram
   - Contest schema (set of contests present)
4. **Compare batches** using a multi-stage approach:
   - Quick elimination (different cardinality, styles, or contests)
   - Strict hash multiset match
   - Fuzzy matching with Hamming distance
   - Sketch consistency check (SimHash clusters)
   - Longest Common Subsequence (LCS) analysis
5. **Provide CLI interface** for batch comparison and batch pair analysis

## Data Sources

**Dominion CVR Files (CSV format)**:
- Format: CSV files with 4 header rows followed by ballot data rows
- Header structure:
  - Row 1: Version/Election name
  - Row 2: Contest names (repeated for each candidate choice)
  - Row 3: Candidate/choice names
  - Row 4: Column headers
- Ballot row columns (first 8 are header columns, then vote columns):
  - `CvrNumber` (column 0): Unique ballot identifier
  - `TabulatorNum` (column 1): Tabulator/scanner identifier
  - `BatchId` (column 2): Batch identifier
  - `RecordId` (column 3): Record identifier
  - `ImprintedId` (column 4): Imprinted ID (often format `tabulator-batch-position`)
  - `CountingGroup` (column 5): Counting group (e.g., vote method)
  - `PrecinctPortion` (column 6): Precinct portion/style identifier
  - `BallotType` (column 7): Ballot type/style
  - Vote columns (column 8+): One column per candidate/choice, values are "1" (voted), "0" (not voted), or "" (contest not on ballot)SInc
- Ballots are uniquely identified by `CvrNumber` or `ImprintedId`

**Note**: The parquet files in `2020-cvrs/` do not contain batch information. This implementation works with Dominion CVR files in CSV format which include `TabulatorNum` and `BatchId` columns.

## Key Design Decisions

1. **Bitstring Representation**: 
   - Sort contests by contest name (from row 2 of CVR) for deterministic ordering
   - For each contest, sort candidate/choice names (from row 3 of CVR)
   - Serialize each contest's vote choices as UTF-8 bytes
   - For each candidate column: "1" if voted, "0" if not voted, "" if contest not on ballot
   - Separate contests with a delimiter (e.g., `\x00`)
   - Handle empty strings (undervotes) consistently

2. **Using CVR Vote Data**:
   - Use vote columns directly from CVR (values "1", "0", or "")
   - CVR represents the machine-readable interpretation of the ballot
   - This allows matching even when there are minor scanner variations

3. **Ballot Style Handling**:
   - Different styles may have different contest sets
   - Batch comparison should only compare ballots with same style (or normalize contest sets)
   - Use `PrecinctPortion` or `BallotType` to identify styles

4. **CVR File Format**:
   - Support CSV format directly (no database required)
   - Handle both individual CVR files and aggregated CVR files
   - For aggregated rows (CvrNumber starts with "AGGREGATED-"), skip or handle specially

## Implementation Phases

### Phase 1: Data Extraction and Ballot Fingerprinting

#### 1.1 Extract ballot data for a batch
- Function: `extract_batch_ballots(cvr_file: str, tabulator_id: str, batch_id: str) -> List[BallotRecord]`
- Read CVR file (CSV format) using existing `TempCVRFile` utility if needed
- Filter rows where `TabulatorNum == tabulator_id` and `BatchId == batch_id`
- Skip aggregated rows (CvrNumber starts with "AGGREGATED-")
- For each ballot row:
  - Extract header fields: `CvrNumber`, `ImprintedId`, `PrecinctPortion`, `BallotType`
  - Extract all vote columns (starting at column 8)
  - Map vote columns to contests and candidates using header rows
- Store: `CvrNumber`, `ImprintedId`, `PrecinctPortion`, `BallotType`, all vote choices

#### 1.2 Build ballot bitstring
- Function: `build_ballot_bitstring(ballot_row: List[str], contests: List[str], choices: List[str], headerlen: int = 8) -> bytes`
- Use contest names (row 2) and candidate names (row 3) from CVR header
- Create deterministic bitstring:
  - Sort contests by contest name
  - For each contest:
    - Sort candidate/choice names for that contest
    - For each candidate: serialize vote value ("1", "0", or "")
    - Concatenate candidate votes for the contest
  - Separate contests with delimiter (e.g., `\x00`)
  - Handle multi-value choices (vote-for-n contests) - multiple "1" values allowed
  - Handle undervotes (empty string) consistently
  - Result: deterministic byte sequence representing all votes

#### 1.3 Compute per-ballot fingerprints
- Function: `compute_ballot_fingerprints(bitstring: bytes) -> Tuple[str, int]`
- **Strict hash (H0)**: `sha256(bitstring).hexdigest()` or faster hash
- **Fuzzy hash (SimHash)**: Use SimHash algorithm (64-bit or 128-bit)
  - Convert bitstring to features (e.g., 8-byte chunks)
  - Compute SimHash signature
  - Alternative: Use MinHash if SimHash library unavailable

### Phase 2: Batch Signature Computation

#### 2.1 Create BatchSignature dataclass
```python
@dataclass
class BatchSignature:
    tabulator_id: str
    batch_id: str
    cardinality: int  # Number of ballots
    style_histogram: Dict[str, int]  # Count per PrecinctPortion/BallotType
    strict_hash_multiset: Counter[str]  # H0 values
    cluster_histogram: Dict[int, int]  # SimHash bucket -> count
    contest_schema: Set[str]  # Set of contest names present
    ballots: List[BallotFingerprint]  # Per-ballot data for matching
```

#### 2.2 Compute batch signature
- Function: `compute_batch_signature(cvr_file: str, tabulator_id: str, batch_id: str) -> BatchSignature`
- Read CVR file and extract all ballots in batch
- For each ballot:
  - Build bitstring using contest and choice data
  - Compute H0 and SimHash
  - Store: `BallotFingerprint(cvr_number, imprinted_id, style_id, h0, simhash, bitstring)`
- Aggregate statistics:
  - Count ballots
  - Count per style_id (using `PrecinctPortion` or `BallotType`)
  - Collect all H0 values (multiset)
  - Bucket SimHash values (use high k bits for clustering)
  - Collect all contest names (from CVR header)

### Phase 3: Comparison Logic

#### 3.1 Quick elimination checks
- Function: `quick_eliminate(sig_a: BatchSignature, sig_b: BatchSignature) -> Optional[str]`
- Check cardinality: if `|A| != |B|` → return "different_cardinality"
- Check style histogram: if `style_histogram_A != style_histogram_B` → return "different_styles"
- Check contest schema: if `contest_schema_A != contest_schema_B` → return "different_contests"
- Return `None` if cannot eliminate

#### 3.2 Strict set match
- Function: `strict_match(sig_a: BatchSignature, sig_b: BatchSignature) -> bool`
- Compare multiset(H0_A) == multiset(H0_B)
- If match → return `True` (virtually certain same physical batch)
- If no match → return `False` (continue to fuzzy matching)

#### 3.3 Fuzzy set match
- Function: `fuzzy_match(sig_a: BatchSignature, sig_b: BatchSignature) -> Tuple[bool, float, float]`
- Greedy bipartite matching:
  - For each ballot in A, find closest match in B by SimHash distance
  - Then verify with Hamming distance on bitstrings
  - Compute metrics:
    - Match rate: `matched_count / |A|`
    - Mean Hamming distance: average over all matches
- Heuristic threshold:
  - `match_rate >= 0.98 AND mean_hamming <= 0.3` → return `(True, match_rate, mean_hamming)`
  - Otherwise → return `(False, match_rate, mean_hamming)`

#### 3.4 Sketch consistency check
- Function: `sketch_consistency(sig_a: BatchSignature, sig_b: BatchSignature) -> float`
- Compare cluster histograms (SimHash buckets)
- Compute χ² distance or Jensen-Shannon divergence
- Return distance metric (lower = more similar)

#### 3.5 Longest Common Subsequence (LCS)
- Function: `compute_lcs(sig_a: BatchSignature, sig_b: BatchSignature) -> int`
- After fuzzy matching, extract matched ballot sequences
- Compute LCS length between sequences
- Higher LCS relative to batch size supports same-batch hypothesis

### Phase 4: Main Comparison Function

#### 4.1 Compare two batches
- Function: `compare_batches(cvr_file: str, tabulator_a: str, batch_a: str, tabulator_b: str, batch_b: str) -> BatchComparisonResult`

```python
@dataclass
class BatchComparisonResult:
    batch_a: Tuple[str, str]  # (tabulator, batch)
    batch_b: Tuple[str, str]
    is_same_batch: bool
    confidence: float  # 0.0 to 1.0
    match_type: str  # "strict", "fuzzy", "none"
    elimination_reason: Optional[str]
    cardinality_match: bool
    style_histogram_match: bool
    contest_schema_match: bool
    strict_hash_match: bool
    fuzzy_match_rate: Optional[float]
    mean_hamming_distance: Optional[float]
    sketch_distance: Optional[float]
    lcs_length: Optional[int]
    lcs_ratio: Optional[float]  # lcs_length / min(|A|, |B|)
```

### Phase 5: SimHash Implementation

#### 5.1 SimHash algorithm
- Function: `simhash(bitstring: bytes, hash_bits: int = 64) -> int`
- Algorithm (implement from scratch):
  1. Split bitstring into features:
     - Use sliding windows (e.g., 8-byte windows with 4-byte stride)
     - Or split by natural boundaries (e.g., per-contest segments)
  2. For each feature, compute hash using SHA-256 truncated to hash_bits
  3. Create vector of hash_bits length, initialized to zeros
  4. For each hash:
     - For each bit position i:
       - If hash bit i is 1: increment vector[i]
       - If hash bit i is 0: decrement vector[i]
  5. Convert final vector to integer:
     - For each position i: if vector[i] > 0, set bit i to 1, else 0
- Return: 64-bit integer (or larger if hash_bits > 64)

#### 5.2 Hamming distance
- Function: `hamming_distance(bitstring_a: bytes, bitstring_b: bytes) -> int`
- Count differing bits between two bitstrings
- Ensure bitstrings are same length (pad with zeros if needed)
- Use XOR and count set bits: `bin(a ^ b).count('1')` for integers

### Phase 6: Utility Functions

#### 6.1 Batch discovery
- Function: `find_batches_in_cvr(cvr_file: str) -> List[Tuple[str, str]]`
- Read CVR file and extract all unique `(TabulatorNum, BatchId)` pairs
- Filter out aggregated rows (CvrNumber starts with "AGGREGATED-")
- Return list of `(tabulator_id, batch_id)` pairs

#### 6.2 Batch comparison CLI
- Command: `compare-batches` (using Typer)
- Options:
  - `--cvr-file PATH`: Path to CVR file (CSV format)
  - `--batch-a T:B`: First batch (tabulator:batch)
  - `--batch-b T:B`: Second batch (tabulator:batch)
  - `--all-pairs`: Compare all batch pairs in CVR file
  - `--output-format`: JSON or text (default: text)
- Output: JSON or formatted text

## Data Structures

### BallotFingerprint
```python
@dataclass
class BallotFingerprint:
    cvr_number: str  # CvrNumber from CVR
    imprinted_id: str  # ImprintedId from CVR
    style_id: str  # PrecinctPortion or BallotType
    h0: str  # Strict hash (hex)
    simhash: int  # Fuzzy hash
    bitstring: bytes  # Original bitstring for Hamming distance
    sequence_index: Optional[int]  # Position within batch (from RecordId or ImprintedId)
```

### BatchSignature
```python
@dataclass
class BatchSignature:
    tabulator_id: str
    batch_id: str
    cardinality: int
    style_histogram: Dict[str, int]
    strict_hash_multiset: Counter[str]
    cluster_histogram: Dict[int, int]  # SimHash bucket (high bits) -> count
    contest_schema: Set[str]  # Contest names
    ballots: List[BallotFingerprint]
```

## Testing Strategy

1. **Unit tests**:
   - Bitstring generation (deterministic across runs)
   - SimHash computation
   - Hamming distance calculation
   - Quick elimination logic

2. **Integration tests**:
   - Extract batch signatures from CVR files
   - Compare known matching batches
   - Compare known non-matching batches

3. **Edge cases**:
   - Empty batches
   - Single ballot batches
   - Batches with all undervotes
   - Batches with different contest sets

## Dependencies

- Standard library: 
  - `hashlib` (SHA-256 for hashing)
  - `collections.Counter` (for multisets)
  - `itertools` (for combinations, permutations)
  - `dataclasses` (for data structures)
  - `typing` (for type hints)
  - `csv` (for reading CVR files)
- Existing: `cvr_utils.TempCVRFile` (for handling Parquet conversion if needed)
- **No external dependencies required** - SimHash will be implemented from scratch

## File Structure

```
src/anonymize_cvr/
  ├── batch_matching.py          # Main module
  ├── simhash.py                 # SimHash implementation
  └── fingerprint_utils.py       # Bitstring and hash utilities
```

## CLI Command

```bash
uv run anonymize-cvr compare-batches \
  --cvr-file "path/to/cvr.csv" \
  --batch-a "102:11" \
  --batch-b "102:12"
```

## Output Format

```json
{
  "batch_a": {"tabulator": "102", "batch": "11"},
  "batch_b": {"tabulator": "102", "batch": "12"},
  "is_same_batch": false,
  "confidence": 0.0,
  "elimination_reason": "different_cardinality",
  "metrics": {
    "cardinality_a": 50,
    "cardinality_b": 47,
    "style_histogram_match": true,
    "contest_schema_match": true
  }
}
```

## Performance Considerations

- Batch signatures can be cached/computed once per batch
- SimHash computation is O(n) where n = ballot count
- Fuzzy matching is O(n²) but can be optimized with approximate nearest neighbor
- For large batches, consider sampling approach
- CVR files can be large - consider streaming or chunked processing for very large files
- Use existing `TempCVRFile` utility to handle Parquet conversion transparently

## Potential Challenges

1. **Missing ballot data**: Not all ballots in a batch may be present in CVR file
   - Solution: Only compare ballots present in both batches

2. **Different contest sets**: Batches may have different contests (different ballot styles)
   - Solution: Compare only common contests, or use contest schema check

3. **Ballot ordering**: Physical order may differ between batches
   - Solution: Use LCS and fuzzy matching rather than strict sequence matching

4. **Scanner variation**: Minor mark detection differences
   - Solution: Fuzzy matching with Hamming distance threshold

5. **Undervotes**: Empty choices need consistent serialization
   - Solution: Use canonical empty string representation

6. **Multi-value choices**: Vote-for-n contests have multiple selections
   - Solution: Sort selections before serialization for consistency

7. **Aggregated rows**: CVR files may contain aggregated rows (CvrNumber starts with "AGGREGATED-")
   - Solution: Skip aggregated rows when extracting batch ballots

8. **Parquet format**: The parquet files in `2020-cvrs/` don't contain batch information
   - Solution: Work with CSV format CVR files that include `TabulatorNum` and `BatchId` columns
   - Note: If parquet files need to be used, batch information would need to come from another source

## Implementation Order

Recommended order of implementation:

1. **Phase 1**: Core utilities
   - CVR file reading and parsing
   - Bitstring building from CVR ballot rows
   - Strict hash computation (SHA-256)
   - Hamming distance calculation

2. **Phase 2**: SimHash implementation
   - Implement SimHash algorithm from scratch
   - Test with known similar/different ballots

3. **Phase 3**: Batch signature computation
   - Extract batch ballots from CVR files
   - Build batch signatures
   - Test with known batches

4. **Phase 4**: Comparison logic
   - Quick elimination checks
   - Strict hash matching
   - Fuzzy matching
   - Sketch consistency

5. **Phase 5**: LCS and main comparison function
   - Implement LCS algorithm
   - Combine all checks into main comparison function
   - Test with real batch pairs

6. **Phase 6**: CLI interface
   - Create Typer command
   - Add output formatting
   - Documentation


## Future Enhancements

1. Cache batch signatures to avoid recomputation
2. Build index of batch signatures for fast lookup
3. Support for comparing batches across multiple CVR files
4. Visualization of batch similarity matrix
5. Automated duplicate batch detection across entire dataset
6. Support for batch information extraction from other sources if parquet files need to be used

