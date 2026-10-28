#!/usr/bin/env python3
"""
CLI interface for batch matching functionality.
"""

import json
import sys
from typing import Dict, Optional, Tuple

try:
    import typer
    from typer import Option
except ImportError:
    print("Error: typer is required. Install with: pip install typer", file=sys.stderr)
    sys.exit(1)

from .batch_matching import compare_batches, find_batches_in_cvr, compute_batch_signature

app = typer.Typer(help="Batch matching tool for comparing batches of ballots")


def format_contest_schema_diff(schema_a: set, schema_b: set) -> str:
    """Format contest schema differences in a readable way."""
    only_a = sorted(schema_a - schema_b)
    only_b = sorted(schema_b - schema_a)
    common = sorted(schema_a & schema_b)
    
    lines = []
    if only_a:
        lines.append(f"  Only in Batch A ({len(only_a)}):")
        for contest in only_a[:5]:  # Limit to first 5
            lines.append(f"    - {contest}")
        if len(only_a) > 5:
            lines.append(f"    ... and {len(only_a) - 5} more")
    
    if only_b:
        lines.append(f"  Only in Batch B ({len(only_b)}):")
        for contest in only_b[:5]:  # Limit to first 5
            lines.append(f"    - {contest}")
        if len(only_b) > 5:
            lines.append(f"    ... and {len(only_b) - 5} more")
    
    if not only_a and not only_b:
        lines.append("  - identical")
    elif common:
        lines.append(f"  Common contests ({len(common)}): {len(common)} shared")
    
    return "\n".join(lines) if lines else "  - identical"


def format_style_histogram_side_by_side(hist_a: dict, hist_b: dict, batch_a_label: str, batch_b_label: str) -> str:
    """Format style histogram comparison side-by-side."""
    hist_a_sorted = dict(sorted(hist_a.items()))
    hist_b_sorted = dict(sorted(hist_b.items()))
    
    if hist_a_sorted == hist_b_sorted:
        # Format nicely for identical case
        style_str = ", ".join(f"{k}: {v}" for k, v in hist_a_sorted.items())
        return f"  Batch {batch_a_label}: {style_str}, Batch {batch_b_label} - identical"
    
    # Show side-by-side for differences
    all_styles = sorted(set(hist_a.keys()) | set(hist_b.keys()))
    lines = [f"  Batch {batch_a_label}: {dict(sorted(hist_a.items()))}"]
    lines.append(f"  Batch {batch_b_label}: {dict(sorted(hist_b.items()))}")
    lines.append("  Differences:")
    for style in all_styles:
        count_a = hist_a.get(style, 0)
        count_b = hist_b.get(style, 0)
        if count_a != count_b:
            lines.append(f"    {style}: Batch {batch_a_label} = {count_a}, Batch {batch_b_label} = {count_b}")
    
    return "\n".join(lines)


