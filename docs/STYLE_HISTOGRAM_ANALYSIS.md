# Style Histogram Analysis

## Summary

Analysis of style histograms across all batches in `test_batch_matching_laplata.csv`.

**Key Findings:**
- **Total batches**: 881
- **Unique style histograms**: 732
- **Average batches per style histogram**: 1.20
- **Most common style histogram**: 10 batches share `{'6 (6)': 11, '8 (8)': 14}`

## Distribution

Most style histograms are unique (appear in only 1 batch). The distribution shows:

- **1 batch per histogram**: 712 histograms (most common)
- **2 batches per histogram**: 15 histograms
- **3 batches per histogram**: 3 histograms
- **4 batches per histogram**: 1 histogram
- **5 batches per histogram**: 1 histogram
- **6 batches per histogram**: 0 histograms
- **7 batches per histogram**: 0 histograms
- **10 batches per histogram**: 1 histogram (most common style)

## Top 20 Most Common Style Histograms

1. **10 batches**: `{'6 (6)': 11, '8 (8)': 14}`
2. **7 batches**: `{'6 (6)': 13, '8 (8)': 12}`
3. **7 batches**: `{'6 (6)': 7, '8 (8)': 18}`
4. **6 batches**: `{'6 (6)': 10, '8 (8)': 15}`
5. **6 batches**: `{'6 (6)': 9, '8 (8)': 16}`
6. **6 batches**: `{'6 (6)': 8, '8 (8)': 17}`
7. **5 batches**: `{'11 (11)': 17, '12 (12)': 8}`
8. **4 batches**: `{'6 (6)': 6, '8 (8)': 19}`
9. **4 batches**: `{'6 (6)': 5, '8 (8)': 20}`
10. **4 batches**: `{'11 (11)': 16, '12 (12)': 9}`
11. **4 batches**: `{'11 (11)': 2, '6 (6)': 7, '8 (8)': 16}`
12. **4 batches**: `{'11 (11)': 1, '6 (6)': 9, '8 (8)': 15}`
13. **3 batches**: `{'Durango Fire Protection (Durango Fire Protection)': 13, 'Uper Pine River Fire Protection (Uper Pine River Fire Protection)': 12}`
14. **3 batches**: `{'6 (6)': 17, '8 (8)': 8}`
15. **3 batches**: `{'6 (6)': 16, '8 (8)': 9}`
16. **3 batches**: `{'5 (5)': 4, '6 (6)': 13, '8 (8)': 8}`
17. **3 batches**: `{'5 (5)': 2, '6 (6)': 12, '8 (8)': 11}`
18. **3 batches**: `{'5 (5)': 2, '6 (6)': 9, '8 (8)': 14}`
19. **3 batches**: `{'5 (5)': 1, '6 (6)': 14, '8 (8)': 10}`
20. **3 batches**: `{'5 (5)': 1, '6 (6)': 10, '8 (8)': 14}`

## Similar But Not Identical Style Histograms

Found 13,929 pairs of similar style histograms. Here are examples of the most similar:

### Example 1: 1 key difference, 2 total count difference
- **Histogram 1** (3 batches): `{'1 (1)': 1, '6 (6)': 8, '8 (8)': 16}`
- **Histogram 2** (1 batch): `{'1 (1)': 1, '6 (6)': 6, '8 (8)': 16}`
- **Difference**: `'6 (6)'` count differs by 2 (8 vs 6)
- **Example batches**: 103:1 vs 103:437

### Example 2: 2 key differences, 2 total count difference
- **Histogram 1** (5 batches): `{'11 (11)': 17, '12 (12)': 8}`
- **Histogram 2** (2 batches): `{'1 (1)': 1, '11 (11)': 17, '12 (12)': 7}`
- **Differences**: Added `'1 (1)'` with count 1, `'12 (12)'` count decreased by 1
- **Example batches**: 102:10 vs 103:250

### Example 3: 2 key differences, 2 total count difference
- **Histogram 1** (5 batches): `{'11 (11)': 17, '12 (12)': 8}`
- **Histogram 2** (1 batch): `{'11 (11)': 16, '12 (12)': 8, '8 (8)': 1}`
- **Differences**: `'11 (11)'` count decreased by 1, added `'8 (8)'` with count 1
- **Example batches**: 102:10 vs 103:285

### Example 4: 2 key differences, 2 total count difference
- **Histogram 1** (5 batches): `{'11 (11)': 17, '12 (12)': 8}`
- **Histogram 2** (4 batches): `{'11 (11)': 16, '12 (12)': 9}`
- **Differences**: `'11 (11)'` count decreased by 1, `'12 (12)'` count increased by 1
- **Example batches**: 102:10 vs 103:313

### Example 5: 2 key differences, 2 total count difference
- **Histogram 1** (1 batch): `{'11 (11)': 3, '6 (6)': 11, '8 (8)': 11}`
- **Histogram 2** (1 batch): `{'11 (11)': 2, '6 (6)': 12, '8 (8)': 11}`
- **Differences**: `'11 (11)'` count decreased by 1, `'6 (6)'` count increased by 1
- **Example batches**: 102:11 vs 103:220

## Observations

1. **High diversity**: 732 unique style histograms for 881 batches indicates high ballot style diversity
2. **Mostly unique**: 97% of style histograms appear in only 1 batch
3. **Common patterns**: The most common patterns involve styles `'6 (6)'` and `'8 (8)'` in various combinations
4. **Similar histograms**: Many histograms differ by only 1-2 ballot counts, suggesting batches with similar but not identical ballot style distributions

## Implications for Batch Matching

- **Quick elimination is effective**: Most batches are eliminated early due to different style histograms
- **Similar batches exist**: Many batches have similar style histograms that differ by only a few ballots
- **Style-based filtering**: To find potential matches, filter by batches with identical or very similar style histograms





