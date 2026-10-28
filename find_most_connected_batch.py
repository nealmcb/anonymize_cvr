#!/usr/bin/env python3
"""
Find the batch with the most comparisons (within 2 style mismatches)
and produce summary statistics for all pairs involving that batch.
"""

import sys
from pathlib import Path
from collections import defaultdict
import statistics

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from anonymize_cvr.batch_matching import find_batches_in_cvr, compare_batches, compute_batch_signature, quick_eliminate

cvr_file = "test_batch_matching_laplata.csv"

# Get all batches
batches = find_batches_in_cvr(cvr_file)
print(f"Total batches: {len(batches)}")

# Pre-compute signatures for efficiency
print("\nComputing batch signatures...")
signatures = {}
for i, (tab, batch_id) in enumerate(batches):
    if i % 100 == 0:
        print(f"  {i}/{len(batches)}...")
    try:
        sig = compute_batch_signature(cvr_file, tab, batch_id)
        signatures[(tab, batch_id)] = sig
    except Exception as e:
        print(f"  Warning: Failed for {tab}:{batch_id}: {e}")

print(f"Computed {len(signatures)} signatures")

# Count comparisons for each batch (only non-eliminated pairs)
print("\nFinding pairs that pass style check (within 2 mismatches)...")
batch_comparison_counts = defaultdict(int)
comparison_results = []

for i, (tab_a, batch_a) in enumerate(batches):
    if i % 50 == 0:
        print(f"  Processing batch {i+1}/{len(batches)}...")
    
    if (tab_a, batch_a) not in signatures:
        continue
    
    sig_a = signatures[(tab_a, batch_a)]
    
    for tab_b, batch_b in batches:
        if (tab_a, batch_a) >= (tab_b, batch_b):  # Avoid duplicates
            continue
        
        if (tab_b, batch_b) not in signatures:
            continue
        
        sig_b = signatures[(tab_b, batch_b)]
        
        # Quick elimination check (allows up to 2 style mismatches)
        elimination_reason = quick_eliminate(sig_a, sig_b)
        
        if elimination_reason is None:  # Passed style check
            batch_comparison_counts[(tab_a, batch_a)] += 1
            batch_comparison_counts[(tab_b, batch_b)] += 1
            
            # Do full comparison
            result = compare_batches(cvr_file, tab_a, batch_a, tab_b, batch_b)
            comparison_results.append((tab_a, batch_a, tab_b, batch_b, result))

print(f"\nFound {len(comparison_results)} pairs that pass style check")
print(f"Batches with comparisons: {len(batch_comparison_counts)}")

