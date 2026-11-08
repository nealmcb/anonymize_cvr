# Style Histogram Relaxation Analysis

## Current Behavior: Different Styles

### How Bitstring Comparison Works with Different Styles

When comparing ballots with different styles:

1. **Bitstring Encoding**:
   - All ballots use the same contest schema (from CVR header)
   - For each contest, vote values are: "1" (voted), "0" (not voted), or "" (contest not on ballot)
   - Ballots with different styles will have different patterns of "" values
   - The bitstring includes ALL contests, with "" marking contests not on that ballot's style

2. **Hamming Distance**:
   - Includes differences from missing contests ("" vs "0" or "1")
   - Example: If ballot A has contest X (vote "1") and ballot B doesn't have contest X (""), this contributes to Hamming distance
   - Normalized by total bitstring length, so missing contests add to the distance

3. **SimHash**:
   - Reflects the overall pattern of contests and votes
   - Different styles produce different SimHash values due to different "" patterns
   - SimHash distance will be higher for ballots with different styles

4. **Fuzzy Matching**:
   - Still works, but match rate will be lower
   - Ballots with very different styles may not match (SimHash distance > 8 or Hamming > 0.3)
   - Only ballots that pass both thresholds are considered matched

### Example: Batch 103:1 vs 103:139

**Batch 103:1**: `{'6 (6)': 8, '1 (1)': 1, '8 (8)': 16}`
**Batch 103:139**: `{'8 (8)': 14, '6 (6)': 11}`

**Results** (with style check disabled):
- **Match rate**: 0.4400 (11/25 matched)
- **Mean Hamming**: 0.000517 (very low - only matched ballots included)
- **Sketch distance**: 0.463073 (high - different cluster distributions)
- **LCS ratio**: 0.2800 (low - different ordering)
- **Contest schema**: Same (both have same 14 contests)

**Interpretation**:
- Only 44% of ballots matched, indicating significant style differences
- Matched ballots are very similar (Hamming ≈ 0), but many ballots couldn't be matched
- High sketch distance confirms different ballot similarity patterns
- Low LCS ratio confirms different physical batches

## Penalty for Unmatched Ballots

### Current Problem

The mean Hamming distance is calculated only over matched pairs, creating selection bias:
- If 23/25 ballots match perfectly (Hamming = 0), mean Hamming = 0.0
- But 2 ballots are unmatched and excluded from the calculation
- This is misleading - the metric doesn't reflect the full batch comparison

### Proposed Solution: Penalty for Unmatched Ballots

**Allow up to 2 unmatched ballots without penalty, then penalize excess unmatched ballots.**

**Formula**:
```
unmatched_count = total_ballots - matched_count
excess_unmatched = max(0, unmatched_count - 2)
penalty = excess_unmatched / total_ballots
adjusted_match_rate = match_rate - penalty
```

**Examples** (for 25-ballot batches):

| Matched | Unmatched | Match Rate | Excess | Penalty | Adjusted Rate |
|---------|-----------|------------|--------|---------|---------------|
| 25      | 0         | 1.0000     | 0      | 0.0000  | 1.0000        |
| 24      | 1         | 0.9600     | 0      | 0.0000  | 0.9600        |
| 23      | 2         | 0.9200     | 0      | 0.0000  | 0.9200        |
| 22      | 3         | 0.8800     | 1      | 0.0400  | 0.8400        |
| 20      | 5         | 0.8000     | 3      | 0.1200  | 0.6800        |
| 15      | 10        | 0.6000     | 8      | 0.3200  | 0.2800        |

### Implications

1. **Threshold adjustment**: With penalty, a match rate of 0.92 (23/25) would have adjusted rate of 0.92, but 0.88 (22/25) would drop to 0.84
2. **Clearer interpretation**: Adjusted rate reflects both match quality and coverage
3. **Tolerance for minor differences**: Allows up to 2 unmatched ballots (8% for 25-ballot batches) without penalty

## Relaxing Style Histogram Requirement

### Current Quick Elimination

The `quick_eliminate` function currently eliminates batches if:
- Different cardinality
- **Different style histogram** ← This is what we want to relax
- Different contest schema

### Proposed Change

**Option 1: Remove style histogram check entirely**
- Pros: Simplest, allows all comparisons
- Cons: May compare batches that are clearly different (e.g., all style "1" vs all style "8")

