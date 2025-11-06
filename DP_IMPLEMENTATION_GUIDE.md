# Differential Privacy Implementation Guide

## Quick Start: Adding DP to anonymize_cvr.py

This guide provides step-by-step instructions for implementing the recommended differential privacy approach (Laplace noise on aggregated counts).

## Implementation Steps

### Step 1: Add Differential Privacy Module

Create a new section in `anonymize_cvr.py` or a separate module `dp_noise.py`:

```python
import random
import math

class DifferentialPrivacyNoise:
    """
    Add differential privacy noise to CVR aggregated counts.
    
    Implements the Laplace mechanism for epsilon-differential privacy.
    """
    
    def __init__(self, epsilon: float = 2.0, random_seed: Optional[int] = None):
        """
        Initialize DP noise generator.
        
        Args:
            epsilon: Privacy budget (smaller = more privacy, more noise)
                    Recommended: 2.0 for moderate privacy
            random_seed: Random seed for reproducibility (optional)
        """
        if epsilon <= 0:
            raise ValueError("Epsilon must be positive")
        
        self.epsilon = epsilon
        self.noise_added = False
        
        if random_seed is not None:
            random.seed(random_seed)
    
    def laplace_sample(self, sensitivity: float = 1.0) -> float:
        """
        Sample from Laplace distribution.
        
        Laplace(0, b) where b = sensitivity/epsilon
        
        Args:
            sensitivity: Maximum change one record can make (default 1 vote)
        
        Returns:
            Random noise value
        """
        scale = sensitivity / self.epsilon
        
        # Use inverse CDF method
        # Laplace CDF: F(x) = 0.5 + 0.5*sign(x)*(1 - exp(-|x|/b))
        # Inverse: x = -b*sign(u)*ln(1 - 2|u|) where u ~ Uniform(-0.5, 0.5)
        u = random.random() - 0.5
        noise = -scale * (1 if u > 0 else -1) * math.log(1 - 2 * abs(u))
        
        return noise
    
    def add_noise_to_count(self, count: int, sensitivity: float = 1.0) -> int:
        """
        Add DP noise to a single vote count.
        
        Args:
            count: True vote count
            sensitivity: Query sensitivity (default 1)
        
        Returns:
            Noisy count (non-negative integer)
        """
        noise = self.laplace_sample(sensitivity)
        noisy_count = count + noise
        
        # Post-processing: ensure non-negative and round to integer
        result = max(0, round(noisy_count))
        self.noise_added = True
        
        return result
    
    def add_noise_to_row(self, vote_counts: List[int]) -> List[int]:
        """
        Add DP noise to all vote counts in a row.
        
        Args:
            vote_counts: List of vote counts
        
        Returns:
            List of noisy counts
        """
        return [self.add_noise_to_count(count) for count in vote_counts]
    
    def get_noise_stats(self, sensitivity: float = 1.0) -> Dict[str, float]:
        """
        Get statistics about expected noise magnitude.
        
        Returns:
            Dictionary with noise statistics
        """
        scale = sensitivity / self.epsilon
        return {
            'epsilon': self.epsilon,
            'scale': scale,
            'mean_absolute_deviation': scale,
            'standard_deviation': math.sqrt(2) * scale,
            'typical_range': 3 * scale,  # ~95% within this range
        }
```

### Step 2: Modify Command Line Arguments

Update the argument parser to support DP options:

```python
def main():
    parser = argparse.ArgumentParser(
        description='Anonymize CVR files by aggregating rare styles',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python anonymize_cvr.py input.csv output.csv
  python anonymize_cvr.py input.csv output.csv --min-ballots 15
  python anonymize_cvr.py input.csv output.csv --differential-privacy
  python anonymize_cvr.py input.csv output.csv --differential-privacy --epsilon 1.0
        """
    )
    
    parser.add_argument('input_file', help='Input CVR file path')
    parser.add_argument('output_file', help='Output anonymized CVR file path')
    parser.add_argument('--min-ballots', type=int, default=10,
                       help='Minimum ballots required per style (default: 10)')
    parser.add_argument('--stylecol', type=int, default=6,
                       help='Index of style column (default: 6)')
    parser.add_argument('--headerlen', type=int, default=8,
                       help='Number of header columns (default: 8)')
    parser.add_argument('--summarize', '-s', action='store_true',
                       help='Print detailed summary of CVR statistics')
    
    # NEW: Differential Privacy options
    parser.add_argument('--differential-privacy', '--dp', action='store_true',
                       help='Add differential privacy noise to aggregated counts')
    parser.add_argument('--epsilon', type=float, default=2.0,
                       help='Privacy budget epsilon (default: 2.0, smaller = more privacy)')
    parser.add_argument('--dp-seed', type=int, default=None,
                       help='Random seed for DP noise (for reproducibility)')
    
    args = parser.parse_args()
    
    # Initialize DP noise generator if requested
    dp_noise = None
    if args.differential_privacy:
        dp_noise = DifferentialPrivacyNoise(
            epsilon=args.epsilon,
            random_seed=args.dp_seed
        )
        print(f"Differential Privacy enabled: ε = {args.epsilon}")
        stats = dp_noise.get_noise_stats()
        print(f"  Expected noise magnitude: ±{stats['typical_range']:.2f} votes (95% range)")
    
    # ... rest of processing ...
```