def format_result(result, cvr_file: Optional[str] = None) -> str:
    """Format comparison result for display with improved readability."""
    batch_a_label = f"{result.batch_a[0]}-{result.batch_a[1]}"
    batch_b_label = f"{result.batch_b[0]}-{result.batch_b[1]}"
    
    lines = [
        f"Batch A: {result.batch_a[0]}:{result.batch_a[1]}",
        f"Batch B: {result.batch_b[0]}:{result.batch_b[1]}",
        f"Same Batch: {result.is_same_batch}",
        f"Match Score: {result.confidence:.2%}",
        f"Match Type: {result.match_type}",
    ]

    if result.elimination_reason:
        lines.append(f"Elimination Reason: {result.elimination_reason}")

    # Get signatures if cvr_file provided for detailed comparison
    sig_a = None
    sig_b = None
    if cvr_file:
        try:
            sig_a = compute_batch_signature(cvr_file, result.batch_a[0], result.batch_a[1])
            sig_b = compute_batch_signature(cvr_file, result.batch_b[0], result.batch_b[1])
        except Exception:
            pass  # Fall back to basic formatting
    
    lines.append("")
    lines.append("Cardinality:")
    if sig_a and sig_b:
        if sig_a.cardinality == sig_b.cardinality:
            lines.append(f"  Batch {batch_a_label}: {sig_a.cardinality} ballots, Batch {batch_b_label} - identical")
        else:
            lines.append(f"  Batch {batch_a_label}: {sig_a.cardinality} ballots, Batch {batch_b_label}: {sig_b.cardinality} ballots")
    else:
        lines.append(f"  Match: {result.cardinality_match}")
    
    lines.append("")
    lines.append("Style Histogram:")
    if sig_a and sig_b:
        lines.append(format_style_histogram_side_by_side(
            sig_a.style_histogram, sig_b.style_histogram, batch_a_label, batch_b_label
        ))
    else:
        lines.append(f"  Match: {result.style_histogram_match}")
    
    lines.append("")
    lines.append("Contest Schema:")
    if sig_a and sig_b:
        lines.append(format_contest_schema_diff(sig_a.contest_schema, sig_b.contest_schema))
    else:
        lines.append(f"  Match: {result.contest_schema_match}")
    
    lines.append("")
    lines.append("Hash Matching:")
    lines.append(f"  Strict Hash Match: {result.strict_hash_match}")
    if result.fuzzy_match_rate is not None:
        lines.append(f"  Fuzzy Match Rate: {result.fuzzy_match_rate:.2%}")
    if result.mean_hamming_distance is not None:
        lines.append(f"  Mean Hamming Distance: {result.mean_hamming_distance:.6f}")
    
    lines.append("")
    lines.append("Similarity Metrics:")
    if result.sketch_distance is not None:
        lines.append(f"  Sketch Distance: {result.sketch_distance:.6f}")
    if result.lcs_ratio is not None:
        lines.append(f"  LCS Ratio: {result.lcs_ratio:.2%} (length: {result.lcs_length})")

    return "\n".join(lines)


