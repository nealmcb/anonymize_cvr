# Differential Privacy Analysis for CVR Anonymization

## Executive Summary

This document investigates how **differential privacy** (DP) principles can be applied to the Cast Vote Record (CVR) anonymization problem, building on the current aggregation-based approach. We propose several differential privacy mechanisms that could enhance privacy guarantees while maintaining the utility needed for Risk-Limiting Audits (RLAs).

## What is Differential Privacy?

Differential privacy is a mathematical framework for privacy-preserving data analysis that provides rigorous, quantifiable privacy guarantees. The core principle is:

> **A randomized algorithm M provides ε-differential privacy if, for any two datasets D₁ and D₂ that differ by one record, and for any possible output O:**
> 
> **Pr[M(D₁) = O] ≤ e^ε × Pr[M(D₂) = O]**

In simpler terms: The presence or absence of any single individual's data has a bounded (controlled by ε) effect on the output. An observer cannot determine with high confidence whether any specific individual's data was included.

### Key Concepts

1. **Privacy Budget (ε)**: Controls the privacy-utility tradeoff
   - Smaller ε = stronger privacy, more noise
   - Larger ε = weaker privacy, less noise
   - Typical values: 0.1 (strong) to 10 (weak)

2. **Privacy Loss**: The information revealed about individuals
   - ε quantifies the maximum privacy loss
   - Accumulates across multiple queries (composition)

3. **Sensitivity**: How much one individual can affect the output
   - Lower sensitivity allows less noise for same privacy

4. **Noise Mechanisms**: How randomness is added
   - **Laplace mechanism**: For numeric queries, adds noise ~ Laplace(Δf/ε)
   - **Exponential mechanism**: For selecting from discrete options
   - **Gaussian mechanism**: Alternative to Laplace with (ε, δ)-DP

## Current Approach Analysis

The existing CVR anonymization uses **k-anonymity** (k=10):
- Groups rare styles to ensure each group has ≥10 ballots
- Deterministic aggregation based on style similarity
- No formal privacy guarantees beyond "hiding in a crowd of 10"

### Limitations of k-Anonymity

1. **No composition guarantees**: Multiple releases can leak information
2. **Vulnerable to auxiliary information**: If attacker knows someone's style, they can narrow down votes
3. **No formal privacy budget**: Hard to reason about privacy loss
4. **Linkage attacks**: Combining multiple datasets can re-identify individuals

## Differential Privacy Applications to CVR Anonymization

### Approach 1: Noisy Aggregation with Laplace Mechanism

**Concept**: Add calibrated noise to vote counts in aggregated rows.

**Implementation**:
```python
For each aggregated row containing n ballots:
  For each candidate c in each contest:
    reported_votes[c] = true_votes[c] + Laplace(Δ/ε)
    where Δ = 1 (one ballot can change count by at most 1)
```

**Privacy Guarantee**: ε-differential privacy per aggregated row

**Parameters**:
- ε = 1.0 (reasonable for election data)
- Noise scale = 1/ε = 1.0
- Expected noise magnitude ≈ 1 vote per candidate

**Advantages**:
- Formal privacy guarantees
- Protects against linkage attacks
- Composable (can track cumulative privacy loss)

**Challenges**:
- Noisy counts may not sum to exactly n ballots per row
- Need post-processing to ensure non-negativity
- May affect audit accuracy if noise is too large

**Compatibility with RLAs**:
- Risk-limiting audits are robust to small errors
- Noise of ±1-2 votes in aggregated groups should be acceptable
- Would need to account for noise in risk calculations

### Approach 2: Differentially Private k-Anonymity

**Concept**: Use exponential mechanism to select aggregation groups, adding privacy to the grouping process itself.

**Implementation**:
```python
For each rare style:
  # Define utility function u(style, group) = similarity score
  # Select aggregation target with probability:
  # P(group) ∝ exp(ε × u(style, group) / 2Δu)
  
  # Where Δu = maximum change in utility from one ballot
```

**Privacy Guarantee**: ε-differential privacy for group assignment

**Advantages**:
- Randomized grouping prevents deterministic inference
- Maintains k-anonymity threshold
- No noise added to final counts (counts are exact)

**Challenges**:
- More complex than current deterministic approach
- Need to define appropriate utility function
- May create less optimal groupings than deterministic method

### Approach 3: Private Multiplicative Weights (Synthetic Data)

**Concept**: Generate synthetic CVR data that preserves statistical properties while providing DP guarantees.

**Implementation**:
```python
# Use Private Multiplicative Weights to generate synthetic ballots
# that approximately match:
#   - Contest marginals (overall vote totals)
#   - Style distributions
#   - Within-style vote patterns
# While providing (ε, δ)-differential privacy
```

