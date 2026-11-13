#!/usr/bin/env python3
"""
run_tests.py

Regenerates test input files, then runs all test scenarios through
anonymize_cvr.py and verify_redaction.py, checking expected output.

Usage:
    python run_tests.py
"""

import csv
import glob
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

GENERATED_DIR = "testCases/generated"
OUTPUT_DIR = "/tmp/anonymize_test_outputs"
# Outputs the tool produced before contests too rare to protect were redacted
# (made with anonymize_cvr.py as of commit 7b70eca).  --keep-rare-contests must
# reproduce them byte for byte.  Regenerate them if VERSION changes, since it
# is written into the first row.
EXPECTED_DIR = "tests/expected"


# Python source that blocks tkinter, so that the command line can be shown to
# work on a machine with no GUI library installed.
BLOCK_TKINTER = """
import sys


class _Blocker:
    '''Meta path finder that makes tkinter unavailable.'''

    def find_spec(self, name, path=None, target=None):
        if name == "tkinter" or name.startswith("tkinter."):
            raise ImportError("tkinter blocked for this test")
        return None


sys.meta_path.insert(0, _Blocker())
"""


@dataclass
class TestCase:
    name: str
    input_file: str
    output_file: Optional[str]  # None = --check only (no redaction step)
    redact_flags: List[str] = field(default_factory=list)
    check_flags: List[str] = field(
        default_factory=list
    )  # extra flags for --check on output
    expected: List[str] = field(default_factory=list)  # must appear in redaction output
    unexpected: List[str] = field(
        default_factory=list
    )  # must not appear in redaction output
    # Extra checks on the written output file; each returns failure messages.
    file_checks: List[Callable[[str], List[str]]] = field(default_factory=list)


def _run(cmd: List[str]) -> Tuple[int, str]:
    """Run a command and return (returncode, combined stdout+stderr)."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


def _check_output(output: str, expected: List[str], unexpected: List[str]) -> List[str]:
    """Return a list of failure messages for unmet expectations."""
    failures = []
    for s in expected:
        if s not in output:
            failures.append(f"  Expected string not found: {s!r}")
    for s in unexpected:
        if s in output:
            failures.append(f"  Unexpected string found: {s!r}")
    return failures


def run_test(tc: TestCase) -> bool:
    """Run one test case. Returns True if all checks pass."""
    failures = []

    if tc.output_file is None:
        # --check only mode, no redaction or verify steps.
        cmd = (
            ["python", "anonymize_cvr.py", "--check"]
            + tc.redact_flags
            + [tc.input_file]
        )
        rc, output = _run(cmd)
        if rc != 0:
            failures.append(f"  --check command exited with code {rc}")
        failures.extend(_check_output(output, tc.expected, tc.unexpected))
    else:
        # Step 1: redact.
        cmd = (
            ["python", "anonymize_cvr.py"]
            + tc.redact_flags
            + [tc.input_file, tc.output_file]
        )
        rc, output = _run(cmd)
        if rc != 0:
            failures.append(f"  Redaction command exited with code {rc}")
        failures.extend(_check_output(output, tc.expected, tc.unexpected))

        if not failures:
            # Step 2: --check on output (rare styles should be gone).
            cmd = (
                ["python", "anonymize_cvr.py", "--check"]
                + tc.check_flags
                + [tc.output_file]
            )
            rc, check_output = _run(cmd)
            if rc != 0:
                failures.append(f"  --check on output exited with code {rc}")
            elif "No redaction needed." not in check_output:
                failures.append(
                    "  --check on output did not say 'No redaction needed.'"
                )

            # Step 3: verify vote totals are preserved.
            cmd = ["python", "verify_redaction.py", tc.input_file, tc.output_file]
            rc, verify_output = _run(cmd)
            if rc != 0:
                failures.append(
                    f"  verify_redaction.py exited with code {rc}:\n    {verify_output.strip()}"
                )
            elif "Verification passed" not in verify_output:
                failures.append(
                    "  verify_redaction.py did not say 'Verification passed'"
                )

            # Step 4: checks on the contents of the written file.
            for file_check in tc.file_checks:
                failures.extend(file_check(tc.output_file))

    if failures:
        print(f"FAIL  {tc.name}")
        for msg in failures:
            print(msg)
        return False
    else:
        print(f"PASS  {tc.name}")
        return True


def _bad_input(name: str, transform: Callable[[bytes], bytes]) -> str:
    """
    Write a damaged copy of a good CVR into OUTPUT_DIR and return its path.

    Used to check that unreadable input produces a plain message naming the
    file and the problem, not a traceback.
    """
    path = f"{OUTPUT_DIR}/{name}"
    with open(f"{GENERATED_DIR}/needs_borrowing.csv", "rb") as f:
        data = f.read()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(path, "wb") as f:
        f.write(transform(data))
    return path


def _copy_input(name: str) -> str:
    """Copy a good CVR into OUTPUT_DIR under name and return its path."""
    path = f"{OUTPUT_DIR}/{name}"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    shutil.copyfile(f"{GENERATED_DIR}/needs_borrowing.csv", path)
    return path


def _unchanged(path: str, reference: str) -> List[str]:
    """Return a failure if path no longer matches reference byte for byte."""
    with open(path, "rb") as f:
        actual = f.read()
    with open(reference, "rb") as f:
        expected = f.read()
    if actual != expected:
        return [f"  file was modified but should not have been: {path}"]
    return []


def _symlink(target: str, link: str) -> None:
    """Point link at target, replacing any previous link."""
    if os.path.lexists(link):
        os.remove(link)
    os.symlink(target, link)


def _write_file(path: str, contents: str) -> None:
    """Create path with the given contents."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contents)


