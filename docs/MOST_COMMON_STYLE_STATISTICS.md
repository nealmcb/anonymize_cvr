# Statistics: Most Common Style Histogram

## Style Histogram

**Style Histogram**: `{'6 (6)': 11, '8 (8)': 14}`  
**Number of batches**: 10  
**Total pairs compared**: 45 (all pairs, none eliminated)

### Batches

1. 103:139
2. 103:2
3. 103:288
4. 103:338
5. 103:499
6. 103:539
7. 103:585
8. 103:604
9. 103:617
10. 103:660

## Statistics Across All 45 Pairs

### Match Score

- **Mean**: 0.476842
- **StdDev**: 0.084992
- **Min**: 0.319645
- **Max**: 0.640000
- **Median**: 0.478106

**Interpretation**: Match scores range from 0.32 to 0.64, with a mean of 0.48. All pairs are below the 0.70 threshold for "same batch" classification, indicating these are different batches with similar style distributions.

### Match Rate

- **Mean**: 0.477333
- **StdDev**: 0.085024
- **Min**: 0.320000
- **Max**: 0.640000
- **Median**: 0.480000

**Interpretation**: On average, 48% of ballots can be matched between batches. This suggests significant overlap in ballot patterns but not enough to indicate the same physical batch.

### Mean Hamming Distance

- **Mean**: 0.000982
- **StdDev**: 0.001358
- **Min**: 0.000000
- **Max**: 0.004261
- **Median**: 0.000406

**Interpretation**: Very low Hamming distances (mean < 0.001) indicate that matched ballots are nearly identical. This suggests that when ballots do match, they match very closely, but many ballots don't match at all.

### Sketch Distance

- **Mean**: 0.334557
- **StdDev**: 0.080318
- **Min**: 0.192010
- **Max**: 0.481439
- **Median**: 0.338714

**Interpretation**: Sketch distances are moderate to high (0.19-0.48), indicating different SimHash cluster distributions. This suggests the batches have different ballot similarity patterns despite sharing the same style histogram.

### LCS Ratio

- **Mean**: 0.347556
- **StdDev**: 0.061391
- **Min**: 0.200000
- **Max**: 0.480000
- **Median**: 0.360000

**Interpretation**: LCS ratios are relatively low (0.20-0.48), indicating ballots are in different orders. This is expected for different physical batches.

## Top 10 Highest Match Scores

1. **103:139 vs 103:499** - Score: 0.640000
   - Match Rate: 0.6400
   - Mean Hamming: 0.000000
   - Sketch Distance: 0.235051
   - LCS Ratio: 0.3600

2. **103:288 vs 103:604** - Score: 0.638846
   - Match Rate: 0.6400
   - Mean Hamming: 0.002308
   - Sketch Distance: 0.288131
   - LCS Ratio: 0.3600

3. **103:139 vs 103:2** - Score: 0.600000
   - Match Rate: 0.6000
   - Mean Hamming: 0.000000
   - Sketch Distance: 0.279973
   - LCS Ratio: 0.4800

4. **103:288 vs 103:499** - Score: 0.600000
   - Match Rate: 0.6000
   - Mean Hamming: 0.000000
   - Sketch Distance: 0.242920
   - LCS Ratio: 0.4000

5. **103:2 vs 103:338** - Score: 0.599811
   - Match Rate: 0.6000
   - Mean Hamming: 0.000379
   - Sketch Distance: 0.303790
   - LCS Ratio: 0.4400

6. **103:139 vs 103:617** - Score: 0.599621
   - Match Rate: 0.6000
   - Mean Hamming: 0.000758
   - Sketch Distance: 0.234211
   - LCS Ratio: 0.3600

7. **103:499 vs 103:617** - Score: 0.599621
   - Match Rate: 0.6000
   - Mean Hamming: 0.000758
   - Sketch Distance: 0.192786
   - LCS Ratio: 0.4000

8. **103:2 vs 103:499** - Score: 0.560000
   - Match Rate: 0.5600
   - Mean Hamming: 0.000000
   - Sketch Distance: 0.306435
   - LCS Ratio: 0.4400

9. **103:139 vs 103:604** - Score: 0.559797
   - Match Rate: 0.5600
   - Mean Hamming: 0.000406
   - Sketch Distance: 0.313546
   - LCS Ratio: 0.3600

10. **103:2 vs 103:617** - Score: 0.559797
    - Match Rate: 0.5600
    - Mean Hamming: 0.000406
    - Sketch Distance: 0.208992
    - LCS Ratio: 0.4400

## Bottom 10 Lowest Match Scores

1. **103:338 vs 103:604** - Score: 0.319645
   - Match Rate: 0.3200
   - Mean Hamming: 0.000710
   - Sketch Distance: 0.481439
   - LCS Ratio: 0.2000

2. **103:585 vs 103:660** - Score: 0.359369
   - Match Rate: 0.3600
   - Mean Hamming: 0.001263
   - Sketch Distance: 0.398461
   - LCS Ratio: 0.3200

3. **103:338 vs 103:617** - Score: 0.359684
   - Match Rate: 0.3600
   - Mean Hamming: 0.000631
   - Sketch Distance: 0.386772
   - LCS Ratio: 0.3200

4. **103:288 vs 103:585** - Score: 0.360000
   - Match Rate: 0.3600
   - Mean Hamming: 0.000000
   - Sketch Distance: 0.449429
   - LCS Ratio: 0.3600

5. **103:539 vs 103:604** - Score: 0.360000
   - Match Rate: 0.3600
   - Mean Hamming: 0.000000
   - Sketch Distance: 0.408324
   - LCS Ratio: 0.2800

6. **103:585 vs 103:617** - Score: 0.360000
   - Match Rate: 0.3600
   - Mean Hamming: 0.000000
   - Sketch Distance: 0.326130
   - LCS Ratio: 0.3200

7. **103:604 vs 103:660** - Score: 0.398011
   - Match Rate: 0.4000
   - Mean Hamming: 0.003977
   - Sketch Distance: 0.364735
   - LCS Ratio: 0.2400

8. **103:539 vs 103:660** - Score: 0.398295
   - Match Rate: 0.4000
   - Mean Hamming: 0.003409
   - Sketch Distance: 0.436846
   - LCS Ratio: 0.2400

9. **103:338 vs 103:539** - Score: 0.399716
   - Match Rate: 0.4000
   - Mean Hamming: 0.000568
   - Sketch Distance: 0.451106
   - LCS Ratio: 0.2800

10. **103:288 vs 103:338** - Score: 0.400000
    - Match Rate: 0.4000
    - Mean Hamming: 0.000000
    - Sketch Distance: 0.335903
    - LCS Ratio: 0.3600

## Key Observations

1. **No exact matches**: All match scores are below 0.70, confirming these are different physical batches
2. **Moderate similarity**: Mean match score of 0.48 indicates significant but not overwhelming similarity
3. **Low Hamming distances**: When ballots match, they match very closely (mean < 0.001)
4. **High sketch distances**: Different SimHash cluster distributions (mean 0.33) indicate different ballot similarity patterns
5. **Low LCS ratios**: Different ballot ordering (mean 0.35) confirms different physical batches
6. **Match rate correlates with score**: Match rate and match score are nearly identical, as expected from the scoring formula

## Implications

- **Style histogram alone is not sufficient**: Batches with identical style histograms can still be very different
- **Match scores provide good discrimination**: Scores range from 0.32 to 0.64, providing clear separation
- **Multiple metrics needed**: Sketch distance and LCS ratio provide additional evidence beyond match rate
- **Threshold validation**: The 0.70 threshold for "same batch" correctly excludes all these pairs





