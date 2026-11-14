.PHONY: test generate lint clean \
    test-no-redaction test-needs-borrowing test-rare-unique-contest \
    test-near-unanimous-fixable test-near-unanimous-unavoidable \
    test-precinct-redaction test-ballot-type-present test-named-style \
    test-no-balancing-skips-borrowing test-no-balancing-near-unanimous \
    test-blocked-style test-rare-contest test-rare-contest-only \
    test-keep-rare-contests test-county-blanked-contest test-rare-ballot-type \
    test-drop-ballottype test-web

GENERATED = testCases/generated
OUTPUT = /tmp/anonymize_test_outputs

test: clean generate \
    test-no-redaction \
    test-needs-borrowing \
    test-rare-unique-contest \
    test-near-unanimous-fixable \
    test-near-unanimous-unavoidable \
    test-precinct-redaction \
    test-ballot-type-present \
    test-named-style \
    test-no-balancing-skips-borrowing \
    test-no-balancing-near-unanimous \
    test-blocked-style \
    test-rare-contest \
    test-rare-contest-only \
    test-keep-rare-contests \
    test-county-blanked-contest \
    test-rare-ballot-type \
    test-drop-ballottype \
    test-web

generate:
	python generate_test_cvrs.py

lint:
	mypy anonymize_cvr.py verify_redaction.py run_tests.py generate_test_cvrs.py
	black anonymize_cvr.py verify_redaction.py run_tests.py generate_test_cvrs.py

test-no-redaction:
	python anonymize_cvr.py --check $(GENERATED)/no_redaction.csv

test-needs-borrowing:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py \
	    $(GENERATED)/needs_borrowing.csv \
	    $(OUTPUT)/needs_borrowing.csv
	python anonymize_cvr.py --check \
	    $(OUTPUT)/needs_borrowing.csv
	python verify_redaction.py \
	    $(GENERATED)/needs_borrowing.csv \
	    $(OUTPUT)/needs_borrowing.csv

test-rare-unique-contest:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py \
	    $(GENERATED)/rare_unique_contest.csv \
	    $(OUTPUT)/rare_unique_contest.csv
	python anonymize_cvr.py --check \
	    $(OUTPUT)/rare_unique_contest.csv
	python verify_redaction.py \
	    $(GENERATED)/rare_unique_contest.csv \
	    $(OUTPUT)/rare_unique_contest.csv

test-near-unanimous-fixable:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py \
	    $(GENERATED)/near_unanimous_fixable.csv \
	    $(OUTPUT)/near_unanimous_fixable.csv
	python anonymize_cvr.py --check \
	    $(OUTPUT)/near_unanimous_fixable.csv
	python verify_redaction.py \
	    $(GENERATED)/near_unanimous_fixable.csv \
	    $(OUTPUT)/near_unanimous_fixable.csv

test-near-unanimous-unavoidable:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py \
	    $(GENERATED)/near_unanimous_unavoidable.csv \
	    $(OUTPUT)/near_unanimous_unavoidable.csv
	python anonymize_cvr.py --check \
	    $(OUTPUT)/near_unanimous_unavoidable.csv
	python verify_redaction.py \
	    $(GENERATED)/near_unanimous_unavoidable.csv \
	    $(OUTPUT)/near_unanimous_unavoidable.csv

test-precinct-redaction:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py --redact-on-precinct \
	    $(GENERATED)/precinct_redaction.csv \
	    $(OUTPUT)/precinct_redaction.csv
	python anonymize_cvr.py --check --redact-on-precinct \
	    $(OUTPUT)/precinct_redaction.csv
	python verify_redaction.py \
	    $(GENERATED)/precinct_redaction.csv \
	    $(OUTPUT)/precinct_redaction.csv

test-ballot-type-present:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py \
	    $(GENERATED)/ballot_type_present.csv \
	    $(OUTPUT)/ballot_type_present.csv
	python anonymize_cvr.py --check \
	    $(OUTPUT)/ballot_type_present.csv
	python verify_redaction.py \
	    $(GENERATED)/ballot_type_present.csv \
	    $(OUTPUT)/ballot_type_present.csv

