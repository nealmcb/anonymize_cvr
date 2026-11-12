# Plan: contests and ballot-type labels too rare to protect

Two related changes to `anonymize_cvr`. Both move a protection into the tool that today depends on a
county preparing its CVR by hand before running it.

- **Feature A** drops the columns of any contest that appears on fewer than `min_ballots` cards in
  the whole file.
- **Feature B** detects `BallotType` labels carried by fewer than `min_ballots` ballots, reports
  them, and can drop the column.

## The problem

A contest can reach only a handful of ballots in a county: a district that crosses the county line
and takes in a few houses, say. Grouping rare ballots into an aggregate row cannot protect such a
contest, because the contest is rarer than the group. Its totals pass straight through the
aggregate row, and every voter it reached is in that row. Contest balancing cannot help either:
it borrows ballots that carry the contest, and there are not enough of them in the file.

The same holds for the style information on redacted rows. A redacted row keeps a `*` in each cell
the ballot had (so the style survives redaction), which shows that the ballot carried the rare
contest even when its votes are hidden.

Counties handle such contests in different ways: some count those few voters' ballots for the
contest in a neighbouring county that the district also covers, so the county's own results show
no votes for it; others report the small totals. Either way, the county's CVR should not reveal
votes, or the presence of the contest, for those few voters. Removing the contest's columns is
consistent with both practices.

A ballot-type label has the same problem from the other side. The rarity check looks only at the
ballot's *fingerprint* (which contests it carries), never at its `BallotType` *label*. A label used
by only a few ballots can ride on a common fingerprint, so those ballots are never grouped, and they
ship with their votes visible next to a label that picks them out. The existing leakage warning
covers only the reverse case (one fingerprint carried under several labels), and only warns.

## Feature A: drop contests too rare to protect

**Rule.** A contest present on more than 0 and fewer than `min_ballots` cards in the file has all
its columns removed from the output: the four header rows, every ballot row and the aggregate row.
The tool reports each removed contest and its card count. On by default; `--keep-rare-contests`
turns it off.

"Present" means the contest is on the card, voted or not: the same notion the style strings use. A
contest present on no card is left as it is; it reveals nothing.

`min_ballots` sets both this threshold and the size of the aggregate. They are equal by definition:
a contest that cannot fill one aggregate cannot be protected by one.

**Order: drop first, then find the rare ballots.** The rare-ballot detection runs as if the
dropped contests had never been in the file. A ballot that was rare only because it carried a
dropped contest then joins a common style and stays visible; one that is still rare on its
remaining contests is grouped as usual. Detecting first and dropping only at output would pull such
ballots out of the visible tallies for no privacy gain.

### Delete the columns, or blank them

A county can instead keep a rare contest's columns and empty every cell in them, as some do now.
Either way the votes, and the presence of the contest, are hidden; with the cells empty, redacted
rows carry no `*` there either. The two differ in what the file says:

| | Blank the columns | Delete the columns |
|---|---|---|
| File layout | Unchanged | The columns disappear; anything keyed to column positions needs the new header |
| What the file claims | That no card carried the contest, which is false and misleads anyone checking ballot styles | Nothing: the contest is visibly absent |
| Results that count those voters in another county (0 here) | Its zeros agree | The contest is missing |
| Results that report the small counts | Its zeros disagree, and a totals check flags them | The contest is missing |

**Default: delete.** It makes no false claim about the ballots. `--rare-contests=blank` empties the
cells instead, for a county that wants to keep its layout or to agree with results that count those
voters elsewhere; the report then says the columns were emptied, not removed. Both are idempotent:
a blanked contest is on no card, so a second run leaves it alone, and a county that blanked the
columns itself needs nothing more.

### Implementation

1. **Count each contest's cards in pass 1, with no extra read of the file.** `build_row_index`
   already gives every row a presence string, one character per contest. A contest's count is the
   sum, over the styles with a `1` in its position, of the number of rows in that style. New
   function: `rare_contests(index, db, min_ballots) -> dict[str, int]`.
2. **Recompute the styles without them.** Blank the rare contests' positions in each style string,
   merge the styles that become identical, and rebuild `style_strings`, `style_id_for_row` and
   `rows_by_privacy_unit` from the merged styles. This happens in memory: CVR files of several
   hundred megabytes occur, and a second read would double the time.
3. **Remove them from everything that reasons about contests.** A new
   `CvrDatabase.drop_contests(names)` takes them out of `contest_names`, `contest_to_columns` and
   `contest_choice_meta`. Contest balancing (`Aggregate`, `CommonPool`), the near-unanimity check
   and the leakage warnings then never see them, with no change to each.
4. **Remove the columns in pass 3.** Add their column indices to `cols_to_remove` in
   `_stream_redacted_output`, the path that already removes `CountingGroup` and `PrecinctPortion`.
   The aggregate row is built at full width (`_build_aggregate_row`), so it must pass through the
   same removal. With `--rare-contests=blank`, empty those cells in every row (the aggregate
   row included) instead of removing them.
5. **Check what ships.** Leave the removed columns out of both `pre_tally` and `post_tally`, so the
   tally check verifies the file that is written rather than passing because both sides still count
   the removed votes.
6. **Check mode.** `--check` lists the contests that would be removed and their card counts, and
   writes nothing. The GUI shows the same in its log.
7. **The web version.** `anonymize_cvr.html` carries its own JavaScript copy of the algorithm and
   has no automated tests. Port the change, and add a small Node test that runs the same synthetic
   files through both versions and compares the outputs.

### Edge cases

- **Ballots left with no contests** after the drop form one style of empty ballots, grouped like any
  other if there are fewer than `min_ballots` of them.
- **Multi-card ballots:** counts are of cards, as everywhere else in the tool.
- **Rows a county has already redacted** (every vote cell blank) carry no contests and are passed
  through, as now.

## Feature B: ballot-type labels too rare to publish

1. **Always detect and report.** Count ballots per `BallotType` value (pass 1 already builds
   `rows_by_ballot_type`) and report every label carried by fewer than `min_ballots` ballots, in
   both check and redact modes and in the GUI log. New function:
   `rare_ballot_type_labels(index, min_ballots) -> dict[str, int]`.
2. **Offer to drop the column.** `--drop-ballottype` removes `BallotType` through the same
   `cols_to_remove` path. The tool works from fingerprints alone, so nothing else depends on the
   column. In the GUI, offer it as a checkbox when rare labels are found.
3. **The default is still to decide.** Dropping the column by default is simplest and safest (it is
   an identifier, not vote data), with `--keep-ballottype` for anyone who needs it; or the tool can
   keep it and only report. A named-style column given with `--stylecol` has the same exposure and
   gets the same treatment.

## Tests (synthetic data only)

- A contest present only on two ballots of a rare style: its columns are removed, the rest of the
  file adds up, and the aggregate row says nothing about it.
- A ballot rare only because of the removed contest rejoins a common style and stays visible.
- `--keep-rare-contests` reproduces today's output exactly.
- `--rare-contests=blank` keeps the layout, with every cell of the rare contests empty, and the
  file adds up without them.
- `--check` lists the rare contests and writes no file.
- A rare `BallotType` label on a common fingerprint is reported, and removed with
  `--drop-ballottype`.
- The Python and web versions produce the same output for every synthetic file.

## Sequence

1. Feature A in the Python version, with its tests.
2. Feature B's detection and `--drop-ballottype`, with its tests.
3. The web version, with the cross-check test.
4. A pull request, reviewed by the tool's other maintainers.
5. A release, sent to counties with a note on what changed.
