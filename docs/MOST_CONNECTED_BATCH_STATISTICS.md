# Most Connected Batch Statistics

## Summary

Analysis of batch comparisons within 2 style mismatches tolerance.

- **Total batches in CVR**: 881
- **Total pairs passing style check**: 11,459
- **Batches with comparisons**: 803
- **Most connected batch**: **103:26** with **98 comparisons**

## Batch 103:26 Statistics

### Overview

- **Total pairs analyzed**: 98
- **Same batch matches**: 0
- **Different batches**: 98

All pairs involving batch 103:26 are identified as different batches (no duplicates found).

### Match Score (Confidence)

| Metric | Value |
|--------|-------|
| Mean | 0.016603 |
| StdDev | 0.032797 |
| Min | 0.000000 |
| Max | 0.120000 |
| Median | 0.000000 |

**Interpretation**: Very low match scores overall, with median of 0.0, indicating these are all different batches.

### Match Rate

| Metric | Value |
|--------|-------|
| Mean | 0.445306 |
| StdDev | 0.076336 |
| Min | 0.120000 |
| Max | 0.560000 |
| Median | 0.440000 |

**Interpretation**: On average, about 44.5% of ballots match between batch 103:26 and other batches, with a range of 12% to 56%.

### Adjusted Match Rate (after penalty)

| Metric | Value |
|--------|-------|
| Mean | 0.016735 |
| StdDev | 0.032957 |
| Min | 0.000000 |
| Max | 0.120000 |
| Median | 0.000000 |

**Interpretation**: After applying penalty for unmatched ballots, the adjusted match rate drops significantly (mean 0.017), confirming these are different batches.

### Unmatched Ballots

| Metric | Value |
|--------|-------|
| Mean | 13.87 |
| StdDev | 1.91 |
| Min | 11 |
| Max | 22 |
| Median | 14.0 |

**Interpretation**: On average, about 14 out of 25 ballots (56%) are unmatched, indicating significant differences between batches.

### Penalty

| Metric | Value |
|--------|-------|
| Mean | 0.554694 |
| StdDev | 0.076336 |
| Min | 0.440000 |
| Max | 0.880000 |
| Median | 0.560000 |

**Interpretation**: The penalty (unmatched ballots / total ballots) averages 0.55, meaning on average 55% of ballots are unmatched.

### Mean Hamming Distance

| Metric | Value |
|--------|-------|
| Mean | 0.001095 |
| StdDev | 0.000925 |
| Min | 0.000000 |
| Max | 0.004025 |
| Median | 0.000852 |

**Interpretation**: Very low Hamming distances for matched ballots (mean 0.001), indicating that when ballots do match, they are very similar.

### Sketch Distance

| Metric | Value |
|--------|-------|
| Mean | 0.381880 |
| StdDev | 0.075162 |
| Min | 0.196464 |
| Max | 0.663827 |
| Median | 0.366620 |

**Interpretation**: Moderate to high sketch distances (mean 0.38), indicating different SimHash cluster distributions between batches.

### LCS Ratio

| Metric | Value |
|--------|-------|
| Mean | 0.291429 |
| StdDev | 0.058574 |
| Min | 0.080000 |
| Max | 0.440000 |
| Median | 0.280000 |

**Interpretation**: Low LCS ratios (mean 0.29), indicating different ballot ordering between batches.

## Top 5 Pairs (by Match Score)

1. **103:26 vs 103:564**
   - Match Score: 0.120000
   - Match Rate: 0.5600
   - Adjusted Rate: 0.1200
   - Unmatched: 11
   - Mean Hamming: 0.000000
   - Sketch Distance: 0.299751
   - LCS Ratio: 0.3200
   - Is Same Batch: False

2. **103:26 vs 103:195**
   - Match Score: 0.119797
   - Match Rate: 0.5600
   - Adjusted Rate: 0.1200
   - Unmatched: 11
   - Mean Hamming: 0.000406
   - Sketch Distance: 0.260911
   - LCS Ratio: 0.2800
   - Is Same Batch: False

3. **103:26 vs 103:588**
   - Match Score: 0.119797
   - Match Rate: 0.5600
   - Adjusted Rate: 0.1200
   - Unmatched: 11
   - Mean Hamming: 0.000406
   - Sketch Distance: 0.369804
   - LCS Ratio: 0.3200
   - Is Same Batch: False

4. **103:26 vs 103:749**
   - Match Score: 0.119797
   - Match Rate: 0.5600
   - Adjusted Rate: 0.1200
   - Unmatched: 11
   - Mean Hamming: 0.000406
   - Sketch Distance: 0.329677
   - LCS Ratio: 0.2400
   - Is Same Batch: False

5. **103:26 vs 103:23**
   - Match Score: 0.119493
   - Match Rate: 0.5600
   - Adjusted Rate: 0.1200
   - Unmatched: 11
   - Mean Hamming: 0.001015
   - Sketch Distance: 0.258827
   - LCS Ratio: 0.3200
   - Is Same Batch: False

## Bottom 5 Pairs (by Match Score)

94. **103:26 vs 103:79**
   - Match Score: 0.000000
   - Match Rate: 0.2800
   - Adjusted Rate: 0.0000
   - Unmatched: 18
   - Mean Hamming: 0.001623
   - Sketch Distance: 0.487025
   - LCS Ratio: 0.2000
   - Is Same Batch: False

95. **103:26 vs 103:8**
   - Match Score: 0.000000
   - Match Rate: 0.4400
   - Adjusted Rate: 0.0000
   - Unmatched: 14
   - Mean Hamming: 0.001808
   - Sketch Distance: 0.341366
   - LCS Ratio: 0.2800
   - Is Same Batch: False

96. **103:26 vs 103:818**
   - Match Score: 0.000000
   - Match Rate: 0.4400
   - Adjusted Rate: 0.0000
   - Unmatched: 14
   - Mean Hamming: 0.000000
   - Sketch Distance: 0.326509
   - LCS Ratio: 0.4000
   - Is Same Batch: False

97. **103:26 vs 103:838**
   - Match Score: 0.000000
   - Match Rate: 0.4800
   - Adjusted Rate: 0.0000
   - Unmatched: 13
   - Mean Hamming: 0.002131
   - Sketch Distance: 0.359883
   - LCS Ratio: 0.3600
   - Is Same Batch: False

98. **103:26 vs 103:846**
   - Match Score: 0.000000
   - Match Rate: 0.4000
   - Adjusted Rate: 0.0000
   - Unmatched: 15
   - Mean Hamming: 0.002273
   - Sketch Distance: 0.465936
   - LCS Ratio: 0.2800
   - Is Same Batch: False

## Key Observations

1. **No duplicates found**: All 98 pairs involving batch 103:26 are identified as different batches.

2. **Low match scores**: The highest match score is only 0.12, well below the threshold for identifying same batches.

3. **High unmatched rate**: On average, 14 out of 25 ballots (56%) are unmatched, indicating significant differences.

4. **Low Hamming distance for matched ballots**: When ballots do match, they are very similar (mean Hamming distance 0.001), suggesting the matching algorithm is working correctly.

5. **Moderate sketch distances**: Sketch distances (mean 0.38) indicate different SimHash cluster distributions, consistent with different batches.

6. **Low LCS ratios**: LCS ratios (mean 0.29) indicate different ballot ordering, which is expected for different batches.

## Conclusion

Batch 103:26 is the most connected batch (98 comparisons) within the 2 style mismatch tolerance, but all comparisons indicate it is different from all other batches. The statistics show consistent patterns of low match scores, high unmatched ballot rates, and different ballot ordering, confirming these are all distinct batches.
