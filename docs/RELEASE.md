# Releasing anonymize_cvr

How a release of `anonymize_cvr` is made, what it contains, and how anyone can check that the
file they run is the file that was released. The first release planned this way is 0.4.0.

## Why releases matter here

A county runs this tool on its unredacted cast vote records, and anyone who uses the redacted
file, to check an audit or the results, needs to know exactly which program wrote it. So does
the county. A copy passed
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
- `SHA256SUMS`: the SHA-256 of each file above, and its two signatures (see Signatures).
- Release notes: what changed, in words a county election office can use; the recommended
  settings (the defaults, and keeping the aggregation line, without which the file's totals no
  longer match the results); how to read `Redacted` in the aggregation line; the warning that ballot
  images need the same redaction.
- A one-page quick start for counties (see Instructions for counties).

The same version is published to PyPI as `anonymize_cvr`.

## Signatures and provenance

All of these are free and public, and each can be checked independently:

1. **Signed tag.** The release tag is signed (`git tag -s`) with the OpenPGP key in item 4, so
   the source it names is signed.
2. **Build provenance from the release workflow.** The workflow attests each file it builds
   (`actions/attest-build-provenance`), recording the repository, the commit and the workflow
   run in Sigstore's public transparency log. Anyone can check a file with:

   ```
   gh attestation verify anonymize_cvr.py -R nealmcb/anonymize_cvr
   ```

3. **PyPI attestations.** Publishing through PyPI's trusted publishing attaches the same kind of
   provenance to the wheel on PyPI.
4. **The maintainer's two signatures on `SHA256SUMS`,** which show that a person approved the
   release and not only that a workflow ran. They are independent: each can be checked without
   the other, and neither depends on the other's provider.
   - **Sigstore,** as `nealmcb@gmail.com` (signed in through Google), recorded in Sigstore's
     public transparency log (`SHA256SUMS.sigstore.json`):

     ```
     sigstore sign SHA256SUMS
     sigstore verify identity SHA256SUMS --cert-identity nealmcb@gmail.com \
       --cert-oidc-issuer https://accounts.google.com
     ```

   - **OpenPGP,** with Neal McBurnett's key `neal@mcburnett.org`, fingerprint
     `EDC0 36EB 2397 A000 D7CD  417B B94C 992F 3314 8156` (`SHA256SUMS.asc`). The fingerprint
     is also published on [Neal's key page](https://neal.mcburnett.org/pgp.html). To sign and
     check:

     ```
     gpg --armor --detach-sign SHA256SUMS
     gpg --verify SHA256SUMS.asc SHA256SUMS
     ```

5. **Optionally, an OpenTimestamps proof** on `SHA256SUMS`, showing it existed by a given time.

Nobody who runs the tool needs to sign anything: a county runs a file that was signed when it was
released, and its output names the version.

## Installing, from most to least transparent

1. **Download one file, check it, read it, run it.** Download `anonymize_cvr.py` (or
   `anonymize_cvr.html`) from the release page, check its SHA-256 against `SHA256SUMS`, read it
   if you wish, and run exactly that file.
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
   commands `anonymize_cvr` and `anonymize_cvr_gui`; on Windows `anonymize_cvr_gui` is a
   launcher that opens the window without a console. The checker runs as
   `python -m verify_redaction original.csv redacted.csv`.

The wheel is built reproducibly from the tag, so anyone can rebuild it and compare hashes.

## PyPI setup (once)

- An account at https://pypi.org with two-factor authentication and a verified email address.
- A pending trusted publisher for the project `anonymize_cvr`: owner `nealmcb`, repository
  `anonymize_cvr`, workflow `release.yml`, environment `pypi`. The `pypi` environment on GitHub
  requires a maintainer's approval before the publishing job runs.
- The same on https://test.pypi.org (a separate account) with environment `testpypi`, for trial
  runs. The `testpypi` environment on GitHub also requires a maintainer's approval, and allows
  the branches `release-trial` and `main`.
- No API token is stored anywhere; old tokens for other projects are not used for this one.

## Trial run

Uploading a version to PyPI can't be undone: the version number can never be used again, and a
broken release can only be yanked and replaced by the next version. Before tagging, try the
whole workflow on TestPyPI:

```
git push origin HEAD:release-trial
```

(Or "Run workflow" on the Actions page, from `main`.) The trial run tests and builds as a
release would, but under the version `X.Y.Z.devN`, N being the workflow's run number, so each
trial gets a new version. After approval of the `testpypi` environment it publishes the wheel to
TestPyPI. Install it from there to try it, on Windows for example:

```
pipx install --index-url https://test.pypi.org/simple/ --pip-args=--pre anonymize_cvr
```

It makes no GitHub Release and doesn't touch PyPI.

## Release steps

1. **Prepare the release in a pull request:** set the version in `anonymize_cvr.py` and
   `anonymize_cvr.html` (they must match, as three numbers: `X.Y.Z`), update the README's status
   and usage, and add the release's entry to `CHANGELOG.md`. Merge it, with CI passing on
   `main`.
2. **Tag the merged commit, on a maintainer's own machine.** The code and the tag travel
   separately: the code reaches `main` through pull requests, and the tag is made afterwards,
   signed, pointing at that commit:

   ```
   git fetch origin
   git tag -s vX.Y.Z -m "anonymize_cvr X.Y.Z" origin/main
   git push origin vX.Y.Z
   ```

   `git tag -s` needs a signing key set up in git (a GPG key, or an SSH key with
   `git config gpg.format ssh`). Don't create the tag from GitHub's web pages: a tag made there
   is not signed. Only maintainers can create `v*` tags: a ruleset forbids creating them and exempts
   the maintainers, so the push prints "Bypassed rule violations ... Cannot create ref due to
   creations being restricted". That message means the exemption was used, not that anything
   failed.
3. **The tag starts the release workflow** (`.github/workflows/release.yml`). It checks that the
   tag is on `main` and matches the version in both tools; runs the tests; builds the wheel;
   writes `SHA256SUMS`; attests each file; waits for a maintainer to approve the `pypi`
   environment (before approving, download the `wheel` artifact from the run and check it), then
   publishes the wheel to PyPI through trusted publishing; and creates a draft
   GitHub Release with the files.
4. **Sign and publish.** The maintainer downloads `SHA256SUMS` from the draft, checks it, signs it
   with Sigstore and with OpenPGP (item 4 under Signatures), adds `SHA256SUMS.sigstore.json` and
   `SHA256SUMS.asc` to the draft, replaces the draft's notes with the release notes, and
   publishes the release.
5. **Announce it,** pointing people to the release page and the quick start rather than to any
   earlier copy.

## Instructions for counties

The quick start covers: installing Python on Windows if
it is missing; downloading `anonymize_cvr.py` from the release page (a fixed link for each
version); optionally checking its SHA-256; starting it; which options to leave as they are
(all of them); keeping the aggregation line; saving the report and the redacted ballot list; and
what to do if Windows warns about the download.

## Open decisions

- Whether the "always write the output file" change goes in the first release.
- Whether counties are offered the web version as well as the Python file.
- Whether copies on a shared drive continue; if so, each is named with its version and linked from
  the release page.
- Who reviews the release notes and the quick start before a release.