def _is_replaced(path: str) -> List[str]:
    """Return a failure if path still holds the placeholder contents."""
    with open(path, encoding="utf-8") as f:
        if f.read().startswith("old contents"):
            return [f"  file was not replaced: {path}"]
    return []


def _remove_if_present(path: str) -> None:
    """Delete path if it is there, so a test starts from a known state."""
    if os.path.exists(path):
        os.remove(path)


def _no_leftovers(*paths: str) -> List[str]:
    """
    Return failures for any of paths that exists, or any temporary .part file
    left in OUTPUT_DIR.  Output is written to a temporary file and moved into
    place only on success, so a failed run must leave neither.
    """
    failures = []
    for path in paths:
        if os.path.exists(path):
            failures.append(f"  file should not exist after a failed run: {path}")
    for leftover in glob.glob(f"{OUTPUT_DIR}/*.part"):
        failures.append(f"  temporary file left behind: {leftover}")
    return failures


def _list_holds(
    path: str, exactly: Optional[List[str]] = None, includes: Sequence[str] = ()
) -> List[str]:
    """
    Return failures unless the --redacted-list file at path holds exactly the
    ImprintedIds given (in any order), or at least those in includes.
    """
    if not os.path.exists(path):
        return [f"  redacted list was not written: {path}"]
    with open(path, encoding="utf-8") as f:
        listed = [line.strip() for line in f if line.strip()]
    failures = []
    if exactly is not None and sorted(listed) != sorted(exactly):
        failures.append(f"  redacted list holds {listed}, expected {exactly}")
    for imprinted_id in includes:
        if imprinted_id not in listed:
            failures.append(f"  redacted list lacks {imprinted_id}")
    return failures


def _read_cvr(path: str) -> List[List[str]]:
    """Read a CVR file into a list of rows (four header rows, then ballots)."""
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def _contest_columns(rows: List[List[str]], contest: str) -> List[int]:
    """Return the column indices whose contest name (row 2) is contest."""
    return [i for i, name in enumerate(rows[1]) if name == contest]


def _vote_columns(rows: List[List[str]]) -> List[int]:
    """Return the indices of all vote columns (those with a contest name)."""
    return [i for i, name in enumerate(rows[1]) if name.strip()]


def _ballot_rows(rows: List[List[str]]) -> List[List[str]]:
    """Return the ballot rows, without the aggregation line."""
    return [r for r in rows[4:] if r and r[0] != "AGGREGATED"]


def _aggregation_line(rows: List[List[str]]) -> Optional[List[str]]:
    """Return the aggregation line, or None if there is none."""
    lines = [r for r in rows[4:] if r and r[0] == "AGGREGATED"]
    return lines[0] if len(lines) == 1 else None


def _contest_redacted(contest: str) -> Callable[[str], List[str]]:
    """
    Check that contest's columns are empty on every ballot row (no '*' either)
    and say "Redacted" in the aggregation line.
    """

    def check(path: str) -> List[str]:
        rows = _read_cvr(path)
        cols = _contest_columns(rows, contest)
        failures = []
        if not cols:
            failures.append(f"  contest {contest!r} is missing from the output")
        for row in _ballot_rows(rows):
            for col in cols:
                if row[col] != "":
                    failures.append(
                        f"  CvrNumber {row[0]}: {contest!r} cell is {row[col]!r}, not empty"
                    )
        agg = _aggregation_line(rows)
        if agg is None:
            failures.append("  output has no single aggregation line")
        else:
            for col in cols:
                if agg[col] != "Redacted":
                    failures.append(
                        f"  aggregation line has {agg[col]!r} for {contest!r}, "
                        "not 'Redacted'"
                    )
        return failures

    return check


def _aggregation_zero_except(contest: str) -> Callable[[str], List[str]]:
    """Check the aggregation line has 0 in every vote column except contest's."""

    def check(path: str) -> List[str]:
        rows = _read_cvr(path)
        agg = _aggregation_line(rows)
        if agg is None:
            return ["  output has no single aggregation line"]
        redacted = set(_contest_columns(rows, contest))
        return [
            f"  aggregation line has {agg[col]!r} in {rows[1][col]!r}, not '0'"
            for col in _vote_columns(rows)
            if col not in redacted and agg[col] != "0"
        ]

    return check


