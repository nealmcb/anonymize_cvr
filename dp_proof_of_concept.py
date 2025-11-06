#!/usr/bin/env python3
"""
Proof of Concept: Differential Privacy for CVR Anonymization

This module demonstrates how differential privacy (DP) mechanisms can be
integrated with the existing k-anonymity approach for CVR anonymization.

It provides:
1. Laplace mechanism for adding DP noise to vote counts
2. Privacy budget tracking
3. Utility analysis (comparing noisy vs. true counts)
4. Demonstration functions showing DP in action

This is a research/demonstration tool, not production code.
"""

import random
import math
from typing import List, Tuple, Dict
from collections import defaultdict


class DifferentialPrivacy:
    """
    Implements differential privacy mechanisms for CVR anonymization.
    
    Supports:
    - Laplace mechanism for numeric queries
    - Privacy budget (epsilon) management
    - Sensitivity analysis
    """
    
    def __init__(self, epsilon: float = 2.0, random_seed: int = None):
        """
        Initialize DP mechanism.
        
        Args:
            epsilon: Privacy budget parameter (smaller = more privacy, more noise)
                    Typical values: 0.1 (strong privacy) to 10 (weak privacy)
            random_seed: Random seed for reproducibility (None = random)
        """
        self.epsilon = epsilon
        self.total_privacy_loss = 0.0
        if random_seed is not None:
            random.seed(random_seed)
    
    def laplace_noise(self, sensitivity: float = 1.0) -> float:
        """
        Generate noise from Laplace distribution.
        
        The Laplace mechanism adds noise ~ Laplace(0, sensitivity/epsilon) to
        protect privacy of individual records.
        
        Args:
            sensitivity: Maximum change one record can make to the query result
                        For vote counts, typically 1 (one ballot = one vote change)
        
        Returns:
            Noise value (can be positive or negative)
        """
        scale = sensitivity / self.epsilon
        # Laplace distribution: f(x) = (1/2b) * exp(-|x|/b) where b = scale
        # Using inverse CDF method: noise = -scale * sign(u) * ln(1 - 2|u|)
        # where u is uniform in (-0.5, 0.5)
        u = random.random() - 0.5
        return -scale * (1 if u > 0 else -1) * math.log(1 - 2 * abs(u))
    
    def add_noise_to_count(self, true_count: int, sensitivity: float = 1.0,
                          post_process: bool = True) -> int:
        """
        Add differential privacy noise to a vote count.
        
        Args:
            true_count: True vote count
            sensitivity: Query sensitivity (default 1 for single vote)
            post_process: If True, ensure non-negative integer result
        
        Returns:
            Noisy count (integer if post_process=True)
        """
        noise = self.laplace_noise(sensitivity)
        noisy_count = true_count + noise
        
        if post_process:
            # Ensure non-negative and round to integer
            return max(0, round(noisy_count))
        else:
            return noisy_count
    
    def add_noise_to_row(self, vote_counts: List[int], 
                        sensitivity: float = 1.0) -> List[int]:
        """
        Add DP noise to all vote counts in an aggregated row.
        
        Args:
            vote_counts: List of vote counts for different choices
            sensitivity: Per-count sensitivity
        
        Returns:
            List of noisy vote counts
        """
        return [self.add_noise_to_count(count, sensitivity) 
                for count in vote_counts]
    
    def track_privacy_loss(self, num_queries: int = 1) -> float:
        """
        Track cumulative privacy loss from composition.
        
        Under basic composition, k queries each with epsilon privacy
        result in total privacy loss of k * epsilon.
        
        Args:
            num_queries: Number of DP queries made
        
        Returns:
            Total privacy loss (cumulative epsilon)
        """
        self.total_privacy_loss += self.epsilon * num_queries
        return self.total_privacy_loss
    
    def get_privacy_guarantee(self) -> str:
        """
        Get human-readable privacy guarantee description.
        
        Returns:
            Description of privacy guarantee
        """
        if self.epsilon < 0.5:
            level = "very strong"
        elif self.epsilon < 1.0:
            level = "strong"
        elif self.epsilon < 3.0:
            level = "moderate"
        elif self.epsilon < 10.0:
            level = "weak"
        else:
            level = "very weak"
        
        return f"ε = {self.epsilon:.2f} ({level} privacy)"
    
    def expected_noise_magnitude(self, sensitivity: float = 1.0) -> Dict[str, float]:
        """
        Calculate expected noise characteristics.
        
        For Laplace(0, b) where b = sensitivity/epsilon:
        - Mean absolute deviation: b
        - Standard deviation: sqrt(2) * b
        - 95% within approximately ±3b
        
        Args:
            sensitivity: Query sensitivity
        
        Returns:
            Dictionary with noise statistics
        """
        scale = sensitivity / self.epsilon
        return {
            "scale": scale,
            "mean_abs_deviation": scale,
            "std_dev": math.sqrt(2) * scale,
            "approx_95_percent_bounds": 3 * scale
        }