### Step 3: Apply Noise to Aggregated Rows

Modify the `aggregate_votes` function or the code that creates aggregated rows:

```python
def aggregate_votes_with_dp(rows: List[List[str]], 
                            headerlen: int = 8, 
                            aggregate_id: str = "",
                            dp_noise: Optional[DifferentialPrivacyNoise] = None) -> List[str]:
    """
    Aggregate multiple CVR rows with optional differential privacy.
    
    Args:
        rows: List of CVR rows to aggregate
        headerlen: Number of header columns
        aggregate_id: Identifier for this aggregate
        dp_noise: Optional DP noise generator
    
    Returns:
        Aggregated row (with DP noise if dp_noise provided)
    """
    if not rows:
        return []
    
    # Create base aggregated row (existing logic)
    aggregated = aggregate_votes(rows, headerlen, aggregate_id)
    
    # Apply differential privacy noise if requested
    if dp_noise is not None:
        for col_idx in range(headerlen, len(aggregated)):
            value = aggregated[col_idx].strip()
            if value and value.replace('.', '').replace('-', '').isdigit():
                try:
                    count = int(float(value))
                    noisy_count = dp_noise.add_noise_to_count(count)
                    aggregated[col_idx] = str(noisy_count)
                except ValueError:
                    pass  # Skip non-numeric values
    
    return aggregated
```

### Step 4: Add Metadata to Output

Document DP parameters in the output file:

```python
def write_output_with_metadata(output_file: str, 
                               header_rows: List[List[str]],
                               data_rows: List[List[str]],
                               dp_noise: Optional[DifferentialPrivacyNoise] = None):
    """
    Write output CVR with optional DP metadata.
    """
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Write headers
        for row in header_rows:
            writer.writerow(row)
        
        # If DP was used, add metadata comment
        if dp_noise is not None:
            stats = dp_noise.get_noise_stats()
            # Add as comment row or in version row
            metadata = [
                f"# Differential Privacy: epsilon={stats['epsilon']}, "
                f"typical_noise=±{stats['typical_range']:.2f}"
            ]
            writer.writerow(metadata)
        
        # Write data rows
        for row in data_rows:
            writer.writerow(row)
```

### Step 5: Update Summary Output

If using `--summarize`, include DP information:

```python
def print_summary_with_dp(stats: dict, dp_noise: Optional[DifferentialPrivacyNoise] = None):
    """Print summary including DP information."""
    
    # ... existing summary output ...
    
    if dp_noise is not None:
        print("\n=== Differential Privacy ===")
        stats = dp_noise.get_noise_stats()
        print(f"  Privacy budget (ε): {stats['epsilon']:.2f}")
        print(f"  Noise scale: {stats['scale']:.2f}")
        print(f"  Expected absolute deviation: {stats['mean_absolute_deviation']:.2f} votes")
        print(f"  95% of noise within: ±{stats['typical_range']:.2f} votes")
        print(f"  Privacy guarantee: {stats['epsilon']:.2f}-differential privacy")
        
        if stats['epsilon'] < 1.0:
            privacy_level = "Strong"
        elif stats['epsilon'] < 3.0:
            privacy_level = "Moderate"
        else:
            privacy_level = "Weak"
        print(f"  Privacy level: {privacy_level}")
```

## Testing

### Test 1: Basic Functionality

```bash
# Without DP (should work as before)
python3 anonymize_cvr.py test_case_cvr.csv output_no_dp.csv --summarize

# With DP (default epsilon=2.0)
python3 anonymize_cvr.py test_case_cvr.csv output_dp.csv --differential-privacy --summarize

# Compare files
diff output_no_dp.csv output_dp.csv
```

### Test 2: Different Epsilon Values

```bash
# Strong privacy (more noise)
python3 anonymize_cvr.py test_case_cvr.csv output_eps1.csv --dp --epsilon 1.0

# Weak privacy (less noise)
python3 anonymize_cvr.py test_case_cvr.csv output_eps5.csv --dp --epsilon 5.0
```

### Test 3: Reproducibility

```bash
# Same seed should produce same output
python3 anonymize_cvr.py test_case_cvr.csv output1.csv --dp --dp-seed 42
python3 anonymize_cvr.py test_case_cvr.csv output2.csv --dp --dp-seed 42
diff output1.csv output2.csv  # Should be identical
```

### Test 4: Utility Validation