**Advantages**:
- Can release individual ballot-level data (synthetic)
- Preserves complex correlations
- Strong theoretical foundations

**Challenges**:
- Complex to implement
- Computational cost increases with data complexity
- Quality depends on carefully chosen query set
- May not preserve rare patterns well

### Approach 4: Local Differential Privacy for Individual Ballots

**Concept**: Each ballot applies local DP before aggregation (flips votes with small probability).

**Implementation**:
```python
For each ballot:
  For each vote:
    With probability p = ε/(ε + 1):
      keep true vote
    With probability 1-p:
      flip to random alternative
  
  Then aggregate as usual
```

**Privacy Guarantee**: ε-local differential privacy

**Advantages**:
- Privacy preserved even if aggregator is untrusted
- No central entity learns true votes
- Simple to implement

**Challenges**:
- High noise for meaningful privacy (ε-LDP requires more noise than central DP)
- May significantly impact utility for RLAs
- Difficult to calibrate for multi-candidate contests

## Recommended Approach: Hybrid System

We recommend a **two-layer approach** combining k-anonymity with noisy aggregation:

### Layer 1: Similarity-Based k-Anonymization (Existing)
- Maintain current aggregation strategy
- Ensures each published row represents ≥10 ballots
- Provides baseline "hiding in crowd" protection

### Layer 2: Calibrated Noise Addition (New)
- Add Laplace noise to aggregated vote counts
- Use moderate ε (e.g., ε = 2.0) for reasonable noise levels
- Apply post-processing constraints:
  - Ensure non-negative counts
  - Optionally round to integers
  - Document noise magnitude in metadata

### Privacy Analysis

**Privacy guarantees**:
- k-anonymity (k=10): protects against simple re-identification
- ε-differential privacy (ε=2.0): formal guarantee even with auxiliary information

**Noise magnitude** (ε = 2.0):
- Scale = 1/ε = 0.5
- Expected absolute deviation ≈ 0.5 votes per candidate
- 95% of noise within ±1.5 votes
- For aggregated groups of 10-20 ballots, this is 5-15% relative noise

**Example**:
```
True aggregated votes: [A: 6, B: 4]
With ε=2.0 Laplace noise: [A: 6.2, B: 3.8] → rounded [A: 6, B: 4]
or: [A: 7.1, B: 2.9] → rounded [A: 7, B: 3]
```

### Implementation Considerations

1. **Noise calibration**:
   - Make ε configurable (default: 2.0)
   - Provide noise-free mode for debugging
   - Document privacy budget in output metadata

2. **Post-processing**:
   ```python
   def add_dp_noise(count: int, epsilon: float = 2.0) -> int:
       """Add Laplace noise for differential privacy."""
       noise = np.random.laplace(loc=0, scale=1/epsilon)
       noisy_count = count + noise
       return max(0, round(noisy_count))  # Non-negative integer
   ```

3. **Metadata and transparency**:
   - Include DP parameters in output file header
   - Document privacy guarantees in README
   - Provide tools to analyze noise impact on RLA

4. **Audit compatibility**:
   - Noise should be small relative to group size
   - Document expected noise magnitude for auditors
   - Consider separate "audit version" with less noise if needed

## Alternative Approaches and Trade-offs

### Option A: Aggressive DP (ε = 0.5)
- **Pros**: Very strong privacy, composable across many releases
- **Cons**: Noise ≈ 2 votes per candidate, may impact audit accuracy
- **Use case**: When privacy is paramount, multiple data releases planned

### Option B: Mild DP (ε = 5.0)
- **Pros**: Minimal noise (≈0.2 votes), preserves utility
- **Cons**: Weaker formal guarantees
- **Use case**: When k-anonymity already provides good protection

### Option C: Randomized Rounding Only
- **Pros**: Minimal implementation change, preserves exact counts for large aggregates
- **Cons**: Limited privacy improvement over k-anonymity alone
- **Use case**: Conservative first step toward DP

### Option D: Exponential Mechanism for Grouping
- **Pros**: DP guarantees without noise in final counts
- **Cons**: More complex, may produce suboptimal groupings
- **Use case**: When exact counts are critical but grouping can be randomized

## Research Foundations

### Key Papers
1. **Dwork, C. (2006). "Differential Privacy."** - Original DP definition
2. **Machanavajjhala et al. (2007). "l-Diversity: Privacy Beyond k-Anonymity."** - Limitations of k-anonymity
3. **McSherry & Mironov (2009). "Differentially Private Recommender Systems."** - Practical DP applications
4. **Dwork & Roth (2014). "The Algorithmic Foundations of Differential Privacy."** - Comprehensive DP textbook

