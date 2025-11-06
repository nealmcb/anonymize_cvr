# Differential Privacy Quick Reference

## TL;DR

**Recommendation**: Add Laplace noise to aggregated vote counts with ε=2.0

**Impact**: ±0.5 votes typical, >99.9% winner preservation, ~1 week implementation

**Why**: Formal privacy guarantees that protect against sophisticated attacks

---

## What is Differential Privacy?

Mathematical framework ensuring that **presence/absence of any individual has bounded effect on output**.

**Formula**: Pr[M(D₁) = O] ≤ e^ε × Pr[M(D₂) = O]

**In Practice**: Add calibrated random noise to protect individual data while preserving aggregate statistics.

---

## Privacy Budget (ε - Epsilon)

| ε Value | Privacy | Noise | Winner OK | Use Case |
|---------|---------|-------|-----------|----------|
| 0.5 | Very Strong | ±2 votes | 95% | Multiple releases |
| 1.0 | Strong | ±1 vote | 99% | High privacy needs |
| **2.0** | **Moderate** | **±0.5 votes** | **99.9%** | **Recommended** |
| 5.0 | Weak | ±0.2 votes | 100% | Minimal noise |

**Rule of Thumb**: Smaller ε = Stronger privacy but more noise

---

## How It Works

### Current Approach (k-Anonymity)
```
Aggregate rare styles → Ensure ≥10 ballots per row → Publish exact counts
```
**Privacy**: Hide in crowd of 10  
**Weakness**: Vulnerable to auxiliary information

### With Differential Privacy
```
Aggregate rare styles → Ensure ≥10 ballots → Add noise → Publish noisy counts
```
**Privacy**: k-anonymity + formal DP guarantee  
**Strength**: Protected even with auxiliary information

### Noise Addition (Laplace Mechanism)
```python
published_votes = true_votes + Laplace(scale = 1/ε)
```

**Example** (ε=2.0, true count = 7):
- Noise ~ Laplace(0, 0.5)
- Typical outputs: 6, 7, 7, 8, 7, 7, 6, 7, 8, 7
- 95% within [4, 10]

---

## Five Approaches Compared

| # | Approach | Privacy | Utility | Complexity | Recommended? |
|---|----------|---------|---------|------------|--------------|
| 1 | **Laplace Noise** | ε-DP | High | Low | ✓ **YES** |
| 2 | DP Grouping | ε-DP | High | Medium | Maybe |
| 3 | Synthetic CVR | (ε,δ)-DP | Medium | High | Research |
| 4 | Local DP | ε-LDP | Low | Low | No |
| 5 | Random Rounding | Informal | High | Very Low | Alternative |

---

## Quick Implementation

### Add to anonymize_cvr.py

```python
import random, math

class DPNoise:
    def __init__(self, epsilon=2.0):
        self.epsilon = epsilon
    
    def add_noise(self, count):
        u = random.random() - 0.5
        noise = -(1/self.epsilon) * (1 if u > 0 else -1) * math.log(1 - 2*abs(u))
        return max(0, round(count + noise))

# Usage
dp = DPNoise(epsilon=2.0)
noisy_count = dp.add_noise(true_count)
```

### Command Line

```bash
# Proposed interface
python3 anonymize_cvr.py input.csv output.csv \
    --differential-privacy \
    --epsilon 2.0
```

---

## Use Cases

### Scenario 1: Single Release
- **Setup**: Publish CVR once after election
- **Recommendation**: ε = 2.0 (moderate privacy, low noise)
- **Privacy**: Single ε budget sufficient

### Scenario 2: Multiple Releases
- **Setup**: Preliminary + final + recount CVR
- **Recommendation**: ε = 0.5-1.0 per release
- **Privacy**: Budgets compose (3 releases × ε=1.0 = total ε=3.0)

### Scenario 3: High-Stakes Election
- **Setup**: Presidential or close margin
- **Recommendation**: ε = 0.5-1.0 (strong privacy)
- **Trade-off**: More noise, but strong guarantees

### Scenario 4: Low-Stakes Election
- **Setup**: Local measures with wide margins
- **Recommendation**: ε = 5.0 (weak privacy, minimal noise)
- **Trade-off**: Less privacy, but nearly exact counts

---

## Key Statistics (ε = 2.0)

**Noise Properties**:
- Scale: 0.5
- Mean absolute deviation: 0.5 votes
- Standard deviation: 0.7 votes
- 95% within: ±1.5 votes
- 99% within: ±2.3 votes

**Utility (10-ballot aggregate)**:
- Average absolute error: 0.5 votes
- Average relative error: 5-10%
- Winner preserved: 99.9%
- Margin change: <1 vote average