test-named-style:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py --stylecol 7 \
	    $(GENERATED)/named_style.csv \
	    $(OUTPUT)/named_style.csv
	python anonymize_cvr.py --check --stylecol 6 \
	    $(OUTPUT)/named_style.csv
	python verify_redaction.py \
	    $(GENERATED)/named_style.csv \
	    $(OUTPUT)/named_style.csv

test-no-balancing-skips-borrowing:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py --no-contest-balancing \
	    $(GENERATED)/needs_borrowing.csv \
	    $(OUTPUT)/no_balancing_skips_borrowing.csv
	python anonymize_cvr.py --check \
	    $(OUTPUT)/no_balancing_skips_borrowing.csv
	python verify_redaction.py \
	    $(GENERATED)/needs_borrowing.csv \
	    $(OUTPUT)/no_balancing_skips_borrowing.csv

test-no-balancing-near-unanimous:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py --no-contest-balancing \
	    $(GENERATED)/near_unanimous_fixable.csv \
	    $(OUTPUT)/no_balancing_near_unanimous.csv
	python anonymize_cvr.py --check \
	    $(OUTPUT)/no_balancing_near_unanimous.csv
	python verify_redaction.py \
	    $(GENERATED)/near_unanimous_fixable.csv \
	    $(OUTPUT)/no_balancing_near_unanimous.csv

test-blocked-style:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py \
	    $(GENERATED)/blocked_style.csv \
	    $(OUTPUT)/blocked_style.csv
	python anonymize_cvr.py --check \
	    $(OUTPUT)/blocked_style.csv
	python verify_redaction.py \
	    $(GENERATED)/blocked_style.csv \
	    $(OUTPUT)/blocked_style.csv

test-rare-contest:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py \
	    $(GENERATED)/rare_contest.csv \
	    $(OUTPUT)/rare_contest.csv
	python anonymize_cvr.py --check \
	    $(OUTPUT)/rare_contest.csv
	python verify_redaction.py \
	    $(GENERATED)/rare_contest.csv \
	    $(OUTPUT)/rare_contest.csv

test-rare-contest-only:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py \
	    $(GENERATED)/rare_contest_only.csv \
	    $(OUTPUT)/rare_contest_only.csv
	python anonymize_cvr.py --check \
	    $(OUTPUT)/rare_contest_only.csv
	python verify_redaction.py \
	    $(GENERATED)/rare_contest_only.csv \
	    $(OUTPUT)/rare_contest_only.csv

test-keep-rare-contests:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py --keep-rare-contests \
	    $(GENERATED)/rare_contest.csv \
	    $(OUTPUT)/rare_contest_keep.csv
	cmp $(OUTPUT)/rare_contest_keep.csv tests/expected/rare_contest_keep_rare_contests.csv

test-county-blanked-contest:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py \
	    $(GENERATED)/county_blanked_contest.csv \
	    $(OUTPUT)/county_blanked_contest.csv
	python verify_redaction.py \
	    $(GENERATED)/county_blanked_contest.csv \
	    $(OUTPUT)/county_blanked_contest.csv

test-rare-ballot-type:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py --check $(GENERATED)/rare_ballot_type.csv
	python anonymize_cvr.py \
	    $(GENERATED)/rare_ballot_type.csv \
	    $(OUTPUT)/rare_ballot_type.csv
	python anonymize_cvr.py --check \
	    $(OUTPUT)/rare_ballot_type.csv
	python verify_redaction.py \
	    $(GENERATED)/rare_ballot_type.csv \
	    $(OUTPUT)/rare_ballot_type.csv

test-drop-ballottype:
	mkdir -p $(OUTPUT)
	python anonymize_cvr.py --drop-ballottype \
	    $(GENERATED)/rare_ballot_type.csv \
	    $(OUTPUT)/rare_ballot_type_dropped.csv
	python verify_redaction.py \
	    $(GENERATED)/rare_ballot_type.csv \
	    $(OUTPUT)/rare_ballot_type_dropped.csv

# The web version (anonymize_cvr.html) against the Python version, on every
# generated file.  Needs node.
test-web:
	node tests/web_matches_python.js

clean:
	rm -f $(OUTPUT)/*.csv
