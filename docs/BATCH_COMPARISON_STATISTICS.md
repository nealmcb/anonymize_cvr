# Batch Comparison Statistics

## Statistics: Batch 103:1 vs All Other Batches

**Data source**: `test_batch_matching_laplata.csv`  
**Total batches**: 881  
**Batches compared**: 2 (most eliminated due to different styles/cardinality)

### Summary

Most batch comparisons are eliminated at the quick elimination stage because batches typically have different ballot styles, cardinalities, or contest schemas. Only batches that pass these initial checks proceed to full comparison.

**Elimination breakdown** (sample of first 20 comparisons):
- Different styles: 20/20 (100%)

### Statistics for Non-Eliminated Comparisons

#### Match Score
- **Mean**: 0.850000
- **StdDev**: 0.212132
- **Min**: 0.700000
- **Max**: 1.000000

#### Match Rate
- **Mean**: 0.960000
- **StdDev**: 0.056569
- **Min**: 0.920000
- **Max**: 1.000000

#### Mean Hamming Distance
- **Mean**: 0.000000
- **StdDev**: 0.000000
- **Min**: 0.000000
- **Max**: 0.000000

#### Sketch Distance
- **Mean**: 0.024902
- **StdDev**: 0.035217
- **Min**: 0.000000
- **Max**: 0.049804

#### LCS Ratio
- **Mean**: 0.700000
- **StdDev**: 0.424264
- **Min**: 0.400000
- **Max**: 1.000000

### Top Results

1. **103:435** - Score: 1.000000 (exact duplicate)
   - Match Rate: 1.0000
   - Mean Hamming: 0.000000
   - Sketch Distance: 0.000000
   - LCS Ratio: 1.0000
   - Same Batch: True

2. **103:436** - Score: 0.700000 (modified ballots)
   - Match Rate: 0.9200
   - Mean Hamming: 0.000000
   - Sketch Distance: 0.049804
   - LCS Ratio: 0.4000
   - Same Batch: True

### Notes

- **Limited sample size**: Only 2 comparisons passed elimination checks, as most batches have different styles
- **Style-based filtering**: To get more meaningful statistics, compare batches with the same ballot style
- **Test cases**: The two matches are intentional test cases (exact duplicate and modified ballots)

### Recommendations for Better Statistics

1. **Filter by style**: Compare only batches with identical style histograms
2. **Filter by cardinality**: Compare only batches with the same number of ballots
3. **Create more test cases**: Add more batches with known relationships (duplicates, modifications, etc.)
4. **Compare within precincts**: Batches from the same precinct are more likely to have similar characteristics