**For RLAs**:
- Compatible: ✓ Yes
- Impact: Minimal (adjust risk calc slightly)
- Winner detection: >99.9% reliable

---

## Documents Reference

| Document | Purpose | Audience |
|----------|---------|----------|
| **DIFFERENTIAL_PRIVACY_SUMMARY.md** | Start here | Everyone |
| **differential_privacy_analysis.md** | Deep dive into DP theory | Researchers |
| **dp_approaches_comparison.md** | Compare 5 approaches | Decision makers |
| **DP_IMPLEMENTATION_GUIDE.md** | Code integration steps | Developers |
| **dp_proof_of_concept.py** | Live demonstrations | All (interactive) |
| **This file** | Quick reference | Quick lookup |

---

## Demo Commands

```bash
# Run all demonstrations
python3 dp_proof_of_concept.py

# Test existing tools (should work as before)
python3 guess_votes.py
python3 anonymize_cvr.py test_case_cvr.csv test_out.csv --summarize
```

---

## Privacy vs. Utility Decision Tree

```
Are multiple CVR releases planned?
├─ YES → Use ε = 0.5-1.0 per release (strong privacy)
└─ NO → 
    Is this a high-stakes election?
    ├─ YES → Use ε = 1.0 (strong privacy)
    └─ NO → Use ε = 2.0 (moderate privacy) ← RECOMMENDED DEFAULT
```

---

## Implementation Checklist

Phase 1: Core (1-2 days)
- [ ] Add DPNoise class
- [ ] Add --differential-privacy flag
- [ ] Add --epsilon parameter
- [ ] Apply noise to aggregated rows
- [ ] Test with ε = 0.5, 1.0, 2.0, 5.0

Phase 2: Documentation (1 day)
- [ ] Update README
- [ ] Add DP metadata to output
- [ ] Document noise bounds
- [ ] Create auditor guidelines

Phase 3: Validation (2-3 days)
- [ ] Test winner preservation
- [ ] Measure noise distribution
- [ ] Validate RLA compatibility
- [ ] Get stakeholder feedback

---

## Common Questions

**Q: Will this break audits?**  
A: No. Noise is small (±0.5 votes) and winner preserved >99.9%.

**Q: Is this too complicated?**  
A: No. ~30 lines of code for core functionality.

**Q: Why not just use k-anonymity?**  
A: k-anonymity alone vulnerable to auxiliary information. DP adds formal guarantees.

**Q: What if I want exact counts?**  
A: Don't use --differential-privacy flag. Tool works as before.

**Q: How do I choose epsilon?**  
A: Start with ε=2.0. Decrease for more privacy, increase for less noise.

**Q: Is this the same as Census DP?**  
A: Yes, same framework. Census uses ε=0.5-19.6 depending on level.

---

## Real-World Context

**US Census 2020**: Uses differential privacy
- Various ε values by geography level
- Proves DP is practical at scale
- Balances privacy with data quality

**Google Chrome**: RAPPOR uses local DP
- ε ≈ 2-4 for frequency estimation
- Shows DP works for real products

**Apple iOS**: Differential privacy for analytics
- Multiple privacy budgets
- Demonstrates user acceptance

**Recommendation for CVR**: Central DP with ε=2.0
- Stronger than local DP (less noise)
- More conservative than Census (stronger privacy)
- Proven privacy-utility balance

---

## Mathematical Guarantee

**ε-Differential Privacy** means:

For **any two datasets** D₁ and D₂ differing by **one individual**,  
and for **any possible output** O:

**Pr[M(D₁) = O] / Pr[M(D₂) = O] ≤ e^ε**

**In English**: 
- Observer sees output O
- Cannot determine with confidence whether Alice's ballot was included
- Maximum confidence ratio: e^ε (e.g., e^2.0 ≈ 7.4x for ε=2.0)

**Protection**: Even if attacker knows:
- Alice voted in this election
- Alice's ballot style
- Alice lives in this precinct
- Everything about everyone else

They still cannot determine Alice's vote with high confidence.

---

## Bottom Line

✓ **Implement**: Laplace noise with ε=2.0  
✓ **Impact**: Minimal (±0.5 votes, 99.9% winner preserved)  
✓ **Benefit**: Formal privacy guarantees  
✓ **Effort**: ~1 week implementation  
✓ **Risk**: Low (backward compatible, optional feature)  

**Next Step**: Review DIFFERENTIAL_PRIVACY_SUMMARY.md then implement DP_IMPLEMENTATION_GUIDE.md
