# Releasing Pennyworth

This is the maintainer guide for cutting a release. Pennyworth ships to
[PyPI](https://pypi.org/project/pennyworth/) so users can simply:

```bash
pipx install 'pennyworth[app]'
alfred app
```

The release chain is **tag-driven and automated** — pushing a `vX.Y.Z` tag builds,
tests, publishes to PyPI, and cuts a GitHub Release. Publishing uses **PyPI Trusted
Publishing (OIDC)**, so there is no API token stored anywhere.

---

## One-time setup

Do this once, before the first PyPI release.

### 1. Register the Trusted Publisher on PyPI

PyPI needs to trust this repo's release workflow. Because the project doesn't exist
on PyPI yet, use a **pending publisher**:

1. Go to <https://pypi.org/manage/account/publishing/>.
2. Add a new pending publisher with:
   - **PyPI Project Name:** `pennyworth`
   - **Owner:** `elbazon`
   - **Repository name:** `pennyworth`
   - **Workflow name:** `release.yml`
   - **Environment name:** `pypi`
3. (Optional, for dry runs) Repeat on <https://test.pypi.org/manage/account/publishing/>
   with environment name `testpypi`.

The first successful publish converts the pending publisher into a real one and
creates the project.

### 2. Create the GitHub environments

In the repo: **Settings → Environments → New environment**. Create:

- `pypi`
- `testpypi` (only if you want TestPyPI dry runs)

These names must match the `environment:` blocks in `.github/workflows/release.yml`.
You can add required reviewers to the `pypi` environment if you want a human to
approve every production publish — recommended.

---

## Cutting a release

### 1. Land everything on `master`

The release builds from the tagged commit. Make sure `master` is green and holds
everything you want in the release.

### 2. Write the changelog entry

Add a `## [X.Y.Z]` section to [`CHANGELOG.md`](../CHANGELOG.md) following the
existing format. The GitHub Release notes are extracted verbatim from this section,
and `cut-release.sh` refuses to proceed without it.

### 3. Bump + tag

```bash
scripts/cut-release.sh X.Y.Z
```

This bumps the version in `pyproject.toml` and `src/pennyworth/__init__.py`
(the two must always agree with the tag — the workflow enforces it), commits the
bump, and creates an annotated `vX.Y.Z` tag. It does **not** push.

### 4. Push

```bash
git push origin master
git push origin vX.Y.Z
```

Pushing the tag fires the **Release** workflow. It will:

1. Verify the tag matches the package version.
2. Run lint, format check, and the full test matrix.
3. Build the wheel + sdist.
4. Publish to PyPI (via OIDC, no token).
5. Cut a GitHub Release with the changelog notes and the built artifacts attached.

Watch it under the **Actions** tab. When it's green, `pipx install pennyworth`
works for the world.

---

## Dry run (optional)

To rehearse against TestPyPI without touching real PyPI:

**Actions → Release → Run workflow**, set target to `testpypi`. This builds, tests,
and publishes to TestPyPI only — no GitHub Release, no real PyPI upload. Install
the result with:

```bash
pipx install --index-url https://test.pypi.org/simple/ \
  --pip-args '--extra-index-url https://pypi.org/simple/' pennyworth
```

---

## If something goes wrong

- **Version mismatch error:** the tag and `pyproject`/`__init__` versions disagree.
  Always bump via `scripts/cut-release.sh` so they stay in lockstep.
- **A PyPI version cannot be re-uploaded.** If a publish is bad, you must bump to a
  new version (e.g. `X.Y.Z+1`) and release again — PyPI forbids overwriting.
- **Trusted Publishing rejected:** confirm the GitHub environment name, repo owner,
  and workflow filename exactly match what's registered on PyPI.
