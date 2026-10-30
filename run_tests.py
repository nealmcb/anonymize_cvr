#!/usr/bin/env python3
"""
run_tests.py

Regenerates test input files, then runs all test scenarios through
anonymize_cvr.py and verify_redaction.py, checking expected output.

Usage:
    python run_tests.py
"""

import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

GENERATED_DIR = "testCases/generated"
OUTPUT_DIR = "/tmp/anonymize_test_outputs"


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
    setup: Optional[Callable[[], None]] = None
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
            # A NUL byte, or a field over 131,072 characters, raises csv.Error.
            name="bad_input_csv_error",
            cmd=[
                "python",
                "anonymize_cvr.py",
                "--check",
                f"{OUTPUT_DIR}/nul_byte.csv",
            ],
            setup=lambda: _bad_input(
                "nul_byte.csv", lambda d: d.replace(b"Alice", b"Ali\x00ce", 1)
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

    print()
    print(f"Results: {passed} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
