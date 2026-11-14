# Plan: contests and ballot-type labels too rare to protect

Two related changes to `anonymize_cvr`. Both move a protection into the tool that today depends on a
county preparing its CVR by hand before running it.

- **Feature A** redacts any contest that appears on fewer than `min_ballots` cards in the whole
  file: its cells are emptied on every ballot row, and its columns in the aggregation line say
  `Redacted`.
- **Feature B** treats a ballot whose `BallotType` label is carried by fewer than `min_ballots`
  ballots as rare, so it is grouped like any rare ballot; or, on request, drops the column instead.

## The problem

A contest can reach only a handful of ballots in a county: a district that crosses the county line
and takes in a few houses, say. Grouping rare ballots into an aggregate row cannot protect such a
contest, because the contest is rarer than the group. Its totals pass straight through the
aggregate row, and every voter it reached is in that row. Contest balancing cannot help either:
it borrows ballots that carry the contest, and there are not enough of them in the file.

Counties handle such contests by counting those few voters' ballots for the contest in a
neighbouring county that the district also covers, so the county's own results show no votes for
it. The county's CVR must not reveal those voters' votes either.

A ballot-type label has the same problem from the other side. The rarity check looks only at the
ballot's *fingerprint* (which contests it carries), never at its `BallotType` *label*. A label used
by only a few ballots can ride on a common fingerprint, so those ballots are never grouped, and they
ship with their votes visible next to a label that picks them out. The existing leakage warning
covers only the reverse case (one fingerprint carried under several labels), and only warns.

## Feature A: redact contests too rare to protect

**Rule.** For a contest present on more than 0 and fewer than `min_ballots` cards in the file:

- its columns stay in the file, in all four header rows;
- every one of its cells is emptied on every ballot row;
- in the aggregation line, each of its choice columns says `Redacted`;
- if the file has no aggregation line (no ballot was rare enough to need one), the tool adds one
  that says `Redacted` in those columns and leaves every other vote column empty. It stands
  for no ballots, so it carries no contest; a 0 would say some ballot carries it.

The tool reports each redacted contest and its card count. On by default; `--keep-rare-contests`
turns it off.

"Present" means the contest is on the card, voted or not: the same notion the style strings use. A
contest present on no card is left as it is; it reveals nothing.

`min_ballots` sets both this threshold and the size of the aggregate. They are equal by definition:
a contest that cannot fill one aggregate cannot be protected by one.

**Why mark the contest `Redacted`, rather than delete or silently blank it.** Deleting the
contest's columns would claim that no one in the county could vote in it. Emptying its cells alone
would claim that no card carried it. Both are false. With `Redacted` in the aggregation line, the
file says what happened: the contest was redacted, and an empty cell in its columns may be a card
that carried it. That reading holds for any column whose aggregation entry says `Redacted`. The
file also keeps its layout, so anything keyed to column positions still works.

**Readers of the file.** A tool that reads redacted CVRs must take `Redacted` as unknown, never as
zero, and should show it to its user rather than drop it. A tool that breaks on the word, or
counts the added aggregation line as a ballot, needs fixing; the aggregation line has always been
special (it stands for many ballots), and the added one stands for none.

**Order: set the contests aside first, then find the rare ballots.** The rare-ballot detection runs
as if the redacted contests had never been in the file. A ballot that was rare only because it
carried a redacted contest then joins a common style and stays visible; one that is still rare on
its remaining contests is grouped as usual. Detecting first and redacting only at output would pull
such ballots out of the visible tallies for no privacy gain.

**Ballot images.** A visible ballot that carried a redacted contest shows nothing of it in the CVR,
but an image of that ballot shows the contest and the marks in it. The tool counts these ballots in
its report, and `--redacted-list` lists them along with the redacted ballots, so a county that
redacts the images on the list covers them too.

### Implementation

1. **Count each contest's cards in pass 1, with no extra read of the file.** `build_row_index`
   already gives every row a presence string, one character per contest. A contest's count is the
   sum, over the styles with a `1` in its position, of the number of rows in that style. New
   function: `rare_contests(index, db, min_ballots) -> dict[str, int]`.
2. **Recompute the styles without them.** Blank the rare contests' positions in each style string,
   merge the styles that become identical, and rebuild `style_strings`, `style_id_for_row` and
   `rows_by_privacy_unit` from the merged styles. This happens in memory: CVR files of several
   hundred megabytes occur, and a second read would double the time.
3. **Hide them from everything that reasons about contests.** A new
   `CvrDatabase.set_aside_contests(names)` takes them out of `contest_names`, `contest_to_columns`
   and `contest_choice_meta`. Contest balancing (`Aggregate`, `CommonPool`), the near-unanimity
   check and the leakage warnings then never see them, with no change to each.
