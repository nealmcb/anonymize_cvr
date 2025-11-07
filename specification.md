# CVR Anonymization Specification

## Goal
Automatically anonymize a CVR (Cast Vote Record) file to meet the Colorado requirement that styles with fewer than 10 ballots per style must be anonymized to protect voter privacy.

## Background
- **Colorado Open Records Act (C.R.S. 24-72-205.5)**: Requires counties to cover or redact before "making available for public inspection" a voted ballot if there are fewer than 10 instances of the ballot's style in the election.
- **Colorado Risk-Limiting Tabulation Audit**: CVRs must be available for public audit purposes while preserving ballot anonymity.

- **[Privacy violations in election results \| Science Advances](https://www.science.org/doi/10.1126/sciadv.adt1512)** Shiro Kuriwaki, Jeffrey B. Lewis, and Michael Morse  on "vote revelation" etc.

## Core Requirements

### 1. Minimum Ballot Threshold
- **Every style and every aggregate must have at least 10 ballots**
- If this is impossible with the available data, the anonymization task should fail with a clear error message
- Never produce an output file that violates the 10-ballot minimum threshold

### 2. Aggregation Strategy
- Rare styles (those with < 10 ballots) must be aggregated to meet the threshold
- **Aggregation can combine:**
  - Multiple rare styles together
  - Rare styles with common (non-rare) styles
- When combining with common styles, prefer popular/common styles that share similar contests
- Strategy: Use similarity-based grouping to preserve statistical properties and maintain auditability
  - Aggregating similar styles preserves vote pattern structure better than mixing dissimilar styles
  - This makes aggregated rows more meaningful and useful for audit purposes
  - We aggregate as few ballots as possible (minimum 10) while still ensuring anonymity

### 3. Style Similarity
- Styles are considered similar based on contest overlap (Jaccard similarity)
- A style signature includes:
  - First 3 characters of the PrecinctPortion (ballot style identifier)
  - Binary pattern indicating which contests appear on the ballot
- When aggregating, prefer combining styles that share more contests

### 4. Contest Diversity (Best Practice)
- Ideally, each contest should appear on at least 10 ballots in each aggregated row
- This helps ensure aggregated rows provide sufficient diversity for anonymity
- This is a best-effort goal - if a contest only appears on very few rare ballots, this may not be achievable without excluding ballots (which we don't do)

## Implementation Details

### Style checking
After reading the file in
- Compute a new unique descriptive style name for each style based solely on which contests have votes.
  Use the naming scheme from the guess_styles game.
- Check that the computed styles each map uniquely to a style name from the cvr.
- If information has been leaked by applying different style names to different ballots which each have the same set of contests, that should be pointed out.

Optionally summarize the cvr:
 * totals by contest for each choice
 * ballot counts for each style encountered, and vote probabilities for each choice across the style.

### Style Signature
A style signature is created from:
- First 3 characters of the PrecinctPortion field
- For each vote column: "1" if the contest appears on the ballot (column is non-empty), "0" if empty

### Aggregation Algorithm
1. Identify rare styles (those with < 10 ballots)
2. If total ballots < 10 and cannot be combined with common styles, fail with error
3. For rare styles:
   - Prefer combining similar rare styles together
   - If needed, combine rare styles with similar common styles
   - Prefer popular/common styles for combination
   - Ensure each aggregate group has >= 10 ballots
4. Create aggregated rows by summing vote counts and anonymizing identifying fields

### Output Format
- Headers preserved at top (version, contests, choices, headers)
- Data rows sorted numerically by CvrNumber
- Aggregated rows placed at the end
- Line terminators preserved from input file (LF, CRLF, or CR)

### Identifying Fields Anonymized
- CvrNumber: Set to "AGGREGATED-N" where N is the aggregate number
- CountingGroup: Set to "AGGREGATED"
- PrecinctPortion: Set to "AGGREGATED-N"
- Other identifying fields (TabulatorNum, BatchId, RecordId, ImprintedId) are anonymized

## Edge Cases and Limitations

### Single Contest Issues
If a single contest has fewer than 10 votes across all ballots, row-level aggregation cannot solve this. This would require a different approach (e.g., contest-level redaction).

### Similarity Measurement
The current similarity metric (Jaccard similarity of contest presence) is a heuristic. More sophisticated metrics could consider:
- Precinct overlap
- Geographic proximity
- Contest importance/weight

## Nebulous Goals and Future Considerations

These are aspirational goals that inform the design but are not strictly required:

### 1. Optimal Style Combination
- When aggregating rare styles, prefer combining similar styles to minimize information loss
- When borrowing from common styles, prefer popular/common styles (those with many ballots)
- The rationale: popular styles provide more "cover" and are less likely to reveal individual voting patterns

### 2. Contest Diversity
- Ideally, each contest should appear on at least 10 ballots in each aggregated row
- This ensures that aggregated rows provide sufficient diversity for anonymity
- However, this may not always be achievable if a contest only appears on very few rare ballots
- Current implementation: warns when contests appear on fewer than 10 ballots, but doesn't fail

### 3. Information Preservation
- When possible, aggregate in ways that preserve as much information as possible about vote patterns
- Combining similar styles (that share contests) helps preserve the structure of the vote data
- This makes aggregated rows more useful for study

### 4. Entropy Considerations
- The "entropy" of each aggregation shouldn't be too low
- One approach mentioned in research: ensure that for each candidate who got at least 20% of the vote, there are at least 3 votes for them in the aggregate
- This ensures it isn't clear how ALL the people voted, even if you know you're one of them
- **Note**: This goal is mentioned but not yet implemented

### 5. Deterministic Output
- The anonymization process should be deterministic (same input produces same output)
- This helps with reproducibility and audit verification

## References
- [Colorado Risk-Limiting Tabulation Audit: Preserving Anonymity of Cast Vote Record](http://www.sos.state.co.us/pubs/rule_making/hearings/2018/20180309BranscombEtAl.pdf) (Branscomb et al., March 9, 2018)
- Colorado Election Rule 21 (CVR definition)
- [C.R.S. 24-72-205.5](https://codes.findlaw.com/co/title-24-government-state/co-rev-st-sect-24-72-205-5/) (Open Records Act requirement)
