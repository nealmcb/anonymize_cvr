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