```python
# Create test to measure noise impact
def test_dp_utility():
    """Test that DP preserves election outcomes."""
    # Run anonymization with and without DP
    results_no_dp = anonymize_cvr("test.csv", dp=False)
    results_with_dp = anonymize_cvr("test.csv", dp=True, epsilon=2.0)
    
    # Check winner preserved
    for contest in contests:
        winner_no_dp = get_winner(results_no_dp, contest)
        winner_with_dp = get_winner(results_with_dp, contest)
        assert winner_no_dp == winner_with_dp, f"Winner changed for {contest}"
    
    # Check noise magnitude
    avg_noise = calculate_average_noise(results_no_dp, results_with_dp)
    assert avg_noise < 1.5, f"Noise too high: {avg_noise}"
```

## Usage Examples

### Example 1: Basic DP Anonymization

```bash
python3 anonymize_cvr.py \
    original_cvr.csv \
    anonymized_cvr.csv \
    --differential-privacy \
    --summarize
```

Output:
```
Differential Privacy enabled: ε = 2.0
  Expected noise magnitude: ±1.50 votes (95% range)

=== CVR Summary ===
...

=== Differential Privacy ===
  Privacy budget (ε): 2.00
  Expected absolute deviation: 0.50 votes
  Privacy level: Moderate
```

### Example 2: High Privacy Setting

```bash
python3 anonymize_cvr.py \
    original_cvr.csv \
    anonymized_cvr.csv \
    --differential-privacy \
    --epsilon 0.5 \
    --summarize
```

### Example 3: Reproducible Output

```bash
# For testing or verification
python3 anonymize_cvr.py \
    original_cvr.csv \
    anonymized_cvr.csv \
    --differential-privacy \
    --epsilon 2.0 \
    --dp-seed 12345
```

## Integration with guess_votes.py

To analyze DP impact on vote guessing probabilities:

```bash
# Generate test case
python3 guess_votes.py

# Anonymize with DP
python3 anonymize_cvr.py \
    test_case_cvr.csv \
    test_case_anonymized_dp.csv \
    --differential-privacy

# Analyze probabilities
python3 guess_votes.py \
    test_case_cvr.csv \
    --anonymized-cvr test_case_anonymized_dp.csv

# Compare probability files
# - test_case_original_probabilities.csv (from CVR styles)
# - test_case_anonymized_probabilities.csv (with DP noise)
```

## Validation Checklist

Before deploying DP implementation:

- [ ] Unit tests pass for DP noise generation
- [ ] Noise magnitude matches expected values for different ε
- [ ] Non-negative integer constraints enforced
- [ ] Reproducibility works (same seed = same output)
- [ ] Winner preserved in >99% of test cases (ε=2.0)
- [ ] Average noise < 1 vote per candidate (ε=2.0)
- [ ] Metadata correctly written to output
- [ ] Summary output includes DP statistics
- [ ] Documentation updated
- [ ] Examples work correctly

## Performance Considerations

Adding DP noise is very fast (microseconds per count), so performance impact is negligible:

```python
import time

# Typical anonymization time
start = time.time()
anonymize_cvr("large_cvr.csv", "output.csv", dp=False)
time_no_dp = time.time() - start

start = time.time()
anonymize_cvr("large_cvr.csv", "output.csv", dp=True, epsilon=2.0)
time_with_dp = time.time() - start

overhead = (time_with_dp - time_no_dp) / time_no_dp * 100
print(f"DP overhead: {overhead:.1f}%")  # Typically < 1%
```

## Troubleshooting

### Issue: Noise seems too high

**Check**: What epsilon value are you using?
- ε < 1.0: High noise (strong privacy)
- ε = 2.0: Moderate noise (recommended)
- ε > 5.0: Low noise (weak privacy)

**Solution**: Increase epsilon for less noise

### Issue: Results not reproducible

**Check**: Are you using the same seed?
```bash
--dp-seed 42
```

**Solution**: Always use same seed for reproducible testing

### Issue: Negative counts appearing

**Check**: Is post-processing enabled?

**Solution**: The implementation should always apply `max(0, round(noisy_count))`

### Issue: Counts don't sum correctly

**Note**: This is expected! DP noise is independent per count, so sum of noisy counts ≠ total ballots.

**Options**:
1. Accept small discrepancies (±1-2 ballots)
2. Post-process to enforce sum constraint (reduces privacy slightly)
3. Document expected variance in output

## Next Steps

After implementing basic DP:

1. **Advanced composition**: Use tighter privacy bounds for multiple releases
2. **Adaptive epsilon**: Adjust ε based on aggregate size or margin
3. **Privacy budget tracking**: Track cumulative ε across releases
4. **RLA integration**: Automatically adjust risk calculations for DP noise
5. **Formal verification**: Prove privacy properties with theorem prover

## Resources

- **Differential Privacy Book**: Dwork & Roth (2014) - Free at https://www.cis.upenn.edu/~aaroth/Papers/privacybook.pdf
- **DP for Social Good**: https://privacytools.seas.harvard.edu/
- **US Census DP**: https://www.census.gov/programs-surveys/decennial-census/decade/2020/planning-management/process/disclosure-avoidance.html
- **OpenDP Library**: https://opendp.org/ (Python library for DP)

## Questions?

See `DIFFERENTIAL_PRIVACY_SUMMARY.md` for overview or `differential_privacy_analysis.md` for detailed theory.