# Find batch with most comparisons
if batch_comparison_counts:
    most_connected = max(batch_comparison_counts.items(), key=lambda x: x[1])
    target_tab, target_batch = most_connected[0]
    print(f"\nMost connected batch: {target_tab}:{target_batch} with {most_connected[1]} comparisons")
    
    # Get all pairs involving this batch
    target_pairs = [
        (tab_a, batch_a, tab_b, batch_b, result)
        for tab_a, batch_a, tab_b, batch_b, result in comparison_results
        if (tab_a, batch_a) == (target_tab, target_batch) or (tab_b, batch_b) == (target_tab, target_batch)
    ]
    
    print(f"Pairs involving {target_tab}:{target_batch}: {len(target_pairs)}")
    
    # Compute summary statistics
    if target_pairs:
        confidences = [r.confidence for _, _, _, _, r in target_pairs]
        match_rates = [r.fuzzy_match_rate for _, _, _, _, r in target_pairs if r.fuzzy_match_rate is not None]
        adjusted_rates = [r.adjusted_match_rate for _, _, _, _, r in target_pairs if r.adjusted_match_rate is not None]
        hamming_dists = [r.mean_hamming_distance for _, _, _, _, r in target_pairs if r.mean_hamming_distance is not None]
        sketch_dists = [r.sketch_distance for _, _, _, _, r in target_pairs if r.sketch_distance is not None]
        lcs_ratios = [r.lcs_ratio for _, _, _, _, r in target_pairs if r.lcs_ratio is not None]
        unmatched_counts = [r.unmatched_count for _, _, _, _, r in target_pairs if r.unmatched_count is not None]
        penalties = [r.penalty for _, _, _, _, r in target_pairs if r.penalty is not None]
        
        print(f"\n{'='*80}")
        print(f"SUMMARY STATISTICS FOR ALL PAIRS INVOLVING {target_tab}:{target_batch}")
        print(f"{'='*80}")
        print(f"\nTotal pairs: {len(target_pairs)}")
        print(f"Same batch matches: {sum(1 for _, _, _, _, r in target_pairs if r.is_same_batch)}")
        print(f"Different batches: {sum(1 for _, _, _, _, r in target_pairs if not r.is_same_batch)}")
        
        if confidences:
            print(f"\nMatch Score (Confidence):")
            print(f"  Mean: {statistics.mean(confidences):.6f}")
            print(f"  StdDev: {statistics.stdev(confidences) if len(confidences) > 1 else 0:.6f}")
            print(f"  Min: {min(confidences):.6f}")
            print(f"  Max: {max(confidences):.6f}")
            print(f"  Median: {statistics.median(confidences):.6f}")
        
        if match_rates:
            print(f"\nMatch Rate:")
            print(f"  Mean: {statistics.mean(match_rates):.6f}")
            print(f"  StdDev: {statistics.stdev(match_rates) if len(match_rates) > 1 else 0:.6f}")
            print(f"  Min: {min(match_rates):.6f}")
            print(f"  Max: {max(match_rates):.6f}")
            print(f"  Median: {statistics.median(match_rates):.6f}")
        
        if adjusted_rates:
            print(f"\nAdjusted Match Rate (after penalty):")
            print(f"  Mean: {statistics.mean(adjusted_rates):.6f}")
            print(f"  StdDev: {statistics.stdev(adjusted_rates) if len(adjusted_rates) > 1 else 0:.6f}")
            print(f"  Min: {min(adjusted_rates):.6f}")
            print(f"  Max: {max(adjusted_rates):.6f}")
            print(f"  Median: {statistics.median(adjusted_rates):.6f}")
        
        if unmatched_counts:
            print(f"\nUnmatched Ballots:")
            print(f"  Mean: {statistics.mean(unmatched_counts):.6f}")
            print(f"  StdDev: {statistics.stdev(unmatched_counts) if len(unmatched_counts) > 1 else 0:.6f}")
            print(f"  Min: {min(unmatched_counts)}")
            print(f"  Max: {max(unmatched_counts)}")
            print(f"  Median: {statistics.median(unmatched_counts):.6f}")
        
        if penalties:
            print(f"\nPenalty:")
            print(f"  Mean: {statistics.mean(penalties):.6f}")
            print(f"  StdDev: {statistics.stdev(penalties) if len(penalties) > 1 else 0:.6f}")
            print(f"  Min: {min(penalties):.6f}")
            print(f"  Max: {max(penalties):.6f}")
            print(f"  Median: {statistics.median(penalties):.6f}")
        
        if hamming_dists:
            print(f"\nMean Hamming Distance:")
            print(f"  Mean: {statistics.mean(hamming_dists):.6f}")
            print(f"  StdDev: {statistics.stdev(hamming_dists) if len(hamming_dists) > 1 else 0:.6f}")
            print(f"  Min: {min(hamming_dists):.6f}")
            print(f"  Max: {max(hamming_dists):.6f}")
            print(f"  Median: {statistics.median(hamming_dists):.6f}")
        
        if sketch_dists:
            print(f"\nSketch Distance:")
            print(f"  Mean: {statistics.mean(sketch_dists):.6f}")
            print(f"  StdDev: {statistics.stdev(sketch_dists) if len(sketch_dists) > 1 else 0:.6f}")
            print(f"  Min: {min(sketch_dists):.6f}")
            print(f"  Max: {max(sketch_dists):.6f}")
            print(f"  Median: {statistics.median(sketch_dists):.6f}")
        
        if lcs_ratios:
            print(f"\nLCS Ratio:")
            print(f"  Mean: {statistics.mean(lcs_ratios):.6f}")
            print(f"  StdDev: {statistics.stdev(lcs_ratios) if len(lcs_ratios) > 1 else 0:.6f}")
            print(f"  Min: {min(lcs_ratios):.6f}")
            print(f"  Max: {max(lcs_ratios):.6f}")
            print(f"  Median: {statistics.median(lcs_ratios):.6f}")
        
        # Show top and bottom pairs
        sorted_pairs = sorted(target_pairs, key=lambda x: x[4].confidence, reverse=True)
        print(f"\n{'='*80}")
        print("TOP 5 PAIRS (by Match Score):")
        print(f"{'='*80}")
        for i, (tab_a, batch_a, tab_b, batch_b, result) in enumerate(sorted_pairs[:5], 1):
            other_batch = f"{tab_b}:{batch_b}" if (tab_a, batch_a) == (target_tab, target_batch) else f"{tab_a}:{batch_a}"
            print(f"\n{i}. {target_tab}:{target_batch} vs {other_batch}")
            print(f"   Match Score: {result.confidence:.6f}")
            if result.fuzzy_match_rate is not None:
                print(f"   Match Rate: {result.fuzzy_match_rate:.4f}")
            if result.adjusted_match_rate is not None:
                print(f"   Adjusted Rate: {result.adjusted_match_rate:.4f}")
            if result.unmatched_count is not None:
                print(f"   Unmatched: {result.unmatched_count}")
            if result.mean_hamming_distance is not None:
                print(f"   Mean Hamming: {result.mean_hamming_distance:.6f}")
            if result.sketch_distance is not None:
                print(f"   Sketch Distance: {result.sketch_distance:.6f}")
            if result.lcs_ratio is not None:
                print(f"   LCS Ratio: {result.lcs_ratio:.4f}")
            print(f"   Is Same Batch: {result.is_same_batch}")
        
        if len(sorted_pairs) > 5:
            print(f"\n{'='*80}")
            print("BOTTOM 5 PAIRS (by Match Score):")
            print(f"{'='*80}")
            for i, (tab_a, batch_a, tab_b, batch_b, result) in enumerate(sorted_pairs[-5:], len(sorted_pairs) - 4):
                other_batch = f"{tab_b}:{batch_b}" if (tab_a, batch_a) == (target_tab, target_batch) else f"{tab_a}:{batch_a}"
                print(f"\n{i}. {target_tab}:{target_batch} vs {other_batch}")
                print(f"   Match Score: {result.confidence:.6f}")
                if result.fuzzy_match_rate is not None:
                    print(f"   Match Rate: {result.fuzzy_match_rate:.4f}")
                if result.adjusted_match_rate is not None:
                    print(f"   Adjusted Rate: {result.adjusted_match_rate:.4f}")
                if result.unmatched_count is not None:
                    print(f"   Unmatched: {result.unmatched_count}")
                if result.mean_hamming_distance is not None:
                    print(f"   Mean Hamming: {result.mean_hamming_distance:.6f}")
                if result.sketch_distance is not None:
                    print(f"   Sketch Distance: {result.sketch_distance:.6f}")
                if result.lcs_ratio is not None:
                    print(f"   LCS Ratio: {result.lcs_ratio:.4f}")
                print(f"   Is Same Batch: {result.is_same_batch}")
else:
    print("No non-eliminated pairs found")