@app.command()
def compare(
    cvr_file: str = Option(..., "--cvr-file", "-f", help="Path to CVR file (CSV or parquet)"),
    batch_a: str = Option(..., "--batch-a", "-a", help="First batch (format: tabulator:batch or PARQUET:precinct)"),
    batch_b: str = Option(..., "--batch-b", "-b", help="Second batch (format: tabulator:batch or PARQUET:precinct)"),
    json_output: bool = Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Compare two batches to determine if they contain the same physical ballots.

    Examples:
        # Compare batches in CSV file
        batch-cli compare -f file.csv -a "103:1" -b "103:2"

        # Compare precincts in parquet file
        batch-cli compare -f file.parquet -a "PARQUET:4356406001" -b "PARQUET:4356406002"
    """
    try:
        # Parse batch identifiers
        parts_a = batch_a.split(":", 1)
        if len(parts_a) != 2:
            typer.echo(f"Error: batch-a must be in format 'tabulator:batch', got '{batch_a}'", err=True)
            raise typer.Exit(1)
        tabulator_a, batch_id_a = parts_a

        parts_b = batch_b.split(":", 1)
        if len(parts_b) != 2:
            typer.echo(f"Error: batch-b must be in format 'tabulator:batch', got '{batch_b}'", err=True)
            raise typer.Exit(1)
        tabulator_b, batch_id_b = parts_b

        # Compare batches
        result = compare_batches(cvr_file, tabulator_a, batch_id_a, tabulator_b, batch_id_b)

        if json_output:
            # Output as JSON
            output = {
                "batch_a": {"tabulator": result.batch_a[0], "batch": result.batch_a[1]},
                "batch_b": {"tabulator": result.batch_b[0], "batch": result.batch_b[1]},
                "is_same_batch": result.is_same_batch,
                "confidence": result.confidence,
                "match_type": result.match_type,
                "elimination_reason": result.elimination_reason,
                "metrics": {
                    "cardinality_match": result.cardinality_match,
                    "style_histogram_match": result.style_histogram_match,
                    "contest_schema_match": result.contest_schema_match,
                    "strict_hash_match": result.strict_hash_match,
                    "fuzzy_match_rate": result.fuzzy_match_rate,
                    "mean_hamming_distance": result.mean_hamming_distance,
                    "sketch_distance": result.sketch_distance,
                    "lcs_length": result.lcs_length,
                    "lcs_ratio": result.lcs_ratio,
                },
            }
            print(json.dumps(output, indent=2))
        else:
            # Output as formatted text
            print(format_result(result, cvr_file))

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def list_batches(
    cvr_file: str = Option(..., "--cvr-file", "-f", help="Path to CVR file (CSV or parquet)"),
    json_output: bool = Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    List all batches (or precincts for parquet files) in a CVR file.

    Examples:
        # List batches in CSV file
        batch-cli list-batches -f file.csv

        # List precincts in parquet file
        batch-cli list-batches -f file.parquet
    """
    try:
        batches = find_batches_in_cvr(cvr_file)

        if json_output:
            output = [
                {"tabulator": tab, "batch": batch} for tab, batch in batches
            ]
            print(json.dumps(output, indent=2))
        else:
            print(f"Found {len(batches)} batch(es):")
            for tabulator, batch_id in batches:
                print(f"  {tabulator}:{batch_id}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def compare_all_pairs(
    cvr_file: str = Option(..., "--cvr-file", "-f", help="Path to CVR file (CSV or parquet)"),
    json_output: bool = Option(False, "--json", "-j", help="Output as JSON"),
    min_confidence: float = Option(0.0, "--min-confidence", "-m", help="Minimum confidence to report"),
):
    """
    Compare all pairs of batches in a CVR file (optimized to avoid unnecessary comparisons).

    Uses indexing to quickly find potential matches before doing full comparison.

    Examples:
        # Compare all pairs
        batch-cli compare-all-pairs -f file.csv

        # Only show matches with confidence >= 0.8
        batch-cli compare-all-pairs -f file.csv --min-confidence 0.8
    """
    try:
        from .batch_matching import compute_batch_signature, quick_eliminate
        from collections import defaultdict

        batches = find_batches_in_cvr(cvr_file)
        typer.echo(f"Found {len(batches)} batches. Computing signatures...", err=True)

        # Pre-compute all batch signatures
        signatures = {}
        for tab, batch_id in batches:
            try:
                sig = compute_batch_signature(cvr_file, tab, batch_id)
                signatures[(tab, batch_id)] = sig
            except Exception as e:
                typer.echo(f"Warning: Failed to compute signature for {tab}:{batch_id}: {e}", err=True)

        typer.echo(f"Computed {len(signatures)} signatures. Finding potential matches...", err=True)

        # Index batches by cardinality, style histogram, and contest schema for quick filtering
        cardinality_index: Dict[int, List[Tuple[str, str]]] = defaultdict(list)
        style_index: Dict[tuple, List[Tuple[str, str]]] = defaultdict(list)
        schema_index: Dict[frozenset, List[Tuple[str, str]]] = defaultdict(list)

        for batch_key, sig in signatures.items():
            cardinality_index[sig.cardinality].append(batch_key)
            style_tuple = tuple(sorted(sig.style_histogram.items()))
            style_index[style_tuple].append(batch_key)
            schema_index[frozenset(sig.contest_schema)].append(batch_key)

        # Find candidate pairs that pass quick elimination
        candidate_pairs = set()
        for batch_key, sig in signatures.items():
            # Only compare with batches that have same cardinality, styles, and schema
            same_card = cardinality_index[sig.cardinality]
            style_tuple = tuple(sorted(sig.style_histogram.items()))
            same_style = style_index[style_tuple]
            same_schema = schema_index[frozenset(sig.contest_schema)]

            # Intersection of all three gives candidates
            candidates = set(same_card) & set(same_style) & set(same_schema)
            candidates.discard(batch_key)  # Remove self

            for candidate in candidates:
                # Add as ordered pair to avoid duplicates
                pair = tuple(sorted([batch_key, candidate]))
                candidate_pairs.add(pair)

        typer.echo(f"Found {len(candidate_pairs)} candidate pairs (out of {len(batches) * (len(batches) - 1) // 2} possible). Comparing...", err=True)

        # Compare candidate pairs
        results = []
        for i, (batch_a_key, batch_b_key) in enumerate(sorted(candidate_pairs)):
            if (i + 1) % 100 == 0:
                typer.echo(f"  Compared {i + 1}/{len(candidate_pairs)} pairs...", err=True)

            sig_a = signatures[batch_a_key]
            sig_b = signatures[batch_b_key]

            # Quick elimination (should pass, but double-check)
            elimination_reason = quick_eliminate(sig_a, sig_b)
            if elimination_reason:
                continue

            # Do full comparison
            result = compare_batches(
                cvr_file,
                batch_a_key[0],
                batch_a_key[1],
                batch_b_key[0],
                batch_b_key[1],
            )
            if result.confidence >= min_confidence:
                results.append(result)

        typer.echo(f"Completed. Found {len(results)} matching pairs.", err=True)

        if json_output:
            output = [
                {
                    "batch_a": {"tabulator": r.batch_a[0], "batch": r.batch_a[1]},
                    "batch_b": {"tabulator": r.batch_b[0], "batch": r.batch_b[1]},
                    "is_same_batch": r.is_same_batch,
                    "confidence": r.confidence,
                    "match_type": r.match_type,
                }
                for r in results
            ]
            print(json.dumps(output, indent=2))
        else:
            print(f"\nFound {len(results)} matching pairs (confidence >= {min_confidence:.0%}):")
            for result in sorted(results, key=lambda r: r.confidence, reverse=True):
                print(f"\n{format_result(result, cvr_file)}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def find_closest(
    cvr_file: str = Option(..., "--cvr-file", "-f", help="Path to CVR file (CSV or parquet)"),
    top_n: int = Option(10, "--top-n", "-n", help="Number of closest pairs to find"),
    json_output: bool = Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Find the N closest batch pairs and provide detailed comparison.

    Examples:
        # Find top 10 closest pairs
        batch-cli find-closest -f file.csv

        # Find top 5 closest pairs
        batch-cli find-closest -f file.csv --top-n 5
    """
    try:
        from .batch_matching import compute_batch_signature, quick_eliminate
        from collections import defaultdict
        import heapq

        batches = find_batches_in_cvr(cvr_file)
        typer.echo(f"Found {len(batches)} batches. Computing signatures...", err=True)

        # Pre-compute all batch signatures
        signatures = {}
        for tab, batch_id in batches:
            try:
                sig = compute_batch_signature(cvr_file, tab, batch_id)
                signatures[(tab, batch_id)] = sig
            except Exception as e:
                typer.echo(f"Warning: Failed to compute signature for {tab}:{batch_id}: {e}", err=True)

        typer.echo(f"Computed {len(signatures)} signatures. Finding closest pairs...", err=True)

        # Index batches by cardinality, style histogram, and contest schema
        cardinality_index: Dict[int, List[Tuple[str, str]]] = defaultdict(list)
        style_index: Dict[tuple, List[Tuple[str, str]]] = defaultdict(list)
        schema_index: Dict[frozenset, List[Tuple[str, str]]] = defaultdict(list)

        for batch_key, sig in signatures.items():
            cardinality_index[sig.cardinality].append(batch_key)
            style_tuple = tuple(sorted(sig.style_histogram.items()))
            style_index[style_tuple].append(batch_key)
            schema_index[frozenset(sig.contest_schema)].append(batch_key)

        # Find candidate pairs
        candidate_pairs = set()
        for batch_key, sig in signatures.items():
            same_card = cardinality_index[sig.cardinality]
            style_tuple = tuple(sorted(sig.style_histogram.items()))
            same_style = style_index[style_tuple]
            same_schema = schema_index[frozenset(sig.contest_schema)]

            candidates = set(same_card) & set(same_style) & set(same_schema)
            candidates.discard(batch_key)

            for candidate in candidates:
                pair = tuple(sorted([batch_key, candidate]))
                candidate_pairs.add(pair)

        typer.echo(f"Found {len(candidate_pairs)} candidate pairs. Comparing...", err=True)

        # Compare all candidate pairs and keep top N by confidence
        heap = []  # Min-heap to keep top N: (confidence, counter, result)
        compared = 0
        counter = 0  # Counter to break ties in heap comparison

        # Import comparison functions
        from .batch_matching import (
            strict_match,
            fuzzy_match,
            sketch_consistency,
            compute_lcs,
            BatchComparisonResult,
        )

        for batch_a_key, batch_b_key in sorted(candidate_pairs):
            compared += 1
            if compared % 100 == 0:
                typer.echo(f"  Compared {compared}/{len(candidate_pairs)} pairs...", err=True)

            sig_a = signatures[batch_a_key]
            sig_b = signatures[batch_b_key]

            elimination_reason = quick_eliminate(sig_a, sig_b)
            if elimination_reason:
                continue

            # Strict hash match
            strict_hash_match = strict_match(sig_a, sig_b)
            if strict_hash_match:
                result = BatchComparisonResult(
                    batch_a=batch_a_key,
                    batch_b=batch_b_key,
                    is_same_batch=True,
                    confidence=1.0,
                    match_type="strict",
                    elimination_reason=None,
                    cardinality_match=True,
                    style_histogram_match=True,
                    contest_schema_match=True,
                    strict_hash_match=True,
                )
            else:
                # Fuzzy matching
                is_fuzzy_match, match_rate, mean_hamming = fuzzy_match(sig_a, sig_b)
                sketch_dist = sketch_consistency(sig_a, sig_b)
                lcs_length, lcs_ratio = compute_lcs(sig_a, sig_b)

                # Determine final result
                if is_fuzzy_match and sketch_dist < 0.1 and lcs_ratio > 0.9:
                    confidence = 0.95
                    is_same = True
                elif is_fuzzy_match and sketch_dist < 0.2 and lcs_ratio > 0.8:
                    confidence = 0.85
                    is_same = True
                elif match_rate > 0.9 and mean_hamming < 0.5:
                    confidence = 0.7
                    is_same = True
                else:
                    confidence = max(0.0, match_rate - (mean_hamming * 0.5))
                    is_same = False

                result = BatchComparisonResult(
                    batch_a=batch_a_key,
                    batch_b=batch_b_key,
                    is_same_batch=is_same,
                    confidence=confidence,
                    match_type="fuzzy" if is_same else "none",
                    elimination_reason=None,
                    cardinality_match=True,
                    style_histogram_match=True,
                    contest_schema_match=True,
                    strict_hash_match=False,
                    fuzzy_match_rate=match_rate,
                    mean_hamming_distance=mean_hamming,
                    sketch_distance=sketch_dist,
                    lcs_length=lcs_length,
                    lcs_ratio=lcs_ratio,
                )

            # Use confidence for min-heap (we want highest confidence)
            # Add counter to break ties when confidence values are equal
            counter += 1
            if len(heap) < top_n:
                heapq.heappush(heap, (result.confidence, counter, result))
            elif result.confidence > heap[0][0]:
                heapq.heapreplace(heap, (result.confidence, counter, result))

        # Extract top N results (sorted by confidence descending)
        top_results = sorted([r for _, _, r in heap], key=lambda r: r.confidence, reverse=True)

        typer.echo(f"Found {len(top_results)} closest pairs.", err=True)

        if json_output:
            output = []
            for result in top_results:
                sig_a = signatures[result.batch_a]
                sig_b = signatures[result.batch_b]
                output.append({
                    "batch_a": {"tabulator": result.batch_a[0], "batch": result.batch_a[1]},
                    "batch_b": {"tabulator": result.batch_b[0], "batch": result.batch_b[1]},
                    "is_same_batch": result.is_same_batch,
                    "confidence": result.confidence,
                    "match_type": result.match_type,
                    "metrics": {
                        "cardinality_match": result.cardinality_match,
                        "cardinality_a": sig_a.cardinality,
                        "cardinality_b": sig_b.cardinality,
                        "style_histogram_match": result.style_histogram_match,
                        "style_histogram_a": sig_a.style_histogram,
                        "style_histogram_b": sig_b.style_histogram,
                        "contest_schema_match": result.contest_schema_match,
                        "contest_schema_a": sorted(sig_a.contest_schema),
                        "contest_schema_b": sorted(sig_b.contest_schema),
                        "strict_hash_match": result.strict_hash_match,
                        "fuzzy_match_rate": result.fuzzy_match_rate,
                        "mean_hamming_distance": result.mean_hamming_distance,
                        "sketch_distance": result.sketch_distance,
                        "lcs_length": result.lcs_length,
                        "lcs_ratio": result.lcs_ratio,
                    },
                })
            print(json.dumps(output, indent=2))
        else:
            print(f"\nTop {len(top_results)} Closest Batch Pairs:\n")
            for idx, result in enumerate(top_results, 1):
                sig_a = signatures[result.batch_a]
                sig_b = signatures[result.batch_b]
                
                print("=" * 80)
                print(f"#{idx}: {result.batch_a[0]}:{result.batch_a[1]} vs {result.batch_b[0]}:{result.batch_b[1]}")
                print("=" * 80)
                print(f"Match Score: {result.confidence:.2%}")
                print(f"Same Batch: {result.is_same_batch}")
                print(f"Match Type: {result.match_type}")
                print()
                
                batch_a_label = f"{result.batch_a[0]}-{result.batch_a[1]}"
                batch_b_label = f"{result.batch_b[0]}-{result.batch_b[1]}"
                
                print("Cardinality:")
                if sig_a.cardinality == sig_b.cardinality:
                    print(f"  Batch {batch_a_label}: {sig_a.cardinality} ballots, Batch {batch_b_label} - identical")
                else:
                    print(f"  Batch {batch_a_label}: {sig_a.cardinality} ballots, Batch {batch_b_label}: {sig_b.cardinality} ballots")
                print()
                
                print("Style Histogram:")
                print(format_style_histogram_side_by_side(
                    sig_a.style_histogram, sig_b.style_histogram, batch_a_label, batch_b_label
                ))
                print()
                
                print("Contest Schema:")
                print(format_contest_schema_diff(sig_a.contest_schema, sig_b.contest_schema))
                print()
                
                print("Hash Matching:")
                print(f"  Strict Hash Match: {result.strict_hash_match}")
                if result.fuzzy_match_rate is not None:
                    print(f"  Fuzzy Match Rate: {result.fuzzy_match_rate:.2%}")
                if result.mean_hamming_distance is not None:
                    print(f"  Mean Hamming Distance: {result.mean_hamming_distance:.4f}")
                print()
                
                print("Similarity Metrics:")
                if result.sketch_distance is not None:
                    print(f"  Sketch Distance: {result.sketch_distance:.6f} (Jensen-Shannon divergence)")
                if result.mean_hamming_distance is not None:
                    print(f"  Mean Hamming Distance: {result.mean_hamming_distance:.6f} (normalized)")
                if result.lcs_ratio is not None:
                    print(f"  LCS Ratio: {result.lcs_ratio:.2%} (length: {result.lcs_length})")
                print()

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()

