# CVR Anonymization Tool

Software to anonymize Cast Vote Records (CVR) files to meet Colorado's requirement that styles with fewer than 10 ballots per style must be anonymized to protect voter privacy.

## Background

This tool addresses the requirement from **Colorado Open Records Act (C.R.S. 24-72-205.5)** which requires counties to cover or redact before "making available for public inspection" a voted ballot if there are fewer than 10 instances of the ballot's style in the election.

The anonymization process aggregates rare styles (those with fewer than 10 ballots) together to meet the minimum threshold while preserving ballot anonymity for Risk-Limiting Tabulation Audits.

## Status

This is alpha-quality software. Use at your own risk.

### Legal and Research Foundation

- **Colorado Open Records Act (C.R.S. 24-72-205.5)**: Requires anonymization of ballots with fewer than 10 instances per style
- **Colorado Risk-Limiting Tabulation Audit**: CVRs must be available for public audit purposes while preserving ballot anonymity
- [Colorado Risk-Limiting Tabulation Audit: Preserving Anonymity of Cast Vote Record](http://www.sos.state.co.us/pubs/rule_making/hearings/2018/20180309BranscombEtAl.pdf) (Branscomb et al., March 9, 2018) - Endorsed by John McCarthy, Neal McBurnett, Harvie Branscomb, Ron Rivest, Philip Stark

## Documentation

- **specification.md**: Detailed specification of requirements, algorithms, and implementation details
- **AGENTS.md**: Guidelines for AI agent interactions with this codebase

### Differential Privacy Research

- **DP_QUICK_REFERENCE.md**: One-page quick reference for differential privacy ⭐ START HERE
- **DIFFERENTIAL_PRIVACY_SUMMARY.md**: Executive summary and recommendations
- **differential_privacy_analysis.md**: Comprehensive analysis of DP principles and applications
- **dp_approaches_comparison.md**: Detailed comparison of 5 differential privacy approaches
- **DP_IMPLEMENTATION_GUIDE.md**: Step-by-step integration guide with code examples
- **dp_proof_of_concept.py**: Working demonstration of differential privacy mechanisms

## Tools

### anonymize_cvr.py

Anonymizes CVR files by aggregating rare styles to meet the 10-ballot minimum threshold.

**Usage:**
```bash
python3 anonymize_cvr.py input.csv output.csv
python3 anonymize_cvr.py input.csv output.csv --min-ballots 15
python3 anonymize_cvr.py input.csv output.csv --summarize
```

**Features:**
- Aggregates rare styles (< 10 ballots) with similar styles to meet threshold
- Computes descriptive style names based on contest patterns
- Detects information leakage when different CVR style names map to the same contest pattern
- Optional summary statistics with `--summarize` flag

**Options:**
- `--min-ballots`: Minimum ballots required per style (default: 10)
- `--stylecol`: Index of style column (default: 6)
- `--headerlen`: Number of header columns (default: 8)
- `--summarize, -s`: Print detailed summary of CVR statistics

### guess_votes.py

Generates test cases and analyzes how anonymization affects vote guessing probabilities.

**Usage:**
```bash
# Generate test case with default settings
python3 guess_votes.py

# Analyze an existing CVR file
python3 guess_votes.py original_cvr.csv

# Compare original vs anonymized CVR
python3 guess_votes.py original_cvr.csv --anonymized-cvr anonymized_cvr.csv
```

**Features:**
- Generates test CVR files with configurable ballot styles
- Calculates vote probabilities from:
  - Overall election results
  - Original CVR file (style-level probabilities)
  - Anonymized CVR file (aggregated probabilities)
- Generates three probability files for comparison:
  - `test_case_results_probabilities.csv`: Overall election results
  - `test_case_original_probabilities.csv`: Original CVR-refined probabilities
  - `test_case_anonymized_probabilities.csv`: Anonymized CVR-refined probabilities

**Options:**
- `original_cvr_file`: Path to original CVR file (positional, optional)
- `--anonymized-cvr, -a`: Path to anonymized CVR file
- `--election-name, -n`: Name of the election (default: "Test Election 2024")
- `--min-ballots, -m`: Minimum ballots per style to be considered common (default: 10)

## Example Workflow

1. **Anonymize a CVR file:**
   ```bash
   python3 anonymize_cvr.py original_cvr.csv anonymized_cvr.csv --summarize
   ```

2. **Generate probability analysis:**
   ```bash
   python3 guess_votes.py original_cvr.csv --anonymized-cvr anonymized_cvr.csv
   ```

3. **Compare the three probability files** to quantify how anonymization affects vote guessing accuracy.

## Differential Privacy Research

This repository includes research on applying **differential privacy** (DP) to enhance CVR anonymization beyond k-anonymity. Key findings:

- **Current approach** (k-anonymity): Aggregates rare styles to ensure ≥10 ballots per row
- **DP enhancement**: Adding calibrated noise provides formal privacy guarantees
- **Recommended**: Laplace mechanism with ε=2.0 (typical noise ±0.5 votes)
- **Impact**: Minimal effect on audits (winner preserved >99.9% of the time)

**To explore differential privacy**:

```bash
# Run interactive DP demonstrations
python3 dp_proof_of_concept.py
```

**Documentation**:
- **DIFFERENTIAL_PRIVACY_SUMMARY.md** - Start here: executive summary and recommendations
- **differential_privacy_analysis.md** - Deep dive into DP theory and applications  
- **dp_approaches_comparison.md** - Comparison of 5 different DP approaches

The research shows that differential privacy can be integrated with ~1 week of implementation effort, providing stronger privacy guarantees while maintaining audit effectiveness.

## Style Analysis

The anonymization tool automatically:
- Computes descriptive style names based on contest patterns (format: `<n><R|S><m>` where n=contest count, R=rare/S=common, m=style number)
- Maps CVR style names to descriptive style names
- Detects information leakage when different CVR style names are used for ballots with the same contest pattern
- Provides optional summaries showing vote totals and probabilities by style

## Requirements

- Python 3.12+
- Standard library only (csv, collections, typing)
