# Releasing anonymize_cvr

How a release of `anonymize_cvr` is made, what it contains, and how anyone can check that the
file they run is the file that was released. The first release planned this way is 0.4.0.

## Why releases matter here

A county runs this tool on its unredacted cast vote records, and verifiers check the audit with
the file it produces. Both need to know exactly which program wrote that file. A copy passed
around by a shared-drive link can't show that: the link can point at different contents over
time, and nothing ties the copy to a commit. A release gives each version a fixed number, a fixed
set of files, published hashes and signatures, and notes on what changed.

The first row of every redacted CVR names the version that wrote it (`anonymize_cvr-v0.4.0`), so
every released version needs its own number, and the version in `anonymize_cvr.py` and
`anonymize_cvr.html` must match.

## What a release contains

A GitHub Release on `nealmcb/anonymize_cvr`, tagged `vX.Y.Z` on `main`, with:

- `anonymize_cvr.py`: the whole tool in one file. It uses only Python's standard library (tkinter
  for the window), so nothing else needs installing.
- `anonymize_cvr.html`: the same tool for a web browser, run offline from the file, with nothing
  installed. `tests/web_matches_python.js` checks that it writes the same output as the Python
  version.
- `verify_redaction.py`: the checker for a redacted file.
- The wheel built for PyPI (see below).
- `SHA256SUMS`: the SHA-256 of each file above, and its signature (see Signatures).
- Release notes: what changed, in words a county election office can use; the recommended
  settings (the defaults: contest balancing on, and the aggregation line kept in the copy sent to
  the audit verifiers); how to read `Redacted` in the aggregation line; the warning that ballot
  images need the same redaction.
- A one-page quick start for counties (see Instructions for counties).

The same version is published to PyPI as `anonymize_cvr`.

## Signatures and provenance

All of these are free and public, and each can be checked independently:

1. **Signed tag.** The release tag is signed (`git tag -s`), so the source it names is signed.
2. **Build provenance from the release workflow.** The workflow attests each file it builds
   (`actions/attest-build-provenance`), recording the repository, the commit and the workflow
   run in Sigstore's public transparency log. Anyone can check a file with:

   ```
   gh attestation verify anonymize_cvr.py -R nealmcb/anonymize_cvr
   ```

3. **PyPI attestations.** Publishing through PyPI's trusted publishing attaches the same kind of
   provenance to the wheel on PyPI.
4. **A maintainer's signature on `SHA256SUMS`.** A maintainer signs the hash list with Sigstore,
   using a personal identity, which shows that a person approved the release and not only that a
   workflow ran:

   ```
   sigstore sign SHA256SUMS
   sigstore verify identity SHA256SUMS --cert-identity MAINTAINER_EMAIL \
     --cert-oidc-issuer https://accounts.google.com
   ```

5. **Optionally, an OpenTimestamps proof** on `SHA256SUMS`, showing it existed by a given time.

Nobody who runs the tool needs to sign anything: a county runs a file that was signed when it was
released, and its output names the version.

## Installing, from most to least transparent

1. **Download one file, check it, read it, run it.** Download `anonymize_cvr.py` (or
   `anonymize_cvr.html`) from the release page, check its SHA-256 against `SHA256SUMS`, read it
   if you wish, and run exactly that file. This is the recommended path for county offices.
2. **From PyPI, as a wheel.** Only wheels are published, never a source package, so installing
   runs no code: a wheel is a zip file that is unpacked, holding `anonymize_cvr.py`,
   `verify_redaction.py`, the package metadata and a `RECORD` file with each file's hash. There
   are no dependencies. To read it before trusting it:

   ```
   pip download anonymize_cvr==X.Y.Z --no-deps --only-binary :all:
   unzip -l anonymize_cvr-X.Y.Z-py3-none-any.whl
   ```

   then check that the `anonymize_cvr.py` inside is byte-identical to the signed file on the
   release page, and install that wheel file, or install with `--require-hashes` and the
   published hash. `pipx install anonymize_cvr` or `uv tool install anonymize_cvr` installs the
   commands `anonymize_cvr`, `anonymize_cvr_gui` and `verify-redaction`; on Windows
   `anonymize_cvr_gui` is a launcher that opens the window without a console.
3. **A signed Windows program** (planned for a later release, see below). A bundled `.exe`
   carries its own Python interpreter and can't practically be read, so it asks for the most
   trust; its signature says who built it, not what it does. If one is offered, it is built in the
   release workflow, with an attestation, from the same tagged source.

The wheel is built reproducibly from the tag, so anyone can rebuild it and compare hashes.

## PyPI setup (once)

- An account at https://pypi.org with two-factor authentication and a verified email address.
- A pending trusted publisher for the project `anonymize_cvr`: owner `nealmcb`, repository
  `anonymize_cvr`, workflow `release.yml`, environment `pypi`. The `pypi` environment on GitHub
  requires a maintainer's approval before the publishing job runs.
- The same on https://test.pypi.org for a trial release first.
- No API token is stored anywhere; old tokens for other projects are not used for this one.

## Release steps

1. Merge the pull requests that make up the release, with CI passing on `main`.
2. Set the version in `anonymize_cvr.py` and `anonymize_cvr.html` (they must match), update the
   README's status and usage, and add the release's entry to `CHANGELOG.md`.
3. Push a signed tag `vX.Y.Z`. The release workflow (`.github/workflows/release.yml`) then:
   runs the tests; builds the wheel; writes `SHA256SUMS`; attests each file; publishes the wheel
   to PyPI through trusted publishing, after a maintainer approves the `pypi` environment; and
   creates a draft GitHub Release with the files.
4. A maintainer downloads `SHA256SUMS` from the draft, checks it, signs it with Sigstore, adds
   the signature and certificate to the draft, and publishes the release.
5. Send counties the release page's link and the quick start, in place of any earlier copy.

## Instructions for counties

The quick start replaces instructions sent by email. It covers: installing Python on Windows if
it is missing; downloading `anonymize_cvr.py` from the release page (a fixed link for each
version); optionally checking its SHA-256; starting it; which options to leave as they are
(contest balancing on); what to send the audit verifiers (the redacted file with its aggregation
line); and what to do if Windows warns about the download. It links the demonstration video.

## Later: signing for Windows (planned for 0.5)

Windows SmartScreen and Defender can't check a signature on a `.py` file; only a program such as
an `.exe` built with PyInstaller can carry an Authenticode signature. Options, as of late 2026:

- **Azure Artifact Signing** (formerly Trusted Signing): about $9.99 a month; open to
  organizations in the USA, Canada, the EU and the UK, and to individual developers in the USA
  and Canada, after identity validation; signs from GitHub Actions with no hardware token.
- **An OV certificate** from a certificate authority: about $150 to $300 a year, with the key on
  a hardware token or a cloud HSM.
- **An EV certificate** no longer bypasses SmartScreen (since 2024), so it is not worth its
  higher price for that purpose.
- **The SignPath Foundation** offers free OV-level signing to qualifying open-source projects.

With any of these, SmartScreen still warns about new files until the publisher's reputation
builds over consecutive releases. Whether a signed `.exe` is needed at all depends on whether
county offices can run Python; ask their IT staff before choosing.

## Open decisions

- The version number of the first release (0.4.0, or 1.0.0 to signal that counties should use it).
- Whether the "always write the output file" change goes in the first release.
- Whether counties are offered the web version as well as the Python file.
- Whether copies on a shared drive continue; if so, each is named with its version and linked from
  the release page.
- Who reviews the release notes and the quick start before a release.
- Whether pull requests are merged with merge commits, or rebased first to keep history linear.
