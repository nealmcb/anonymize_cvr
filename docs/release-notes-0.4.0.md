# anonymize_cvr 0.4.0: release notes for county election offices

`anonymize_cvr` prepares a cast vote record (CVR) for public release under C.R.S. 24-72-205.5:
it finds ballots rare enough to identify a voter and publishes only their combined totals. This
release protects voters in cases the earlier version missed. Please use it in place of any
earlier copy.

## What to do

1. Download `anonymize_cvr.py` from this release page, not from an earlier link. The first row
   of the file it writes says `anonymize_cvr-v0.4.0`.
2. Follow the quick start for county election offices, step by step:
   https://github.com/nealmcb/anonymize_cvr/blob/main/docs/QUICKSTART.md
   **Leave the options at their defaults,** in particular leave contest balancing on.
3. Keep the line marked `AGGREGATED` at the end of the redacted file. It holds the combined
   totals of the redacted ballots; without it, the file's vote totals no longer match your
   results.

## What changed

**Precinct portions.** Each ballot's header or barcode records its precinct portion, so a ballot
image shows it even when the CVR's precinct column is removed. The tool now keeps the precinct
column by default and redacts the ballots whose style is rare within their precinct portion, so
they can't be picked out by precinct. Remove the column instead only if you will never release
ballot images with precinct information.

**Contests on only a few ballots.** A contest that appears on fewer than 10 ballots in the whole
county (a district that takes in a few houses across the county line, say) can't be protected by
aggregating ballots. The tool now empties that contest's cells throughout the file and writes
`Redacted` in its columns of the aggregation line, instead of publishing its totals. The report
lists each such contest.

**Ballot-type labels used by only a few ballots.** A `BallotType` label carried by fewer than 10
ballots identifies those ballots even when their contests are common. The tool now redacts those
ballots like any other rare ballot.

**Contest balancing.** The tool reports any contest that ends up on only a few of the redacted
ballots, whose totals for those few voters the aggregation line would then show. With contest
balancing on (the default) the tool borrows enough common ballots to prevent this; turning it off
is not recommended.

**Ballot images.** Redacting the CVR does not redact ballot images. If you release images, the
redacted ballot list (always written by the window, `--redacted-list` on the command line) includes
every ballot whose image needs redacting, with the reason for each: the redacted ballots;
visible ballots that carried a redacted contest; and, if you removed the precinct or ballot-type
column, visible ballots that are rare within their precinct portion or carry a rare label, whose
images still show the precinct or the ballot-style code.

**The options window** puts the protections first, then offers precinct portions and ballot
types as a pair of choices each. Keep the default choice in each pair.

**Files named for you, and a saved report.** The window asks only for a folder (your export's,
unless you choose another) and writes three files named after your export: the redacted CVR, the
list of ballots whose images need redacting, and a report of the run with the version, the
options, your export's SHA-256 and everything the tool found. It asks before replacing any of
them.

**Safer with your files.** The tool never writes over the CVR it is reading, never replaces an
existing file without asking, and never leaves a half-written file if something goes wrong.

## Reading the redacted file

- A blank cell means the contest is not on that card, as in the original export.
- In the aggregation line, a number is the total for all the redacted ballots, and a blank means
  none of them carries that contest.
- `Redacted` means the totals are withheld. Read it as unknown, never as zero.

## Checking the file you downloaded

The release page lists the SHA-256 of each file in `SHA256SUMS`, signed by the maintainer
(Sigstore, as nealmcb@gmail.com, and OpenPGP, key EDC0 36EB 2397 A000 D7CD 417B B94C 992F 3314
8156). On
Windows, in PowerShell:

```
Get-FileHash anonymize_cvr.py -Algorithm SHA256
```

The result should match the line for `anonymize_cvr.py` in `SHA256SUMS`. See `docs/RELEASE.md`
for checking the signatures.

## Installing from PyPI

If you use Python's package tools, the same release is on PyPI as `anonymize-cvr`:

```
pipx install anonymize_cvr
```

This installs the commands `anonymize_cvr` and `anonymize_cvr_gui`.

## Questions

Report a problem or ask a question at https://github.com/nealmcb/anonymize_cvr/issues
