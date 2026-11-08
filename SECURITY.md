# Security and privacy

anonymize_cvr runs on unredacted cast vote records (CVRs), often on computers in county election
offices. Two kinds of problem matter most: the tool itself being turned against the machine and data
it runs on, and its output or its check being insufficiently redacted, so that it could be used to
reveal how someone voted. The redaction requirement comes from the Colorado Open Records Act
(C.R.S. 24-72-205.5).

## Reporting a problem privately

Please report privately, not in a public issue, using GitHub's private vulnerability reporting for
this repository: the **Security** tab, then **Report a vulnerability**.

Please don't include real CVR rows, imprinted IDs or other ballot details in a report. A
description, or a small synthetic example, is enough.

## What to report

Most serious: anything that lets input make the tool act as malware on the machine running it, for
example:

- a parsing problem in how the tool, or a library it uses, reads input files (CSV), command-line
  options or file paths, that lets crafted input make it run code, read or write files it
  shouldn't, send data over the network, or change other files;
- a way to make the tool hang or exhaust memory or disk while election staff depend on it.

Then, problems with its redaction:

- output that doesn't meet the minimum group size it was asked to enforce, or aggregation that can
  be reversed;
- check mode reporting that no redaction is needed when the minimum isn't met.

## Problems in a published CVR

If you find a published CVR that exposes voters, contact the county that published it directly and
privately. This project can't change files already posted elsewhere, and public reports could add to
the exposure.

## What to expect

This is a volunteer project. We'll acknowledge reports as soon as we can, work on a fix or
mitigation, coordinate disclosure with you, and credit you if you wish.

## Vendored code

The browser version, `anonymize_cvr.html`, includes an unmodified copy of Papa Parse 5.4.1 (MIT
license) to read CSV files. Upstream:

https://github.com/mholt/PapaParse

The copy is not updated automatically, because Dependabot can't see code pasted into an HTML file.
When Papa Parse publishes a security fix, the copy has to be replaced by hand. Everything else in
the project uses only the Python standard library.

## Supported versions

Fixes are made on the main branch.
