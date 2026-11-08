# SimHash Implementation Comparison

## Summary

Comparison between local SimHash implementation and `python-simhash` library from PyPI.

## Benchmark Results

### Performance

**Small scale (25 ballots):**
- Local: 0.0017s (14,978 ballots/sec)
- PyPI: 0.0001s (385,506 ballots/sec)
- **PyPI is 23.88x FASTER**

**Larger scale (65 ballots):**
- Local: 0.0039s (16,823 ballots/sec)
- PyPI: 0.0001s (449,143 ballots/sec)
- **PyPI is 26.70x FASTER**

### Similarity Detection

Both implementations correctly detect similarity:
- **Similar ballots**: Small Hamming distances (7-9 bits for 1-byte difference)
- **Different ballots**: Large Hamming distances (26-31 bits for completely different ballots)
- **Distance patterns**: Both show similar relative distances between ballots

### Key Differences

1. **Hash values differ**: Expected - different algorithms produce different hashes
2. **Distance calculations**: Both work correctly for similarity detection
3. **API**: 
   - Local: Works directly with bytes
   - PyPI: Requires string tokens (we convert bytes to hex strings)

## Recommendation

### ✅ **ADD python-simhash as a dependency**

**Reasons:**
1. **Performance**: 24-27x faster, which matters for large-scale batch comparisons
2. **Correctness**: Both implementations correctly detect similar/different ballots
3. **Maintenance**: Well-maintained Rust-based library reduces maintenance burden
4. **Safety**: Rust implementation provides memory safety guarantees

**Trade-offs:**
- Adds external dependency
- Requires converting bytes to hex strings (minor overhead)
- Hash values differ (but distances work correctly)

### Implementation Strategy

1. **Keep local implementation as fallback** if PyPI library unavailable
2. **Use PyPI library by default** for better performance
3. **Maintain compatibility**: Both should work with existing code

## Migration Path

1. Add `python-simhash` to dependencies
2. Update `simhash.py` to use PyPI library with local fallback
3. Update token conversion to use hex strings
4. Test with existing batch matching code
5. Benchmark end-to-end performance improvement

## Code Changes Needed

```python
# In simhash.py
try:
    import simhash as pypi_simhash
    USE_PYPI = True
except ImportError:
    USE_PYPI = False

def simhash(bitstring: bytes, hash_bits: int = 64) -> int:
    if USE_PYPI:
        # Convert bytes to hex string tokens
        tokens = [bitstring[i:i+8].hex() 
                  for i in range(0, len(bitstring), 8) 
                  if bitstring[i:i+8]]
        return pypi_simhash.simhash(tokens, hasher="xxh3")
    else:
        # Use local implementation
        return local_simhash_impl(bitstring, hash_bits)
```

## Expected Performance Impact

For a typical batch comparison with 25 ballots:
- **Current**: ~0.04ms per ballot × 25 = 1ms per batch
- **With PyPI**: ~0.002ms per ballot × 25 = 0.05ms per batch
- **Improvement**: ~20x faster per batch comparison

For comparing all pairs in a file with 881 batches:
- **Current**: ~881 batches × 1ms = 881ms (0.88s) just for SimHash
- **With PyPI**: ~881 batches × 0.05ms = 44ms (0.04s)
- **Improvement**: ~20x faster, saving ~0.84 seconds per full comparison