def _rows_visible(cvr_numbers: List[str]) -> Callable[[str], List[str]]:
    """Check that the listed ballots are not redacted (no '*' in their votes)."""

    def check(path: str) -> List[str]:
        rows = _read_cvr(path)
        by_number = {r[0]: r for r in _ballot_rows(rows)}
        failures = []
        for number in cvr_numbers:
            row = by_number.get(number)
            if row is None:
                failures.append(f"  CvrNumber {number} is missing")
            elif "*" in row:
                failures.append(
                    f"  CvrNumber {number} was redacted but should be visible"
                )
        return failures

    return check


def _rows_redacted(cvr_numbers: List[str]) -> Callable[[str], List[str]]:
    """Check that the listed ballots are redacted ('*' in their votes)."""

    def check(path: str) -> List[str]:
        by_number = {r[0]: r for r in _ballot_rows(_read_cvr(path))}
        return [
            f"  CvrNumber {number} should be redacted"
            for number in cvr_numbers
            if "*" not in by_number.get(number, [])
        ]

    return check


def _no_header_column(name: str) -> Callable[[str], List[str]]:
    """Check that the output has no header column of this name (row 4)."""

    def check(path: str) -> List[str]:
        if name in _read_cvr(path)[3]:
            return [f"  output still has a {name!r} column"]
        return []

    return check


def _has_header_column(name: str) -> Callable[[str], List[str]]:
    """Check that the output still has a header column of this name (row 4)."""

    def check(path: str) -> List[str]:
        if name not in _read_cvr(path)[3]:
            return [f"  output has lost its {name!r} column"]
        return []

    return check


def _no_redacted_anywhere(path: str) -> List[str]:
    """Check that nothing in the output says "Redacted"."""
    if any("Redacted" in row for row in _read_cvr(path)):
        return ["  output has a 'Redacted' entry but no contest should be redacted"]
    return []


def _same_as(reference: str) -> Callable[[str], List[str]]:
    """Check that the output matches reference byte for byte."""

    def check(path: str) -> List[str]:
        return [
            msg.replace(
                "was modified but should not have been", "differs from " + reference
            )
            for msg in _unchanged(path, reference)
        ]

    return check


def _snapshot(directory: str) -> List[str]:
    """List the files in directory, so a test can show none was written."""
    return sorted(os.listdir(directory)) if os.path.isdir(directory) else []


_SNAPSHOTS: Dict[str, List[str]] = {}


def _remember(directory: str) -> None:
    """Record the files in directory before a command runs."""
    _SNAPSHOTS[directory] = _snapshot(directory)


def _remember_test_dirs() -> None:
    """Record the files in the output and generated-input directories."""
    _remember(OUTPUT_DIR)
    _remember(GENERATED_DIR)


def _nothing_written(directory: str) -> List[str]:
    """Return a failure if a file appeared in directory since _remember()."""
    added = set(_snapshot(directory)) - set(_SNAPSHOTS.get(directory, []))
    return [f"  --check wrote a file: {name}" for name in sorted(added)]


@dataclass
class CommandTest:
    """
    One command run as-is, checked by exit status and output text.

    Used for the robustness checks (bad input, refusing to clobber files,
    option validation), where what matters is a clear message and a non-zero
    exit status rather than a redacted CVR.
    """

    name: str
    cmd: List[str]
    expect_failure: bool = False
    expected: List[str] = field(default_factory=list)
    unexpected: List[str] = field(default_factory=list)
    setup: Optional[Callable[[], object]] = None
    after: Optional[Callable[[], List[str]]] = None


def run_command_test(tc: CommandTest) -> bool:
    """Run one CommandTest. Returns True if all checks pass."""
    failures = []
    if tc.setup is not None:
        tc.setup()

    rc, output = _run(tc.cmd)
    if tc.expect_failure and rc == 0:
        failures.append("  command succeeded but was expected to fail")
    if not tc.expect_failure and rc != 0:
        failures.append(f"  command exited with code {rc}:\n    {output.strip()}")
    failures.extend(_check_output(output, tc.expected, tc.unexpected))

    if tc.after is not None:
        failures.extend(tc.after())

    if failures:
        print(f"FAIL  {tc.name}")
        for msg in failures:
            print(msg)
        return False
    print(f"PASS  {tc.name}")
    return True