**Option 2: Relax style histogram check**
- Allow style histograms that differ by ≤ 2 ballots
- Example: `{'6 (6)': 8, '8 (8)': 17}` vs `{'6 (6)': 10, '8 (8)': 15}` (2 ballot difference)
- Pros: Still filters obviously different batches
- Cons: More complex logic

**Option 3: Make style histogram check a warning, not elimination**
- Allow comparison but flag style differences
- Use style difference as a factor in final confidence score
- Pros: Most flexible, preserves information
- Cons: More complex scoring

### Impact on Metrics

When comparing batches with different styles:

1. **Match Rate**: Will be lower because ballots with different styles are less likely to match
   - Example: 0.44 (11/25) instead of 0.64+ for same-style batches

2. **Mean Hamming Distance**: 
   - Still calculated only over matched pairs
   - May be low if matched ballots are similar, but many unmatched
   - **This is why we need the penalty**

3. **Sketch Distance**: 
   - Will be higher (different SimHash cluster distributions)
   - Example: 0.463 vs 0.235 for same-style batches

4. **LCS Ratio**: 
   - Will be lower (different ballot ordering)
   - Example: 0.28 vs 0.36 for same-style batches

5. **Contest Schema**: 
   - Should still match (both batches have same contests available)
   - If contest schemas differ, batches are truly different

## Real-World Example Comparison

### Different Styles: Batch 103:1 vs 103:139

**Batch 1**: `{'6 (6)': 8, '1 (1)': 1, '8 (8)': 16}`
**Batch 139**: `{'8 (8)': 14, '6 (6)': 11}`

**Results**:
- Match rate: **0.4400** (11/25 matched, 14 unmatched)
- Mean Hamming: **0.000517** (very low - only matched ballots)
- Sketch distance: **0.463073** (high - different cluster distributions)
- LCS ratio: **0.2800** (low - different ordering)

**With penalty** (allowing up to 2 unmatched):
- Unmatched: 14
- Excess: 12
- Penalty: 0.4800
- Adjusted match rate: **-0.0400** (negative - indicates very poor match)

### Same Styles: Batch 103:139 vs 103:499

**Both batches**: `{'8 (8)': 14, '6 (6)': 11}`

**Results**:
- Match rate: **0.6400** (16/25 matched, 9 unmatched)
- Mean Hamming: **0.000000** (perfect matches)
- Sketch distance: **0.235051** (moderate - similar clusters)
- LCS ratio: **0.3600** (moderate - some ordering similarity)

**With penalty**:
- Unmatched: 9
- Excess: 7
- Penalty: 0.2800
- Adjusted match rate: **0.3600** (still positive, but reduced)

### Key Observations

1. **Different styles reduce match rate**: 0.44 vs 0.64 (31% reduction)
2. **Different styles increase sketch distance**: 0.463 vs 0.235 (97% increase)
3. **Different styles reduce LCS ratio**: 0.28 vs 0.36 (22% reduction)
4. **Mean Hamming is misleading**: Both show very low values, but match rates differ significantly

## Recommendations

1. **Relax style histogram check**: Remove it from quick elimination, or make it a soft check
2. **Add penalty for unmatched ballots**: Implement the 2-ballot tolerance with penalty
3. **Update match score calculation**: Incorporate adjusted match rate and style difference
4. **Document style differences**: Report style histogram differences in comparison results
5. **Clamp adjusted rate**: Don't allow negative values - use `max(0.0, adjusted_rate)` or treat as 0.0

### Updated Match Score Formula (Proposed)

```
if strict_match:
    score = 1.0
else:
    unmatched = total - matched
    excess = max(0, unmatched - 2)
    penalty = excess / total
    adjusted_rate = match_rate - penalty
    
    if adjusted_rate > 0.9 and mean_hamming < 0.1 and sketch_dist < 0.2:
        score = 0.95
    elif adjusted_rate > 0.9 and mean_hamming < 0.5:
        score = 0.85
    elif adjusted_rate > 0.85 and mean_hamming < 0.5:
        score = 0.70
    else:
        score = max(0.0, adjusted_rate - (mean_hamming * 0.5))
```

This formula:
- Accounts for unmatched ballots via penalty
- Still considers Hamming distance and sketch distance
- Provides clear thresholds for different confidence levels

