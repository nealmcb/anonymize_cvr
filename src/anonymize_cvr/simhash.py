#!/usr/bin/env python3
"""
SimHash implementation for fuzzy matching of ballots.

SimHash is a locality-sensitive hashing technique that produces similar hashes
for similar inputs. This is useful for detecting near-duplicate ballots that may
have minor scanner variations.

Uses python-simhash library (PyPI) for performance, with local fallback.
"""

import hashlib
from typing import List, Optional

# Try to import PyPI library, fallback to local implementation
try:
    import simhash as pypi_simhash

    _PYPI_SIMHASH_AVAILABLE = True
except ImportError:
    _PYPI_SIMHASH_AVAILABLE = False


def _bitstring_to_tokens(bitstring: bytes) -> List[str]:
    """
    Convert bitstring to hex string tokens for python-simhash library.

    Args:
        bitstring: Byte sequence

    Returns:
        List of hex string tokens (8-byte chunks)
    """
    tokens = []
    chunk_size = 8
    for i in range(0, len(bitstring), chunk_size):
        chunk = bitstring[i : i + chunk_size]
        if chunk:
            tokens.append(chunk.hex())
    return tokens


def _local_simhash_impl(bitstring: bytes, hash_bits: int = 64) -> int:
    """
    Local SimHash implementation (fallback when PyPI library unavailable).

    Args:
        bitstring: Byte sequence representing ballot votes
        hash_bits: Number of bits in the hash (default 64)

    Returns:
        SimHash value as integer
    """
    if not bitstring:
        return 0

    # Split bitstring into features using sliding windows
    # Window size: 8 bytes, stride: 4 bytes
    window_size = 8
    stride = 4

    features: List[bytes] = []
    for i in range(0, len(bitstring) - window_size + 1, stride):
        features.append(bitstring[i : i + window_size])

    # If bitstring is shorter than window_size, use the whole thing
    if not features:
        features = [bitstring]

    # Initialize vector
    vector = [0] * hash_bits

    # Process each feature
    for feature in features:
        # Compute hash and truncate to hash_bits
        hash_bytes = hashlib.sha256(feature).digest()
        # Convert to integer and extract hash_bits bits
        hash_int = int.from_bytes(hash_bytes[: (hash_bits + 7) // 8], byteorder="big")
        # Truncate to hash_bits bits
        hash_int = hash_int & ((1 << hash_bits) - 1)

        # Update vector based on hash bits
        for i in range(hash_bits):
            if hash_int & (1 << i):
                vector[i] += 1
            else:
                vector[i] -= 1

    # Convert vector to integer
    result = 0
    for i in range(hash_bits):
        if vector[i] > 0:
            result |= 1 << i

    return result


def simhash(bitstring: bytes, hash_bits: int = 64) -> int:
    """
    Compute SimHash signature for a bitstring.

    Uses python-simhash library (PyPI) if available for better performance,
    otherwise falls back to local implementation.

    Args:
        bitstring: Byte sequence representing ballot votes
        hash_bits: Number of bits in the hash (default 64, must be 64 for PyPI)

    Returns:
        SimHash value as integer
    """
    if not bitstring:
        return 0

    # Use PyPI library if available (much faster)
    if _PYPI_SIMHASH_AVAILABLE and hash_bits == 64:
        tokens = _bitstring_to_tokens(bitstring)
        return pypi_simhash.simhash(tokens, hasher="xxh3")

    # Fallback to local implementation
    return _local_simhash_impl(bitstring, hash_bits)


def simhash_distance(simhash_a: int, simhash_b: int) -> int:
    """
    Compute Hamming distance between two SimHash values.

    Uses python-simhash library if available for better performance,
    otherwise uses local implementation.

    Args:
        simhash_a: First SimHash value
        simhash_b: Second SimHash value

    Returns:
        Number of differing bits
    """
    if _PYPI_SIMHASH_AVAILABLE:
        return pypi_simhash.hamming_distance(simhash_a, simhash_b)
    return bin(simhash_a ^ simhash_b).count("1")


def simhash_similarity(simhash_a: int, simhash_b: int, hash_bits: int = 64) -> float:
    """
    Compute similarity score (0.0 to 1.0) between two SimHash values.

    Args:
        simhash_a: First SimHash value
        simhash_b: Second SimHash value
        hash_bits: Number of bits in the hash (default 64)

    Returns:
        Similarity score (1.0 = identical, 0.0 = completely different)
    """
    distance = simhash_distance(simhash_a, simhash_b)
    return 1.0 - (distance / hash_bits)


def get_simhash_bucket(simhash_value: int, k: int = 8) -> int:
    """
    Get bucket/cluster ID for a SimHash value using high k bits.

    This is useful for grouping similar ballots into clusters.

    Args:
        simhash_value: SimHash value
        k: Number of high bits to use for bucketing (default 8)

    Returns:
        Bucket ID (integer)
    """
    # Extract high k bits
    return simhash_value >> (64 - k) if k < 64 else simhash_value