def _make_command_tests() -> List[CommandTest]:
    return [
        CommandTest(
            # tkinter is imported only inside the window code, so the module
            # must import, and the command line must work, without it.
            name="imports_without_tkinter",
            cmd=[
                sys.executable,
                "-c",
                BLOCK_TKINTER
                + "import anonymize_cvr\n"
                + "print('module imported without tkinter')\n"
                + "sys.argv = ['anonymize_cvr.py', '--check', "
                + f"{GENERATED_DIR + '/no_redaction.csv'!r}]\n"
                + "anonymize_cvr.main()\n",
            ],
            expected=[
                "module imported without tkinter",
                "No redaction needed.",
            ],
            unexpected=["Traceback"],
        ),
        CommandTest(
            # Writing the output onto the input empties the input while it is
            # still being read, which destroys it.
            name="output_same_as_input_refused",
            cmd=[
                "python",
                "anonymize_cvr.py",
                f"{OUTPUT_DIR}/same_file.csv",
                f"{OUTPUT_DIR}/same_file.csv",
            ],
            setup=lambda: _copy_input("same_file.csv"),
            expect_failure=True,
            expected=["is the same file as the input CVR"],
            unexpected=["Traceback"],
            after=lambda: _unchanged(
                f"{OUTPUT_DIR}/same_file.csv",
                f"{GENERATED_DIR}/needs_borrowing.csv",
            ),
        ),
        CommandTest(
            # The same file reached by a different path: os.path.samefile
            # follows the symlink.
            name="output_same_as_input_via_symlink_refused",
            cmd=[
                "python",
                "anonymize_cvr.py",
                f"{OUTPUT_DIR}/symlinked.csv",
                f"{OUTPUT_DIR}/symlink_to_input.csv",
            ],
            setup=lambda: _symlink(
                _copy_input("symlinked.csv"), f"{OUTPUT_DIR}/symlink_to_input.csv"
            ),
            expect_failure=True,
            expected=["is the same file as the input CVR"],
            unexpected=["Traceback"],
            after=lambda: _unchanged(
                f"{OUTPUT_DIR}/symlinked.csv",
                f"{GENERATED_DIR}/needs_borrowing.csv",
            ),
        ),
        CommandTest(
            name="existing_output_refused",
            cmd=[
                "python",
                "anonymize_cvr.py",
                f"{GENERATED_DIR}/needs_borrowing.csv",
                f"{OUTPUT_DIR}/already_there.csv",
            ],
            setup=lambda: _copy_input("already_there.csv"),
            expect_failure=True,
            expected=["already there", "--force"],
            unexpected=["Traceback"],
            after=lambda: _unchanged(
                f"{OUTPUT_DIR}/already_there.csv",
                f"{GENERATED_DIR}/needs_borrowing.csv",
            ),
        ),
        CommandTest(
            name="existing_redacted_list_refused",
            cmd=[
                "python",
                "anonymize_cvr.py",
                f"{GENERATED_DIR}/needs_borrowing.csv",
                f"{OUTPUT_DIR}/list_output.csv",
                "--redacted-list",
                f"{OUTPUT_DIR}/already_a_list.txt",
            ],
            setup=lambda: _write_file(f"{OUTPUT_DIR}/already_a_list.txt", "keep me\n"),
            expect_failure=True,
            expected=["already_a_list.txt", "already there", "--force"],
            unexpected=["Traceback"],
            after=lambda: _no_leftovers(f"{OUTPUT_DIR}/list_output.csv"),
        ),
        CommandTest(
            name="existing_output_replaced_with_force",
            cmd=[
                "python",
                "anonymize_cvr.py",
                f"{GENERATED_DIR}/needs_borrowing.csv",
                f"{OUTPUT_DIR}/forced.csv",
                "--force",
            ],
            setup=lambda: _write_file(f"{OUTPUT_DIR}/forced.csv", "old contents\n"),
            expected=["Tally verification passed.", "Output written to"],
            unexpected=["Traceback"],
            after=lambda: _is_replaced(f"{OUTPUT_DIR}/forced.csv"),
        ),
        CommandTest(
            # The --redacted-list path is in a directory that does not exist,
            # so the run fails after the output file would have been opened.
            # Neither the output nor a temporary file may survive that.
            name="no_partial_output_after_failure",
            cmd=[
                "python",
                "anonymize_cvr.py",
                f"{GENERATED_DIR}/needs_borrowing.csv",
                f"{OUTPUT_DIR}/partial.csv",
                "--redacted-list",
                f"{OUTPUT_DIR}/no_such_directory/list.txt",
            ],
            setup=lambda: _remove_if_present(f"{OUTPUT_DIR}/partial.csv"),
            expect_failure=True,
            expected=["Error:"],
            unexpected=["Traceback"],
            after=lambda: _no_leftovers(f"{OUTPUT_DIR}/partial.csv"),
        ),
        CommandTest(
            # Fremont's 2020 CVR is Latin-1, which used to raise
            # UnicodeDecodeError.
            name="bad_input_not_utf8",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--check",
                f"{OUTPUT_DIR}/not_utf8.csv",
            ],
            setup=lambda: _bad_input(
                "not_utf8.csv",
                lambda d: d.replace(b"Alice", "Alic\u00e9".encode("latin-1"), 1),
            ),
            expect_failure=True,
            expected=["not UTF-8 text; save it as UTF-8 CSV and try again"],
            unexpected=["Traceback"],
        ),
        CommandTest(
            # A field over 131,072 characters raises csv.Error on every Python version.
            # (A NUL byte does too before Python 3.11, but not since.)
            name="bad_input_csv_error",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--check",
                f"{OUTPUT_DIR}/huge_field.csv",
            ],
            setup=lambda: _bad_input(
                "huge_field.csv", lambda d: d.replace(b"Alice", b"A" * 200000, 1)
            ),
            expect_failure=True,
            expected=["the CSV could not be read:"],
            unexpected=["Traceback"],
        ),
        CommandTest(
            # Fewer than four header rows used to raise StopIteration.
            name="bad_input_too_few_header_rows",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--check",
                f"{OUTPUT_DIR}/short.csv",
            ],
            setup=lambda: _bad_input(
                "short.csv", lambda d: b"\n".join(d.split(b"\n")[:3])
            ),
            expect_failure=True,
            expected=[
                "fewer than four header rows; this does not look like a "
                "Dominion CVR export"
            ],
            unexpected=["Traceback"],
        ),
        CommandTest(
            # 0 or a negative --min-ballots turned redaction off while the run
            # still looked like a success.
            name="min_ballots_zero_refused",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--check",
                "--min-ballots",
                "0",
                f"{GENERATED_DIR}/needs_borrowing.csv",
            ],
            expect_failure=True,
            expected=["--min-ballots must be at least 2."],
            unexpected=["Traceback", "No redaction needed."],
        ),
        CommandTest(
            name="min_ballots_negative_refused",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--check",
                "--min-ballots",
                "-3",
                f"{GENERATED_DIR}/needs_borrowing.csv",
            ],
            expect_failure=True,
            expected=["--min-ballots must be at least 2."],
            unexpected=["Traceback", "No redaction needed."],
        ),
        CommandTest(
            name="min_ballots_two_accepted",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--check",
                "--min-ballots",
                "2",
                f"{GENERATED_DIR}/needs_borrowing.csv",
            ],
            expected=["No redaction needed."],
            unexpected=["Traceback"],
        ),
        CommandTest(
            # --check lists the contests too rare to protect, with their card
            # counts, and writes nothing.
            name="check_lists_rare_contests",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--check",
                f"{GENERATED_DIR}/rare_contest.csv",
            ],
            setup=_remember_test_dirs,
            expected=[
                "Contests present on fewer than 10 cards (1)",
                "'Fringe District': 5 card(s)",
                "These contests would be redacted",
                "This protects only the CVR.",
                "Redaction is needed.",
            ],
            unexpected=["Traceback", "Output written"],
            after=lambda: _nothing_written(OUTPUT_DIR)
            + _nothing_written(GENERATED_DIR),
        ),
        CommandTest(
            # A rare-contest-only file needs redacting even though no style is rare.
            name="check_rare_contest_only",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--check",
                f"{GENERATED_DIR}/rare_contest_only.csv",
            ],
            expected=["'Fringe District': 3 card(s)", "Redaction is needed."],
            unexpected=["Traceback", "Rare ballot styles"],
        ),
        CommandTest(
            # The tool's own output has the rare contest on no card, so a check
            # of it finds nothing to redact.
            name="check_own_output_finds_nothing",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--check",
                f"{OUTPUT_DIR}/rare_contest.csv",
            ],
            expected=["No redaction needed."],
            unexpected=["Traceback", "Contests present on fewer than"],
        ),
        CommandTest(
            name="check_own_output_finds_nothing_added_line",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--check",
                f"{OUTPUT_DIR}/rare_contest_only.csv",
            ],
            expected=["No redaction needed."],
            unexpected=["Traceback", "Contests present on fewer than"],
        ),
        CommandTest(
            # Ballots 46-47 are grouped; 48-50 stay visible but carried Fringe
            # District, which their images still show.  The list has them all.
            name="redacted_list_has_visible_rare_contest_ballots",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--force",
                f"{GENERATED_DIR}/rare_contest.csv",
                f"{OUTPUT_DIR}/rare_contest_listed.csv",
                "--redacted-list",
                f"{OUTPUT_DIR}/rare_contest_listed.txt",
            ],
            expected=[
                "3 ballot(s) carried a redacted contest",
                "They are in the redacted ballot list too.",
            ],
            unexpected=["Traceback"],
            after=lambda: _list_holds(
                f"{OUTPUT_DIR}/rare_contest_listed.txt",
                includes=["1-1-46", "1-1-47", "1-1-48", "1-1-49", "1-1-50"],
            ),
        ),
        CommandTest(
            # No ballot is redacted here, so the list is only the three visible
            # ballots that carried Fringe District.
            name="redacted_list_only_visible_rare_contest_ballots",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--force",
                f"{GENERATED_DIR}/rare_contest_only.csv",
                f"{OUTPUT_DIR}/rare_contest_only_listed.csv",
                "--redacted-list",
                f"{OUTPUT_DIR}/rare_contest_only_listed.txt",
            ],
            expected=["3 ballot(s) carried a redacted contest"],
            unexpected=["Traceback"],
            after=lambda: _list_holds(
                f"{OUTPUT_DIR}/rare_contest_only_listed.txt",
                exactly=["1-1-46", "1-1-47", "1-1-48"],
            ),
        ),
        CommandTest(
            # Without --redacted-list the report still counts them, and says
            # how to get the list.
            name="visible_rare_contest_ballots_reported_without_list",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--force",
                f"{GENERATED_DIR}/rare_contest_only.csv",
                f"{OUTPUT_DIR}/rare_contest_only_nolist.csv",
            ],
            expected=[
                "3 ballot(s) carried a redacted contest",
                "--redacted-list lists them with the redacted ballots.",
            ],
            unexpected=["Traceback"],
        ),
        CommandTest(
            # Redacting the tool's own output again is refused, as before: it
            # has an aggregation line (and here redacted rows).  Unchanged.
            name="redact_own_output_refused",
            cmd=[
                "python",
                "anonymize_cvr.py",
                f"{OUTPUT_DIR}/rare_contest.csv",
                f"{OUTPUT_DIR}/rare_contest_again.csv",
            ],
            expect_failure=True,
            expected=["cannot re-redact a previously anonymized file"],
            unexpected=["Traceback"],
            after=lambda: _no_leftovers(f"{OUTPUT_DIR}/rare_contest_again.csv"),
        ),
        CommandTest(
            # A rare BallotType label on a common fingerprint is reported, with
            # the warning about ballot images, and makes redaction needed: by
            # default its ballots are treated as rare.
            name="check_reports_rare_ballot_type",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--check",
                f"{GENERATED_DIR}/rare_ballot_type.csv",
            ],
            expected=[
                "BallotType labels carried by fewer than 10 ballots (1):",
                "'BT-9': 3 ballot(s)",
                "These ballots would be treated as rare",
                "Grouping these ballots protects only the CVR.",
                "3 ballot(s)  [rare BallotType 'BT-9', style #0]",
                "Redaction is needed.",
            ],
            unexpected=["Traceback", "'BT-1'", "'BT-2'", "No redaction needed."],
        ),
        CommandTest(
            # With --drop-ballottype the remedy is the dropped column, and
            # redaction is still needed (the column must go).
            name="check_reports_rare_ballot_type_drop",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--check",
                "--drop-ballottype",
                f"{GENERATED_DIR}/rare_ballot_type.csv",
            ],
            expected=[
                "'BT-9': 3 ballot(s)",
                "would be dropped from the output (--drop-ballottype)",
                "Dropping the column protects only the CVR.",
                "Redaction is needed.",
            ],
            unexpected=["Traceback", "Rare ballot styles", "No redaction needed."],
        ),
        CommandTest(
            name="check_reports_rare_named_style",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--check",
                "--stylecol",
                "7",
                f"{GENERATED_DIR}/named_style.csv",
            ],
            expected=[
                "Named-style labels (column 7) carried by fewer than 10 ballots (2):",
                "'NS-B': 8 ballot(s)",
                "'NS-RARE': 6 ballot(s)",
                "Grouping these ballots protects only the CVR.",
                "Redaction is needed.",
            ],
            unexpected=["Traceback", "'NS-A'"],
        ),
        CommandTest(
            # With no arguments the window is wanted; without tkinter that has
            # to be a clear message and a non-zero exit, not a traceback.
            name="no_tkinter_no_args_message",
            cmd=[
                sys.executable,
                "-c",
                BLOCK_TKINTER
                + "import anonymize_cvr\n"
                + "sys.argv = ['anonymize_cvr.py']\n"
                + "anonymize_cvr.main()\n",
            ],
            expect_failure=True,
            expected=["tkinter is not available"],
            unexpected=["Traceback"],
        ),
    ]


