# Quick start for county election offices

How to redact your cast vote record (CVR) with `anonymize_cvr` before releasing it. It takes a
few minutes.

## 1. Make sure Python is installed (once)

The tool is a Python program. On Windows, type `python` in the search box on the taskbar. If
Python is installed, it opens; close it again. If not, Windows offers to install it from the
Microsoft Store: accept. That version includes everything the tool needs.

## 2. Download the tool

Download `anonymize_cvr.py` from the release page:

RELEASE_PAGE_LINK

Use this page for each new version, not a copy saved earlier or sent by email, so you always know
which version you ran. The version is also noted on the first line of every file the tool produces.

Your browser or Windows may warn that the file could harm your computer, because it is a program.
That is expected for any program downloaded from the web.

**Recommended: check the download.** In PowerShell, in the folder you saved it to:

```
Get-FileHash anonymize_cvr.py -Algorithm SHA256
```

The long number it prints should match the line for `anonymize_cvr.py` in `SHA256SUMS` on the
release page. If it doesn't, don't run the file; download it again from the release page.

## 3. Start it

Double-click `anonymize_cvr.py` in File Explorer. A window titled "CVR Anonymizer" opens. If
double-clicking doesn't start it, open PowerShell in that folder and type:

```
py anonymize_cvr.py
```

## 4. Check the options

Click **(1) Configure Redaction Options**. We recommend you leave everything as it is.

Under **Protections**:

- **Skip contest balancing:** leave it *unchecked*. Checking it offers weaker voter protections.
- **Keep rare contests:** leave it *unchecked*. Checking it offers weaker voter protections.

Under **Precinct portions and ballot types**, each ballot's header or barcode records its precinct
portion and ballot type, so ballot images show them even when the CVR doesn't. Keep the default
choice in each pair:

- **Precinct portions:** "Group rare ballots within their precinct portion". The tool keeps the
  precinct column and groups the ballots that would stand out within it. Choose "Remove the
  precinct column" only if you will never release ballot images with precinct information.
- **Ballot types:** "Group ballots whose ballot type is rare". Choose "Remove the ballot-type
  column" only if you will never release ballot images with ballot-type information.

At the bottom, leave **Minimum Ballots** at 10 unless local laws or rules require a higher number,
and leave **Style Column** empty unless your CVR has a separate named-style column.

Click **Save**.

## 5. Redact

Click **(2) Produce Redacted CVR**, then:

1. **Input CVR File:** choose the CVR exported from the voting system, as a CSV file. The tool
   only reads it; it never changes it.
2. **Save into Folder:** the input's folder is filled in; choose another with **Browse...** if
   you like. The window shows the three files it will write there, named after your export:
   - `<export>-redacted.csv`: the redacted CVR;
   - `<export>-redacted-ballots.txt`: the ballots whose images need redacting if you ever
     release ballot images. Keep it with the redacted CVR even if you don't plan to;
   - `<export>-report.txt`: a record of the run: the version, the options, your export's
     SHA-256, and everything the tool found and did.
3. Click **Run Redaction**. If any of the three files is already there, the tool asks before
   replacing it.

The status box shows the same report as it runs, ends by saying the totals check passed, and
names each file written. Keep all three files together.

If it says no redaction is needed, nothing in your CVR needed redacting, and it writes only the
report.
Your export, without its CountingGroup column (as uploaded to the RLA tool), needs no redaction.

## 6. Excel caution

Don't open the redacted CVR in Excel and save it again: Excel can silently change ballot IDs
such as `3-19-7` into dates (3/19/2007), damaging the file.

## Reading the redacted file

- `*` in place of votes: a ballot that was grouped; its votes are in the `AGGREGATED` line.
  Keep the `AGGREGATED` line: without it the file's totals no longer match reported results.
- A blank cell: the contest is not on that card.
- `Redacted` in the `AGGREGATED` line: a contest on so few ballots countywide
  that its totals are withheld.

## Questions or problems

Report a problem or ask a question at https://github.com/nealmcb/anonymize_cvr/issues