### Election Privacy Research
1. **Chaum (1981). "Untraceable Electronic Mail."** - Foundation of voting privacy
2. **Benaloh (2006). "Simple Verifiable Elections."** - Balancing privacy and auditability
3. **Adida (2008). "Helios: Web-based Open-Audit Voting."** - Privacy in e-voting
4. **Rivest & Stark (2008). "Risk-Limiting Audits."** - Statistical auditing methods

### Relevant to CVR Anonymization
- **U.S. Census Bureau (2019).** Uses differential privacy for 2020 Census
  - ε ≈ 0.5-19.6 depending on geography level
  - Shows DP is practical at scale
- **Google RAPPOR (2014).** Local DP for Chrome telemetry
  - ε ≈ 2-4 for frequency estimation
  - Demonstrates utility can be preserved with moderate ε

## Implementation Roadmap

### Phase 1: Research and Specification (This Document)
- ✓ Document DP principles
- ✓ Analyze current approach
- ✓ Propose DP mechanisms
- ✓ Recommend hybrid approach

### Phase 2: Proof of Concept (Recommended Next Steps)
1. Implement Laplace noise addition as optional flag
2. Create test suite comparing:
   - Original CVR
   - k-anonymized CVR (current)
   - k-anonymized + DP noise (proposed)
3. Measure:
   - Privacy metrics (ε, k)
   - Utility metrics (vote accuracy, RLA impact)
   - Noise distribution statistics

### Phase 3: Validation and Tuning
1. Work with election officials and auditors
2. Determine acceptable ε values for real elections
3. Validate that DP noise doesn't break RLA guarantees
4. Document best practices

### Phase 4: Production Implementation
1. Add `--differential-privacy` flag with configurable ε
2. Update documentation with DP explanations
3. Provide analysis tools for privacy/utility assessment
4. Consider formal verification of privacy properties

## Open Questions and Future Research

1. **Composition**: How should ε accumulate if CVRs are released multiple times?
2. **Contest heterogeneity**: Should ε vary by contest importance?
3. **Temporal privacy**: What if CVR is updated during canvass?
4. **Auxiliary information**: What external data might attackers have?
5. **Legal compliance**: Does DP satisfy C.R.S. 24-72-205.5 intent?
6. **Audit impact**: Exactly how does noise affect RLA risk calculations?

## Conclusion

Differential privacy provides a rigorous mathematical framework that can enhance the CVR anonymization tool beyond k-anonymity. The recommended hybrid approach:

1. **Maintains current k-anonymization** for baseline protection
2. **Adds calibrated Laplace noise** for formal DP guarantees
3. **Uses moderate ε (≈2.0)** to balance privacy and utility
4. **Preserves RLA compatibility** with documented noise bounds
5. **Enables privacy composition** for multiple data releases

This approach provides:
- **Stronger privacy**: ε-DP protects against sophisticated attacks
- **Formal guarantees**: Quantifiable privacy loss
- **Backward compatibility**: Can be added as optional enhancement
- **Practical utility**: Noise levels acceptable for auditing

The next step is to implement a proof-of-concept to empirically validate that differential privacy can be successfully integrated while maintaining the tool's core mission: enabling transparent, auditable elections while protecting voter privacy.

## References

1. Dwork, C., & Roth, A. (2014). "The Algorithmic Foundations of Differential Privacy." Foundations and Trends in Theoretical Computer Science, 9(3-4), 211-407.

2. Machanavajjhala, A., Kifer, D., Gehrke, J., & Venkitasubramaniam, M. (2007). "L-diversity: Privacy beyond k-anonymity." ACM Transactions on Knowledge Discovery from Data, 1(1), 3.

3. Colorado Revised Statutes 24-72-205.5. "Public records - ballots - cast vote records."

4. Branscomb, H., McCarthy, J., McBurnett, N., Rivest, R., & Stark, P. (2018). "Colorado Risk-Limiting Tabulation Audit: Preserving Anonymity of Cast Vote Record." Colorado Secretary of State.

5. Abowd, J. M. (2018). "The U.S. Census Bureau Adopts Differential Privacy." Proceedings of the 24th ACM SIGKDD International Conference on Knowledge Discovery & Data Mining, 2867.

6. Erlingsson, Ú., Pihur, V., & Korolova, A. (2014). "RAPPOR: Randomized Aggregatable Privacy-Preserving Ordinal Response." Proceedings of the 2014 ACM SIGSAC Conference on Computer and Communications Security, 1054-1067.