def _make_test_cases() -> List[TestCase]:
    g = GENERATED_DIR
    o = OUTPUT_DIR
    return [
        TestCase(
            name="no_redaction",
            input_file=f"{g}/no_redaction.csv",
            output_file=None,
            expected=["No redaction needed."],
        ),
        TestCase(
            name="needs_borrowing",
            input_file=f"{g}/needs_borrowing.csv",
            output_file=f"{o}/needs_borrowing.csv",
            expected=["Tally verification passed.", "Total ballots in aggregate: 10"],
            unexpected=["Traceback"],
        ),
        TestCase(
            name="rare_unique_contest",
            input_file=f"{g}/rare_unique_contest.csv",
            output_file=f"{o}/rare_unique_contest.csv",
            expected=["Tally verification passed."],
            unexpected=["Traceback"],
        ),
        TestCase(
            name="near_unanimous_fixable",
            input_file=f"{g}/near_unanimous_fixable.csv",
            output_file=f"{o}/near_unanimous_fixable.csv",
            expected=[
                "Tally verification passed.",
                "Borrowed 3 contrasting ballot(s).",
            ],
            unexpected=[
                "Traceback",
                "Warning: the following contests remain near-unanimous",
            ],
        ),
        TestCase(
            name="near_unanimous_unavoidable",
            input_file=f"{g}/near_unanimous_unavoidable.csv",
            output_file=f"{o}/near_unanimous_unavoidable.csv",
            expected=[
                "Tally verification passed.",
                "WARNING: the following contests remain near-unanimous",
            ],
            unexpected=["Traceback"],
        ),
        TestCase(
            name="precinct_redaction",
            input_file=f"{g}/precinct_redaction.csv",
            output_file=f"{o}/precinct_redaction.csv",
            redact_flags=["--redact-on-precinct"],
            check_flags=["--redact-on-precinct"],
            expected=[
                "Tally verification passed.",
                "Rare ballot style/precinct combinations (1 of 3 total):",
            ],
            unexpected=["Traceback"],
        ),
        TestCase(
            name="ballot_type_present",
            input_file=f"{g}/ballot_type_present.csv",
            output_file=f"{o}/ballot_type_present.csv",
            expected=[
                "Tally verification passed.",
                "WARNING: Leakage: ballot types [1, 2] all share the same contest pattern",
            ],
            unexpected=["Traceback"],
        ),
        TestCase(
            name="named_style",
            input_file=f"{g}/named_style.csv",
            output_file=f"{o}/named_style.csv",
            redact_flags=["--stylecol", "7"],
            check_flags=["--stylecol", "6"],
            expected=[
                "Tally verification passed.",
                "WARNING: Leakage: named styles [NS-A, NS-B] all share the same contest pattern",
            ],
            unexpected=["Traceback"],
        ),
        TestCase(
            # --no-contest-balancing still borrows the minimum needed to meet
            # the mandatory total floor (Rule a), just without per-contest or
            # unanimity balancing.  A rare style below the floor borrows enough
            # common ballots to reach it.
            name="no_balancing_meets_floor",
            input_file=f"{g}/needs_borrowing.csv",
            output_file=f"{o}/no_balancing_meets_floor.csv",
            redact_flags=["--no-contest-balancing"],
            expected=[
                "Tally verification passed.",
                "Ballots borrowed from common styles: 4",
                "Total ballots in aggregate: 10",
            ],
            unexpected=["Traceback", "WARNING"],
        ),
        TestCase(
            # Floor is enforced (rare 8 -> borrow 2 -> 10) but the near-unanimous
            # President contest is deliberately left unbalanced (Rule c skipped).
            name="no_balancing_near_unanimous",
            input_file=f"{g}/near_unanimous_fixable.csv",
            output_file=f"{o}/no_balancing_near_unanimous.csv",
            redact_flags=["--no-contest-balancing"],
            expected=[
                "Tally verification passed.",
                "Ballots borrowed from common styles: 2",
                "Total ballots in aggregate: 10",
            ],
            unexpected=["Traceback", "WARNING"],
        ),
        TestCase(
            # Every common style sits at exactly the floor (10), so no individual
            # donor has surplus.  Reaching the floor requires pulling a whole
            # blocked style; rare 1 + blocked 10 -> aggregate of 11.
            name="no_balancing_blocked_pull",
            input_file="test_case_cvr.csv",
            output_file=f"{o}/no_balancing_blocked_pull.csv",
            redact_flags=["--no-contest-balancing"],
            expected=[
                "Tally verification passed.",
                "Ballots borrowed from common styles: 10",
                "Total ballots in aggregate: 11",
            ],
            unexpected=["Traceback", "WARNING"],
        ),
        TestCase(
            # Fringe District is on 5 cards: emptied everywhere, "Redacted" in
            # the aggregation line.  Ballots 46-47 stay rare without it and are
            # grouped; 48-50 were rare only because of it and stay visible.
            name="rare_contest",
            input_file=f"{g}/rare_contest.csv",
            output_file=f"{o}/rare_contest.csv",
            expected=[
                "'Fringe District': 5 card(s)",
                "These contests are redacted",
                "Rare ballot styles (1 of 3 total):",
                "Total ballots in aggregate: 10",
                "Tally verification passed.",
            ],
            unexpected=["Traceback", "WARNING: could not find enough ballots"],
            file_checks=[
                _contest_redacted("Fringe District"),
                _rows_redacted(["46", "47"]),
                _rows_visible(["48", "49", "50"]),
            ],
        ),
        TestCase(
            # No ballot is rare once Fringe is set aside, so an aggregation line
            # is added: "Redacted" for Fringe, 0 everywhere else.
            name="rare_contest_only",
            input_file=f"{g}/rare_contest_only.csv",
            output_file=f"{o}/rare_contest_only.csv",
            expected=[
                "'Fringe District': 3 card(s)",
                "An aggregation line standing for no ballots will be added",
                "Tally verification passed.",
            ],
            unexpected=["Traceback", "Rare ballot styles", "WARNING"],
            file_checks=[
                _contest_redacted("Fringe District"),
                _aggregation_zero_except("Fringe District"),
                _rows_visible(["46", "47", "48"]),
            ],
        ),
        TestCase(
            # --keep-rare-contests reproduces the output from before the change.
            name="keep_rare_contests_unchanged",
            input_file=f"{g}/rare_contest.csv",
            output_file=f"{o}/rare_contest_keep.csv",
            redact_flags=["--keep-rare-contests"],
            check_flags=["--keep-rare-contests"],
            expected=[
                "WARNING: --keep-rare-contests was given",
                "Tally verification passed.",
            ],
            unexpected=["Traceback"],
            file_checks=[
                _same_as(f"{EXPECTED_DIR}/rare_contest_keep_rare_contests.csv"),
            ],
        ),
        TestCase(
            name="keep_rare_contests_unchanged_no_rare_ballots",
            input_file=f"{g}/rare_contest_only.csv",
            output_file=f"{o}/rare_contest_only_keep.csv",
            redact_flags=["--keep-rare-contests"],
            check_flags=["--keep-rare-contests"],
            expected=["Tally verification passed."],
            unexpected=["Traceback"],
            file_checks=[
                _same_as(f"{EXPECTED_DIR}/rare_contest_only_keep_rare_contests.csv"),
            ],
        ),
        TestCase(
            # A contest present on no card (a county emptied it) is left alone.
            name="county_blanked_contest_left_alone",
            input_file=f"{g}/county_blanked_contest.csv",
            output_file=f"{o}/county_blanked_contest.csv",
            expected=["Tally verification passed."],
            unexpected=["Traceback", "Contests present on fewer than"],
            file_checks=[_no_redacted_anywhere],
        ),
        TestCase(
            # By default the 3 ballots with the rare label BT-9 (CvrNumbers
            # 23-25) are treated as rare: aggregated, votes starred, the
            # BallotType column kept.
            name="rare_ballot_type_aggregated",
            input_file=f"{g}/rare_ballot_type.csv",
            output_file=f"{o}/rare_ballot_type.csv",
            expected=[
                "'BT-9': 3 ballot(s)",
                "These ballots are treated as rare",
                "Grouping these ballots protects only the CVR.",
                "Tally verification passed.",
            ],
            unexpected=["Traceback"],
            file_checks=[
                _rows_redacted(["23", "24", "25"]),
                _has_header_column("BallotType"),
            ],
        ),
        TestCase(
            # With --drop-ballottype the column goes instead, and the BT-9
            # ballots stay visible: their contest pattern is common.
            name="drop_ballottype",
            input_file=f"{g}/rare_ballot_type.csv",
            output_file=f"{o}/rare_ballot_type_dropped.csv",
            redact_flags=["--drop-ballottype"],
            expected=[
                "'BT-9': 3 ballot(s)",
                "dropped from the output (--drop-ballottype)",
                "Dropping the column protects only the CVR.",
                "Output written to",
            ],
            unexpected=["Traceback", "Rare ballot styles"],
            file_checks=[
                _no_header_column("BallotType"),
                _rows_visible(["23", "24", "25"]),
                _no_redacted_anywhere,
            ],
        ),
        TestCase(
            # The same for a --stylecol column, alongside a rare style.
            name="drop_ballottype_named_style",
            input_file=f"{g}/named_style.csv",
            output_file=f"{o}/named_style_dropped.csv",
            redact_flags=["--stylecol", "7", "--drop-ballottype"],
            expected=["'NS-RARE': 6 ballot(s)", "Tally verification passed."],
            unexpected=["Traceback"],
            file_checks=[
                _no_header_column("BallotType"),
                _no_header_column("NamedStyle"),
            ],
        ),
        TestCase(
            name="blocked_style",
            input_file=f"{g}/blocked_style.csv",
            output_file=f"{o}/blocked_style.csv",
            expected=[
                "Tally verification passed.",
            ],
            unexpected=[
                "Traceback",
                "WARNING: could not find enough ballots",
            ],
        ),
    ]


def main() -> None:
    # Start from an empty output directory: a redaction now refuses to replace
    # an existing output file unless --force is given, and leftovers from an
    # earlier run would make every test look like that refusal.
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Regenerating test input files...")
    rc, output = _run(["python", "generate_test_cvrs.py"])
    if rc != 0:
        print(f"generate_test_cvrs.py failed:\n{output}")
        sys.exit(1)
    print(output.rstrip())
    print()

    passed = 0
    failed = 0
    for tc in _make_test_cases():
        if run_test(tc):
            passed += 1
        else:
            failed += 1

    for ctc in _make_command_tests():
        if run_command_test(ctc):
            passed += 1
        else:
            failed += 1

    # The web version's JavaScript against this one, on the generated files.
    if shutil.which("node") is None:
        print("SKIP  web_matches_python (node is not installed)")
    elif run_command_test(
        CommandTest(
            name="web_matches_python",
            cmd=["node", "tests/web_matches_python.js"],
            expected=["Web cross-check:", " 0 failed."],
        )
    ):
        passed += 1
    else:
        failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
