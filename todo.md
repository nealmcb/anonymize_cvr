# To-Do

## Code cleanup

1. **Consolidate "rules" references**
   The code mentions Rules a, b, c, d in scattered docstrings and comments with no
   single authoritative definition.  Collect them in one place (e.g., a module-level
   docstring block or a comment section above the redaction functions) and replace
   scattered mentions with references to that block.

2. **Decide whether to delete parquetCVR/ (ask Neal)**
   `parquetCVR/` holds 670 MB of Parquet CVRs (`2020gen`, `2022pri` and their
   zip files) that nothing reads since `guess_votes.py` was removed.  It has
   never been committed, here or on Neal's `guess_votes` branch, so deleting it
   cannot be undone.  If it goes, remove its `.gitignore` entry at the same
   time, not before, or the data could be committed by accident.


## Testing

1. **Test re-redacting an already-redacted CVR**
   The tests run `--check` on redacted output, but nothing runs a full redaction
   on an already-redacted file (one with `*` marks and an `AGGREGATED` row).  Add
   a scenario to `generate_test_cvrs.py`, or a case in `run_tests.py` that redacts
   the output a second time.

2. **Test a first row that is shorter than the other rows**
   Some unredacted CVRs may have a first row with only the election name and the
   Dominion version (two cells, no blanks).  `anonymize_cvr.py` then appends the
   version string to row 1; no test covers that.  Add a case with a two-cell first
   row and check that `anonymize_cvr-v<VERSION>` is appended and that row 1 is no
   wider than the other rows.  (The committed `test_case_cvr.csv` has a short
   first row, 8 cells against 12, but it has blank cells, so it takes the
   ordinary path, and its test does not check row 1.)

3. **Decide how to handle hand-made test files**
   Every `run_tests.py` input comes from `generate_test_cvrs.py` except
   `test_case_cvr.csv` (used by `no_balancing_blocked_pull`), which was originally
   produced by the now-removed `guess_votes.py` and can no longer be regenerated.
   Decide whether to turn it into a scenario in `generate_test_cvrs.py`, or to
   keep hand-made files in their own folder with a note on what each is for.


## Window and outputs

1. **Review the options window**
   Put the precinct and ballot-type options next to each other, under one short explanation of
   ballot images: a ballot carries its style and, where results are reported by precinct, its
   precinct, so whatever the CVR hides the images may still show. Word the protections so that
   leaving every box as it starts is the recommended setting, e.g. "Skip redaction by precinct
   (not recommended)" in place of "Redact on Precinct", like "Skip contest balancing (not
   recommended)". Group the boxes under "Protections" and "What to publish". Say "precinct
   portion" consistently, with a note that it may be a real precinct, a split or a ballot style,
   depending on how the county set up the election.

2. **Give each listed ballot its reason**
   The window always writes the list of ballots whose images need redacting, one ImprintedId per
   line. Add each ballot's reason: grouped in the CVR; visible but carried a redacted contest; or
   visible but rare once the columns the CVR dropped are counted (precinct, ballot type), since
   the image still shows them. The third kind is not listed today. The remedies differ: hide the
   votes or withhold the image for the first two, black out the precinct or style code for the
   third. An option says what the county's images show; assume both precinct and style unless
   told otherwise. A reason column changes the list's format, so check first what reads it.

3. **The web version: the same files**
   The window names its outputs after the input and saves a report of each run; the web version
   still suggests only the redacted CVR's name, and keeps no report.

4. **Always write the output file, even when nothing needs redaction**
   Today a run that finds nothing to redact prints "No redaction needed." and writes no file, in
   the window, on the command line and in the web version, so the county releases its export as
   it is: with no version tag in the first row, a reader can't tell a file the tool checked from
   one it never saw, and a CountingGroup column stays unless removed by hand (often in Excel,
   which drops the quotes and can turn imprinted IDs into dates). Always write the output, with
   the version tag and without CountingGroup, plus the report. This is only for the released
   copy; the file uploaded to CORLA stays the voting system's export without CountingGroup.
