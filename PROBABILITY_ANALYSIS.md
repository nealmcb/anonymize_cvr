# Ballot Guessing Probability Analysis

This document describes how anonymization affects the probability of correctly guessing a voter's ballot choices in the CVR anonymization system.

## Overview

The system generates three different probability files that represent different levels of information availability:

1. **Results-only probabilities** (`test_case_results_probabilities.csv`): Based solely on overall election results
2. **Original CVR probabilities** (`test_case_original_probabilities.csv`): Based on the original (non-anonymized) CVR with style-level detail
3. **Anonymized CVR probabilities** (`test_case_anonymized_probabilities.csv`): Based on the anonymized CVR where rare styles are aggregated

## Test Case Structure

The test case demonstrates three different ballot styles:

- **Style 1R1** (Rare): 1 ballot with contest A only
- **Style 2S2** (Common): 10 ballots with contests A and B  
- **Style 1S3** (Common): 10 ballots with contest B only

### Election Results
- **Contest A**: 7 votes for A0 (63.64%), 4 votes for A1 (36.36%) out of 11 total
- **Contest B**: 11 votes for B0 (55.00%), 9 votes for B1 (45.00%) out of 20 total

## Probability Differences by Voter Type

### Voter 1: Rare Style (1R1 - Contest A only)

This voter is in a rare style with only 1 ballot, which gets aggregated with the common style 2S2 to create `AGGREGATED-1` (11 ballots total).

| Information Source | P(A0) | P(A1) | Guessing Accuracy |
|-------------------|-------|-------|-------------------|
| Results-only      | 0.6364| 0.3636| 63.64% chance of guessing correctly |
| Original CVR      | 1.000 | 0.0000| **100% chance** - ballot is revealed! |
| Anonymized CVR    | 0.6364| 0.3636| 63.64% chance - protected by aggregation |

**Analysis**: 
- With the **original CVR**, this voter's ballot is completely revealed because they're the only one in their style. An attacker knows with 100% certainty how they voted.
- With **anonymization**, the rare ballot is aggregated with the 10 ballots from style 2S2. The probability drops back to the overall election result (63.64%), providing strong privacy protection.
- **Privacy gain**: Anonymization reduces guessing accuracy from 100% to 63.64%, a **36.36 percentage point improvement**.

### Voter 2: Common Style (2S2 - Contests A and B)

This voter is in a common style with 10 ballots, which gets aggregated with the rare style 1R1 to create `AGGREGATED-1`.

| Information Source | Contest A: P(A0) / P(A1) | Contest B: P(B0) / P(B1) | Best Guess Accuracy |
|-------------------|-------------------------|-------------------------|---------------------|
| Results-only      | 0.6364 / 0.3636        | 0.5500 / 0.4500        | 63.64% × 55.00% = 35.00% |
| Original CVR      | 0.6000 / 0.4000        | 0.5000 / 0.5000        | 60.00% × 50.00% = 30.00% |
| Anonymized CVR    | 0.6364 / 0.3636        | 0.5000 / 0.5000        | 63.64% × 50.00% = 31.82% |

**Analysis**:
- The **original CVR** provides style-specific probabilities: 60% for A0 and exactly 50/50 for B0/B1.
- With **results-only** data, an attacker would use overall election results: 63.64% for A0 and 55% for B0.
- With **anonymization**, Contest A reverts to overall results (63.64%) because aggregation mixes the rare voter (who voted A0) with this style. Contest B stays at 50% because style 1S3 doesn't have contest A, so only style 2S2 ballots contribute to contest B in the aggregate.
- **Privacy impact**: Anonymization slightly **reduces** privacy for contest A (from 60% to 63.64% accuracy) but is a necessary tradeoff to protect the rare voter. Overall joint probability stays similar.

### Voter 12: Common Style (1S3 - Contest B only)

This voter is in a common style with 10 ballots that remains separate and is not aggregated.

| Information Source | P(B0) | P(B1) | Guessing Accuracy |
|-------------------|-------|-------|-------------------|
| Results-only      | 0.5500| 0.4500| 55.00% chance |
| Original CVR      | 0.6000| 0.4000| 60.00% chance |
| Anonymized CVR    | 0.6000| 0.4000| 60.00% chance - unchanged |

**Analysis**:
- This voter's style has ≥10 ballots and is not aggregated, so their probabilities remain **unchanged** between original and anonymized CVRs.
- The **original/anonymized CVR** reveals that within this style, 60% voted for B0, compared to the overall 55%.
- **Privacy trade-off**: Common styles (≥10 ballots) retain their style-specific probabilities because they already meet the anonymity threshold. This provides better audit utility while maintaining reasonable privacy protection through the 10-ballot pool.

## Key Insights

### 1. Rare Styles Get Maximum Protection
Voters in rare styles (< 10 ballots) benefit most from anonymization:
- **Before**: Can have 100% guessing accuracy (completely revealed)
- **After**: Protected by aggregation, typically dropping to overall election probabilities
- In this example: **36.36 percentage point reduction** in guessing accuracy for the rare voter

### 2. Common Styles Retain Style-Level Detail
Voters in common styles (≥10 ballots) maintain style-specific probabilities:
- This is intentional - they already have sufficient anonymity from the 10-ballot pool
- Preserves audit utility by keeping granular voting patterns
- Provides reasonable privacy: guessing accuracy is based on a pool of at least 10 voters

### 3. Aggregation Creates Complex Probability Mixing
When rare styles are aggregated with common styles:
- The aggregate's probabilities reflect all included ballots
- Contest-specific probabilities may differ from overall results based on which styles had which contests
- Some common-style voters may see their probabilities shift slightly (as seen with Voter 2's Contest A)

### 4. Quantifying Privacy Protection

We can quantify privacy protection using the **guessing accuracy** metric:

- **Rare voter (V1)**: 100% → 63.64% = **36.36 point improvement**
- **Common voter in aggregated style (V2)**: 
  - Joint: 30.00% → 31.82% = 1.82 point reduction (acceptable cost)
  - This small reduction for common voters protects rare voters dramatically
- **Common voter in separate style (V12)**: 60.00% → 60.00% = **no change**

The system successfully achieves its goal: **protecting rare voters** (who are most vulnerable) while **maintaining utility** for common styles (which already provide anonymity through numbers).

## Recommendations for Analysis

When analyzing your own CVR data:

1. **Compare all three probability files** to understand the privacy impact
2. **Focus on rare voters**: Look for cases where original CVR probabilities approach 1.0 (revealed ballots)
3. **Calculate guessing accuracy** as the product of probabilities across all contests
4. **Verify aggregation effectiveness**: Anonymized probabilities for formerly-rare voters should drop significantly
5. **Monitor common style drift**: Large changes in common style probabilities may indicate over-aggregation

## Generating Probability Analysis for Your Data

```bash
# Generate original CVR
python3 guess_votes.py your_cvr.csv

# Anonymize the CVR
python3 anonymize_cvr.py your_cvr.csv your_cvr_anonymized.csv --summarize

# Generate probability comparison
python3 guess_votes.py your_cvr.csv --anonymized-cvr your_cvr_anonymized.csv

# Compare the three files:
# - test_case_results_probabilities.csv
# - test_case_original_probabilities.csv  
# - test_case_anonymized_probabilities.csv

# Run the validation script to see a detailed analysis
python3 validate_probability_analysis.py
```

Look for voters where the probability in the original CVR file is significantly higher than in the anonymized file - these are the voters most protected by anonymization.

The `validate_probability_analysis.py` script provides an automated way to verify the analysis and displays detailed privacy improvements for each voter type.
