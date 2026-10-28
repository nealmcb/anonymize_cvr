#!/usr/bin/env python3
"""
Benchmark comparison between local SimHash implementation and python-simhash library.
"""

import time
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from anonymize_cvr.simhash import simhash as local_simhash
from anonymize_cvr.fingerprint_utils import build_ballot_bitstring, find_vote_column_start
from anonymize_cvr.batch_matching import extract_batch_ballots

try:
    import simhash as pypi_simhash
    PYPI_AVAILABLE = True
except ImportError:
    PYPI_AVAILABLE = False
    print("Warning: python-simhash not installed. Install with: pip install python-simhash")


def benchmark_local_simhash(bitstrings):
    """Benchmark local SimHash implementation."""
    start = time.time()
    results = []
    for bitstring in bitstrings:
        result = local_simhash(bitstring)
        results.append(result)
    elapsed = time.time() - start
    return elapsed, results


def benchmark_pypi_simhash(bitstrings):
    """Benchmark python-simhash library."""
    if not PYPI_AVAILABLE:
        return None, None
    
    start = time.time()
    results = []
    for bitstring in bitstrings:
        # python-simhash expects string tokens
        # Convert bitstring to hex string tokens (chunks)
        tokens = []
        chunk_size = 8
        for i in range(0, len(bitstring), chunk_size):
            chunk = bitstring[i:i+chunk_size]
            if chunk:
                # Convert bytes to hex string for python-simhash
                tokens.append(chunk.hex())
        
        # python-simhash API: simhash(tokens, hasher="xxh3")
        sh_value = pypi_simhash.simhash(tokens, hasher="xxh3")
        results.append(sh_value)
    elapsed = time.time() - start
    return elapsed, results


def compare_results(local_results, pypi_results):
    """Compare results from both implementations."""
    if not pypi_results:
        return
    
    print("\nComparing results:")
    matches = 0
    total = min(len(local_results), len(pypi_results))
    
    for i in range(min(10, total)):  # Compare first 10
        local_val = local_results[i]
        pypi_val = pypi_results[i]
        match = (local_val == pypi_val)
        if match:
            matches += 1
        print(f"  Ballot {i+1}: Local={local_val}, PyPI={pypi_val}, Match={match}")
    
    print(f"\nExact matches in first 10: {matches}/10")
    print("\nNote: Implementations may differ due to different algorithms,")
    print("but both should produce similar hashes for similar inputs.")


def main():
    """Run benchmarks."""
    cvr_file = "test_batch_matching_laplata.csv"
    if not Path(cvr_file).exists():
        cvr_file = "neal_ignore/laplata-Modified_CVR_Export_20251113162556.csv"
    
    print(f"Using CVR file: {cvr_file}")
    print("Extracting batch ballots and computing bitstrings...")
    
    # Extract a batch
    try:
        ballot_rows, contests, choices, vote_start = extract_batch_ballots(
            cvr_file, "103", "1"
        )
    except Exception as e:
        print(f"Error extracting batch: {e}")
        return
    
    print(f"Found {len(ballot_rows)} ballots in batch 103:1")
    
    # Build bitstrings
    print("Building bitstrings...")
    bitstrings = []
    for row in ballot_rows:
        bitstring = build_ballot_bitstring(row, contests, choices, vote_start)
        bitstrings.append(bitstring)
    
    print(f"Built {len(bitstrings)} bitstrings")
    print(f"Average bitstring length: {sum(len(b) for b in bitstrings) / len(bitstrings):.0f} bytes")
    
    # Benchmark local implementation
    print("\n" + "="*60)
    print("Benchmarking LOCAL SimHash implementation...")
    print("="*60)
    local_time, local_results = benchmark_local_simhash(bitstrings)
    print(f"Time: {local_time:.4f} seconds")
    print(f"Time per ballot: {local_time/len(bitstrings)*1000:.2f} ms")
    print(f"Ballots per second: {len(bitstrings)/local_time:.0f}")
    
    # Benchmark PyPI implementation
    if PYPI_AVAILABLE:
        print("\n" + "="*60)
        print("Benchmarking PYPI python-simhash library...")
        print("="*60)
        pypi_time, pypi_results = benchmark_pypi_simhash(bitstrings)
        if pypi_time is not None:
            print(f"Time: {pypi_time:.4f} seconds")
            print(f"Time per ballot: {pypi_time/len(bitstrings)*1000:.2f} ms")
            print(f"Ballots per second: {len(bitstrings)/pypi_time:.0f}")
            
            # Compare
            print("\n" + "="*60)
            print("COMPARISON")
            print("="*60)
            print(f"Local implementation: {local_time:.4f}s ({len(bitstrings)/local_time:.0f} ballots/sec)")
            print(f"PyPI library:        {pypi_time:.4f}s ({len(bitstrings)/pypi_time:.0f} ballots/sec)")
            speedup = pypi_time / local_time if local_time > 0 else 0
            if speedup > 1:
                print(f"Local is {speedup:.2f}x FASTER")
            else:
                print(f"PyPI is {1/speedup:.2f}x FASTER")
            
            compare_results(local_results, pypi_results)
        else:
            print("Failed to benchmark PyPI implementation")
    else:
        print("\n" + "="*60)
        print("PYPI python-simhash not available")
        print("="*60)
        print("Install with: pip install python-simhash")
        print("Then run this script again to compare.")
    
    # Test with multiple batches for larger scale
    print("\n" + "="*60)
    print("LARGER SCALE TEST")
    print("="*60)
    
    # Get more bitstrings from multiple batches
    all_bitstrings = bitstrings.copy()
    for batch_id in ["2", "3", "4", "5"]:
        try:
            rows, _, _, vs = extract_batch_ballots(cvr_file, "103", batch_id)
            for row in rows[:10]:  # Take first 10 from each batch
                bs = build_ballot_bitstring(row, contests, choices, vs)
                all_bitstrings.append(bs)
        except:
            pass
    
    print(f"Testing with {len(all_bitstrings)} bitstrings...")
    
    # Benchmark local
    local_time_large, _ = benchmark_local_simhash(all_bitstrings)
    print(f"Local: {local_time_large:.4f}s ({len(all_bitstrings)/local_time_large:.0f} ballots/sec)")
    
    if PYPI_AVAILABLE:
        pypi_time_large, _ = benchmark_pypi_simhash(all_bitstrings)
        if pypi_time_large:
            print(f"PyPI:  {pypi_time_large:.4f}s ({len(all_bitstrings)/pypi_time_large:.0f} ballots/sec)")
            speedup = pypi_time_large / local_time_large if local_time_large > 0 else 0
            if speedup > 1:
                print(f"Local is {speedup:.2f}x FASTER")
            else:
                print(f"PyPI is {1/speedup:.2f}x FASTER")


if __name__ == "__main__":
    main()