4. **Write them in pass 3.** In `_stream_redacted_output`, empty their cells on every ballot row,
   visible or redacted (a redacted row gets no `*` there), and write `Redacted` in their columns of
   the aggregation line, which `_build_aggregate_row` would otherwise fill with sums. If there is no
   aggregation line, append one with the same identifier fields an aggregation line has, `Redacted`
   in those columns and every other vote column empty: in a CVR an empty cell means the contest is
   not on the card and 0 means it is there and not voted, and this line stands for no cards.
5. **Check what ships.** Leave the redacted columns out of both `pre_tally` and `post_tally`, so the
   tally check verifies the file that is written rather than passing because both sides still count
   the redacted votes.
6. **Check mode.** `--check` lists the contests that would be redacted and their card counts, and
   writes nothing. The GUI shows the same in its log.
7. **The web version.** `anonymize_cvr.html` carries its own JavaScript copy of the algorithm and
   has no automated tests. Port the change, and add a small Node test that runs the same synthetic
   files through both versions and compares the outputs.

### Edge cases

- **Ballots left with no contests** once the rare ones are set aside form one style of empty
  ballots, grouped like any other if there are fewer than `min_ballots` of them.
- **Multi-card ballots:** counts are of cards, as everywhere else in the tool.
- **Rows a county has already redacted** (every vote cell blank) carry no contests and are passed
  through, as now.
- **A contest a county emptied itself** is present on no card, so the tool leaves it alone; running
  the tool twice gives the same file.

## Feature B: ballot-type labels too rare to publish

1. **Always detect and report.** Count ballots per `BallotType` value (pass 1 already builds
   `rows_by_ballot_type`) and report every label carried by fewer than `min_ballots` ballots, in
   both check and redact modes and in the GUI log. New function:
   `rare_ballot_type_labels(index, min_ballots) -> dict[str, int]`. The count includes rows already
   redacted, which still carry the label; a label left only on redacted rows exposes no votes and is
   not reported. A rare label means redaction is needed, and the report says which remedy applies.
2. **By default, make those ballots rare.** After the rare contests are set aside, each ballot that
   carries a rare label moves into a privacy unit of its own (its style, its precinct and the
   label). Such a unit has fewer than `min_ballots` ballots, so the ballot is grouped into the
   aggregate like any rare ballot, contest balancing included, and its votes are starred. The label
   column stays. What remains of the ballot's old unit stays in it, and is rare in turn if it now
   has fewer than `min_ballots` ballots. Pass 2 finds a row's unit through
   `RowIndex.label_unit_for_row`, so no other code changes.
3. **Or drop the column.** `--drop-ballottype` removes `BallotType` through the `cols_to_remove`
   path that already removes `CountingGroup` and `PrecinctPortion`, and the ballots are then not
   made rare on account of the label: with the label gone, a ballot on a common style stays
   visible. The tool works from fingerprints alone, so nothing else depends on the column. The GUI
   and the web page offer it as a checkbox.
4. **The warning that goes with either remedy, in the report and the GUI:** it protects only the
   CVR. The same label is often printed on the ballot itself (a ballot-style code, a precinct
   number), so any ballot images the county releases carry it too, and a rare label on an image
   identifies the ballot just as it would in the CVR. The county must redact the label on those
   images as well, or better, stop printing a label that a few ballots alone carry. The same holds
   for a rare contest's ballots under Feature A: an image of the ballot shows the contest and the
   marks in it.
5. **Named styles.** A named-style column given with `--stylecol` has the same exposure and gets the
   same treatment: its rare labels make their ballots rare, and `--drop-ballottype` drops it along
   with `BallotType`.

## Tests (synthetic data only)

- A contest present only on two ballots of a rare style: its cells are empty on every row, its
  aggregation entries say `Redacted`, and the rest of the file adds up.
- The same contest in a file with no rare ballots otherwise: an aggregation line is added that says
  `Redacted` in its columns and leaves every other vote column empty.
- A ballot rare only because of the redacted contest rejoins a common style and stays visible.
- `--redacted-list` includes the visible ballots that carried a redacted contest.
- `--keep-rare-contests` reproduces today's output exactly.
- `--check` lists the rare contests and writes no file.
- Running the tool on its own output changes nothing.
- A rare `BallotType` label on a common fingerprint is reported, with the warning about ballot
  images, and `--check` says redaction is needed.
- By default the ballots with that label are aggregated and their votes starred, and the column
  stays; with `--drop-ballottype` the column is gone and those ballots stay visible.
- The Python and web versions produce the same output for every synthetic file.

## Sequence

1. Feature A in the Python version, with its tests.
2. Feature B's detection and `--drop-ballottype`, with its tests.
3. The web version, with the cross-check test.
4. A pull request, reviewed by the tool's other maintainers.
5. A release, sent to counties with a note on what changed, including how to read `Redacted`.