class UtilityAnalyzer:
    """
    Analyzes utility (accuracy) of differentially private CVR anonymization.
    
    Measures how much noise affects vote counting and audit processes.
    """
    
    @staticmethod
    def absolute_error(true_counts: List[int], noisy_counts: List[int]) -> float:
        """Mean absolute error between true and noisy counts."""
        return sum(abs(t - n) for t, n in zip(true_counts, noisy_counts)) / len(true_counts)
    
    @staticmethod
    def relative_error(true_counts: List[int], noisy_counts: List[int]) -> float:
        """Mean relative error (as percentage)."""
        errors = []
        for t, n in zip(true_counts, noisy_counts):
            if t > 0:
                errors.append(abs(t - n) / t * 100)
        return sum(errors) / len(errors) if errors else 0.0
    
    @staticmethod
    def winner_preservation(true_counts: List[int], noisy_counts: List[int]) -> bool:
        """Check if winner is preserved after adding noise."""
        if not true_counts or not noisy_counts:
            return True
        return true_counts.index(max(true_counts)) == noisy_counts.index(max(noisy_counts))
    
    @staticmethod
    def margin_change(true_counts: List[int], noisy_counts: List[int]) -> float:
        """Calculate change in victory margin."""
        if len(true_counts) < 2 or len(noisy_counts) < 2:
            return 0.0
        
        true_sorted = sorted(true_counts, reverse=True)
        noisy_sorted = sorted(noisy_counts, reverse=True)
        
        true_margin = true_sorted[0] - true_sorted[1]
        noisy_margin = noisy_sorted[0] - noisy_sorted[1]
        
        return abs(true_margin - noisy_margin)


def demonstrate_dp_noise():
    """
    Demonstrate differential privacy noise on sample vote counts.
    
    Shows how different epsilon values affect noise and utility.
    """
    print("=" * 70)
    print("DIFFERENTIAL PRIVACY DEMONSTRATION")
    print("=" * 70)
    print()
    
    # Sample aggregated row: 10 ballots, contest with 3 candidates
    true_counts = [6, 3, 1]  # Candidate A: 6, B: 3, C: 1
    print(f"True vote counts: {true_counts}")
    print()
    
    # Test different epsilon values
    epsilon_values = [0.5, 1.0, 2.0, 5.0]
    
    for epsilon in epsilon_values:
        print(f"\n--- ε = {epsilon:.1f} ({DifferentialPrivacy(epsilon).get_privacy_guarantee()}) ---")
        
        dp = DifferentialPrivacy(epsilon=epsilon, random_seed=42)
        noise_stats = dp.expected_noise_magnitude()
        
        print(f"Expected noise scale: {noise_stats['scale']:.2f}")
        print(f"95% of noise within: ±{noise_stats['approx_95_percent_bounds']:.2f}")
        print()
        
        # Generate 5 noisy samples to show variation
        print("Sample noisy outputs:")
        for i in range(5):
            dp_sample = DifferentialPrivacy(epsilon=epsilon)
            noisy = dp_sample.add_noise_to_row(true_counts)
            
            analyzer = UtilityAnalyzer()
            abs_err = analyzer.absolute_error(true_counts, noisy)
            rel_err = analyzer.relative_error(true_counts, noisy)
            winner_ok = analyzer.winner_preservation(true_counts, noisy)
            
            print(f"  {i+1}. {noisy} | MAE={abs_err:.2f} | MAPE={rel_err:.1f}% | Winner={'✓' if winner_ok else '✗'}")
    
    print("\n" + "=" * 70)


def demonstrate_privacy_composition():
    """
    Demonstrate privacy budget composition.
    
    Shows how privacy loss accumulates with multiple queries.
    """
    print("\n" + "=" * 70)
    print("PRIVACY BUDGET COMPOSITION DEMONSTRATION")
    print("=" * 70)
    print()
    
    epsilon_per_query = 1.0
    dp = DifferentialPrivacy(epsilon=epsilon_per_query)
    
    print(f"Privacy budget per query: ε = {epsilon_per_query}")
    print()
    print("Simulating multiple releases of CVR data:")
    
    for release in range(1, 6):
        total_loss = dp.track_privacy_loss(num_queries=1)
        print(f"  Release {release}: Total privacy loss = ε = {total_loss:.2f}")
    
    print()
    print("Note: Advanced composition theorems can provide tighter bounds,")
    print("but basic composition (sum of epsilons) is a safe upper bound.")
    print("=" * 70)


