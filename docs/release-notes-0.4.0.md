# anonymize_cvr 0.4.0: release notes for county election offices

`anonymize_cvr` prepares a cast vote record (CVR) for public release under C.R.S. 24-72-205.5:
it finds ballots rare enough to identify a voter and publishes only their combined totals. This
release protects voters in cases the earlier version missed. Please use it in place of any
earlier copy.

## What to do

1. Download `anonymize_cvr.py` from this release page, not from an earlier link. The first row
   of the file it writes says `anonymize_cvr-v0.4.0`.
2. Run it as before (see the quick start). **Leave the options at their defaults,** in
   particular leave contest balancing on.
3. Send the audit verifiers the redacted file **with its aggregation line** (the line marked
   `AGGREGATED` at the end). Whether the copy you publish keeps that line is your decision, but
   the verifiers need it to check the audit.

## What changed

**Contests on only a few ballots.** A contest that appears on fewer than 10 ballots in the whole
county (a district that takes in a few houses across the county line, say) can't be protected by
grouping ballots. The tool now empties that contest's cells throughout the file and writes
`Redacted` in its columns of the aggregation line, instead of publishing its totals. The report
lists each such contest.

**Ballot-type labels used by only a few ballots.** A `BallotType` label carried by fewer than 10
ballots identifies those ballots even when their contests are common. The tool now groups those
ballots like any other rare ballot.

**Contest balancing.** The tool reports any contest that ends up on only a few of the grouped
ballots, whose totals for those few voters the aggregation line would then show. With contest
balancing on (the default) the tool borrows enough common ballots to prevent this; turning it off
is not recommended.

**Ballot images.** Redacting the CVR does not redact ballot images. If you release images, the
list from `--redacted-list` now includes every ballot whose image needs redacting: the grouped
ballots, and visible ballots that carried a redacted contest. A label printed on the ballot (a
ballot-style code or precinct number) carried by only a few ballots needs redacting on the images
too.

**Safer with your files.** The tool never writes over the CVR it is reading, never replaces an
existing file without asking, and never leaves a half-written file if something goes wrong.

## Reading the redacted file

- A blank cell means the contest is not on that card, as in the original export.
- In the aggregation line, a number is the total for all the grouped ballots, and a blank means
  none of them carries that contest.
- `Redacted` means the totals are withheld. Read it as unknown, never as zero.

## Checking the file you downloaded

The release page lists the SHA-256 of each file in `SHA256SUMS`, signed by the maintainers. On
Windows, in PowerShell:

```
Get-FileHash anonymize_cvr.py -Algorithm SHA256
```

The result should match the line for `anonymize_cvr.py` in `SHA256SUMS`. See `docs/RELEASE.md`
for checking the signatures.

## Questions

Contact the people who sent you this release. Problems can also be reported at
https://github.com/nealmcb/anonymize_cvr/issues
