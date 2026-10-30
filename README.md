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

## Tools

### anonymize_cvr.py

Anonymizes CVR files by aggregating rare styles to meet the 10-ballot minimum threshold. Reads CVR
exports in CSV format.

**Usage:**
```bash
python3 anonymize_cvr.py input.csv output.csv
python3 anonymize_cvr.py input.csv output.csv --min-ballots 15
python3 anonymize_cvr.py --check input.csv
python3 anonymize_cvr.py input.csv output.csv --redact-on-precinct
```

**Features:**
- Reads CSV CVR exports
- `--check` reports whether redaction is needed, without writing output
- Combines all rare styles (< 10 ballots) into a single aggregation
- Ensures at least 10 ballots per contest in the aggregation
- Adds contrasting votes to prevent unanimous/near-unanimous patterns
- **Anonymizes identifying fields**: CountingGroup and PrecinctPortion are dynamically detected from headers and blanked in all output rows to prevent revealing geographic or voting method information beyond the contest bitmap
- **Preserves BallotType**: BallotType is preserved in non-aggregated rows (set to "AGGREGATED" in aggregated rows). The tool warns if BallotType varies for ballots with the same contest pattern, which could indicate information leakage. BallotType values are displayed in the style mapping output
- Computes descriptive style names based on contest patterns
- Detects information leakage when different CVR style names map to the same contest pattern
- Automatic tally verification ensures vote totals match between original and anonymized CVR
- Comprehensive aggregation statistics showing:
  - Totals after including all rare styles (with ballot counts, vote counts, and undervotes)
  - Contests needing additional ballots (with reasons: had X, needed Y more to reach Z)
  - Contests needing balancing (unanimous/near-unanimous patterns)
  - Total extra CVRs added to aggregate
  - Final aggregate totals (with ballot counts, vote counts, and undervotes)
- Style mapping output includes BallotType information for each CVR style

**Options:**
- `--check`, `-c`: report whether redaction is needed, without writing output
- `--min-ballots N`: minimum ballots required per style or precinct (default: 10, and at
  least 2)
- `--redact-on-precinct`: aggregate precincts with fewer than the minimum, instead of blanking the
  PrecinctPortion column
- `--stylecol N`: column index (0-based) of a named style field, if present
- `--no-contest-balancing`: skip the optional per-contest minimum and near-unanimity balancing
- `--force`: replace the output file, and the `--redacted-list` file, if they already exist.
  Without it an existing file is left alone and the run stops, and the output is never allowed to
  be the input file itself
- `--redacted-list FILENAME`: write the ImprintedId of every redacted ballot to FILENAME
- `--version`: print the version

## Example Workflow

1. **Check whether a CVR file needs redaction:**
   ```bash
   python3 anonymize_cvr.py --check original_cvr.csv
   ```

2. **Anonymize the CVR file:**
   ```bash
   python3 anonymize_cvr.py original_cvr.csv anonymized_cvr.csv
   ```

3. **Verify that vote totals are preserved:**
   ```bash
   python3 verify_redaction.py original_cvr.csv anonymized_cvr.csv
   ```

## Aggregation Approach

The anonymization tool uses a balance-focused approach:

1. **Combine all rare styles**: All ballots from rare styles (< 10 ballots) are combined into a single aggregation
2. **Meet minimum thresholds**: If needed, ballots are borrowed from common styles to ensure:
   - At least 10 ballots total in the aggregation
   - At least 10 ballots per contest in the aggregation
3. **Balance votes**: The tool checks for unanimous or near-unanimous patterns (all but 2 votes for the same candidate) and adds contrasting votes from common styles to break these patterns
4. **Anonymize identifying fields**: CountingGroup and PrecinctPortion are blanked in all output rows to prevent revealing geographic or voting method information. BallotType is preserved in non-aggregated rows (it should only reflect contest pattern, not additional identifying information). Note that if this sort of information is visible on the printed ballot, that should be taken into account when procedures for releasing ballot images are designed.
5. **Verify tallies**: Before delivering the redacted CVR, vote tallies are automatically verified to match the original

This approach minimizes the number of ballots that need to be redacted while ensuring both anonymity and statistical balance.

## Style Analysis

The anonymization tool automatically:
- Computes descriptive style names based on contest patterns (format: `<n><R|S><m>` where n=contest count, R=rare/S=common, m=style number)
- Maps CVR style names to descriptive style names, including BallotType information for each style
- Detects information leakage when different CVR style names or BallotType values are used for ballots with the same contest pattern
- Displays detailed aggregation statistics including totals (with ballot counts, vote counts, and undervotes), contests needing balancing, and extra CVRs added

## Requirements

- Python 3.12+
- Standard library only (csv, collections, typing); no third-party packages are needed
- `tkinter` only for the optional graphical interface, which starts when the program is run with no
  command-line arguments.  The command line works without it.
