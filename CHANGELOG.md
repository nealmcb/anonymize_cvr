# Changelog

Changes to `anonymize_cvr` that matter to people who run it or read its output. The version
written in the first row of every redacted CVR (`anonymize_cvr-vX.Y.Z`) names the release that
wrote it.

## 0.4.0 (unreleased)

### Redaction

- **Contests too rare to protect are redacted.** A contest present on more than 0 and fewer than
  `--min-ballots` cards in the whole file can't be protected by grouping ballots, because it is
  rarer than the group. Its columns stay in the file, every cell in them is emptied on every
  ballot row, and its columns in the aggregation line say `Redacted`. If no ballot needed
  grouping, an aggregation line standing for no ballots is added to carry the `Redacted` marks.
  `--keep-rare-contests` turns this off.
- **Rare ballot-type labels make their ballots rare.** A ballot whose `BallotType` label (or
  `--stylecol` label) is carried by fewer than `--min-ballots` ballots is grouped into the
  aggregate like any rare ballot, since the label alone picks it out. `--drop-ballottype` drops
  the label columns instead.
- **The aggregation line leaves a contest's columns empty when no grouped ballot carries it,** as
  a ballot row does, instead of writing 0. A 0 says the contest is on the card and not voted, which
  overstated the number of cards carrying the contest and so understated its margin. The
  aggregation line added for rare contests alone is empty in every column it does not mark
  `Redacted`.
- **Warning when contest balancing is skipped or falls short.** The report lists each contest that
  is on a rare ballot and on fewer than `--min-ballots` of the aggregate's ballots, whose votes for
  those few ballots the aggregation line then shows. The help text and the window now say that
  skipping contest balancing is not recommended.
- **`--redacted-list` also lists visible ballots that carried a redacted contest.** Their rows show
  nothing of the contest, but their ballot images do, so images of these ballots need redacting
  too.

### Safety of files

- The output may not be the input file, under any name or link, and an existing output or
  `--redacted-list` file is never replaced without `--force` (the window asks first).
- A run that fails partway leaves no partial output file: output is written to a temporary file
  and moved into place only after the whole file is written and its totals check out.
- An unreadable input file (not UTF-8, a malformed CSV, too few header rows) gives a plain error
  message instead of a traceback.
- `--min-ballots` must be at least 2.

### The web version (`anonymize_cvr.html`)

- Gets all of the redaction changes above, and writes the version in the first row.
- Fixed: a CVR whose last line had no line ending had that last ballot written out without being
  checked for redaction. Anyone who ran the web version on such a file should run it again.
- Fixed: a redacted ballot had every vote cell starred, including blank ones, unlike the Python
  version; blank cells now stay blank.
- `tests/web_matches_python.js` checks that the web and Python versions write identical output.

### Reading redacted files

- `verify_redaction.py` reads `Redacted` as unknown, never as zero. Any other program that reads
  redacted CVRs should do the same, and should not count an aggregation line as a ballot.

### Project

- Licensed under the Apache License 2.0.
- Continuous integration runs the tests on Python 3.9 and 3.12, and mypy and black.
- Files left over from an earlier, removed tool were removed.

## 0.3

- The first row of a redacted CVR names the version that wrote it.

## 0.2 and earlier

Not recorded here; see the commit history.