def demonstrate_k_anonymity_vs_dp():
    """
    Compare k-anonymity alone vs k-anonymity + differential privacy.
    
    Shows the difference in privacy guarantees.
    """
    print("\n" + "=" * 70)
    print("K-ANONYMITY VS. DIFFERENTIAL PRIVACY COMPARISON")
    print("=" * 70)
    print()
    
    # Scenario: Aggregated row with 10 ballots
    k = 10
    true_counts = [7, 3]  # 7 voted for A, 3 for B
    
    print(f"Scenario: Aggregated row with k={k} ballots")
    print(f"True counts: {true_counts}")
    print()
    
    print("--- K-Anonymity Only (Current Approach) ---")
    print(f"Published counts: {true_counts}")
    print("Privacy guarantee: Individual is one of {k} people")
    print("Attack scenario: If attacker knows someone in this group,")
    print("                 they can infer votes with certainty if k is small")
    print()
    
    print("--- K-Anonymity + Differential Privacy (Proposed) ---")
    epsilon = 2.0
    dp = DifferentialPrivacy(epsilon=epsilon, random_seed=42)
    noisy_counts = dp.add_noise_to_row(true_counts)
    
    print(f"Published counts: {noisy_counts}")
    print(f"Privacy guarantee: ε={epsilon} differential privacy")
    print("Attack scenario: Even if attacker knows someone in this group,")
    print(f"                 uncertainty from noise protects individual votes")
    print(f"                 Maximum privacy loss bounded by ε={epsilon}")
    print()
    print("=" * 70)


def demonstrate_audit_impact():
    """
    Demonstrate impact of DP noise on risk-limiting audits.
    
    Shows that small noise doesn't break RLA guarantees.
    """
    print("\n" + "=" * 70)
    print("IMPACT ON RISK-LIMITING AUDITS")
    print("=" * 70)
    print()
    
    # Simulate election with clear winner
    total_ballots = 100
    true_winner_votes = 60
    true_loser_votes = 40
    margin = true_winner_votes - true_loser_votes
    
    print(f"Election scenario:")
    print(f"  Total ballots: {total_ballots}")
    print(f"  Winner votes: {true_winner_votes}")
    print(f"  Loser votes: {true_loser_votes}")
    print(f"  Margin: {margin} votes ({margin/total_ballots*100:.1f}%)")
    print()
    
    epsilon = 2.0
    print(f"Applying DP noise with ε={epsilon}:")
    print()
    
    # Simulate 1000 trials
    winner_preserved = 0
    margin_changes = []
    
    for _ in range(1000):
        dp = DifferentialPrivacy(epsilon=epsilon)
        noisy_winner = dp.add_noise_to_count(true_winner_votes)
        noisy_loser = dp.add_noise_to_count(true_loser_votes)
        
        if noisy_winner > noisy_loser:
            winner_preserved += 1
        
        noisy_margin = noisy_winner - noisy_loser
        margin_changes.append(abs(margin - noisy_margin))
    
    avg_margin_change = sum(margin_changes) / len(margin_changes)
    
    print(f"  Winner preserved: {winner_preserved}/1000 trials ({winner_preserved/10:.1f}%)")
    print(f"  Average margin change: {avg_margin_change:.2f} votes")
    print()
    
    print("Conclusion:")
    if winner_preserved >= 990:
        print("  ✓ DP noise does NOT affect election outcome")
        print("  ✓ RLA risk calculations would need minor adjustment")
    elif winner_preserved >= 950:
        print("  ~ DP noise rarely affects outcome")
        print("  ~ RLA should account for noise variance")
    else:
        print("  ✗ DP noise may affect outcome - epsilon too small or margin too tight")
        print("  ✗ Consider larger epsilon or different approach")
    
    print("=" * 70)


if __name__ == "__main__":
    """Run all demonstrations."""
    
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  DIFFERENTIAL PRIVACY FOR CVR ANONYMIZATION".center(68) + "║")
    print("║" + "  Proof of Concept Demonstration".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    
    demonstrate_dp_noise()
    demonstrate_privacy_composition()
    demonstrate_k_anonymity_vs_dp()
    demonstrate_audit_impact()
    
    print("\n" + "=" * 70)
    print("SUMMARY AND RECOMMENDATIONS")
    print("=" * 70)
    print()
    print("Key Findings:")
    print("  1. Differential Privacy provides formal, quantifiable privacy guarantees")
    print("  2. With ε=2.0, noise is typically ±1-2 votes per candidate")
    print("  3. Winner is preserved in >99% of cases for reasonable margins")
    print("  4. DP complements k-anonymity by protecting against auxiliary info")
    print()
    print("Recommended Implementation:")
    print("  • Add optional --differential-privacy flag to anonymize_cvr.py")
    print("  • Default ε=2.0 (moderate privacy, low noise)")
    print("  • Allow configuration via --epsilon parameter")
    print("  • Document noise bounds for auditors")
    print("  • Track cumulative privacy loss across releases")
    print()
    print("Next Steps:")
    print("  1. Integrate with anonymize_cvr.py as optional feature")
    print("  2. Create test suite measuring privacy/utility tradeoffs")
    print("  3. Consult with election officials on acceptable ε values")
    print("  4. Document DP implications for Risk-Limiting Audits")
    print()
    print("=" * 70)
    print()
