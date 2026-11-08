#!/usr/bin/env python3
"""
CLI entry point for batch matching functionality.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from anonymize_cvr.batch_cli import main

if __name__ == "__main__":
    main()





