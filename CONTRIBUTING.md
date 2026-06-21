# Contributing to Pennyworth

Thank you for lending a hand. Pennyworth is the open-source core of **Alfred**, a
butler-engineer AI companion. This guide covers how to set up, what the project
holds sacred, and how to get a change merged.

## The one rule

Before anything else, internalise the invariant the whole project is built around:

> **The brain is clean by construction.** With no pack attached, the assembled
> prompt contains zero platform specifics — no platform name, no repository, no
> teammate, no tool. Everything a platform contributes flows through its pack and
> *only* through its pack.

This is enforced by `tests/test_clean_brain.py`, and it is the acceptance gate for
any change that touches prompt assembly. If your work makes the no-pack brain
mention a specific platform, repo, person, or tool, the change is wrong — route it
through a pack seam instead. When in doubt, read [`docs/architecture.md`](docs/architecture.md).

## Development setup

Pennyworth uses [Poetry](https://python-poetry.org/) and targets Python 3.11–3.13.

```bash
poetry install --extras app     # core + the desktop app (pywebview)
poetry run alfred --version
```

The agent runner shells out to `claude` by default; install the
[Claude Code](https://claude.com/claude-code) CLI, or point `PENNYWORTH_AGENT` at
another agent command. Packs and your profile install under `PENNYWORTH_HOME`
(default `~/.pennyworth`), so local experimentation never touches your real config
if you set that variable.

## Quality gate

Two commands must pass before any commit. CI runs the same on every push and pull
request across Python 3.11–3.13.

```bash
poetry run ruff check src tests     # lint + import order
poetry run pytest -q                # the full suite, incl. the clean-brain test
```

Keep them green. A red `test_clean_brain` in particular means the invariant above
has been breached.

## Adding a pack seam

The pattern is deliberate and worth following exactly when you extend the pack
contract:

1. Add the field to `pack.Pack` with an **empty default**.
2. Add a loader in `packs.py`.
3. Add a renderer in `prompt.py` that **omits the section when the field is empty**.
4. Demonstrate it in [`examples/acme`](examples/acme).
5. Guard both ways: present in the example, absent from the clean brain.
6. Add a loader test, and document the seam in the README and architecture doc.

## Submitting changes

1. Fork the repository and create a branch from `master`
   (e.g. `feat/your-change` or `fix/the-bug`).
2. Make your change, keeping the quality gate green.
3. Update the docs in the same change when behaviour changes —
   `README.md` and `docs/architecture.md` should never drift behind the code.
4. **Sign off your commits** with `git commit -s` (see Licensing below).
5. Open a pull request against `master` with a clear description: the context, why
   this approach, and anything a reviewer should focus on.

Small, focused pull requests are easier to review and merge than sprawling ones.

## Cutting a release

Maintainers only. Releases are tag-driven: bump with `scripts/cut-release.sh X.Y.Z`,
push the `vX.Y.Z` tag, and the **Release** workflow builds, tests, publishes to PyPI
(via Trusted Publishing — no token), and cuts a GitHub Release. Full guide,
including the one-time PyPI setup, in [`docs/releasing.md`](docs/releasing.md).

## Licensing & sign-off

This project is open source under [Apache-2.0](LICENSE), created and maintained
by Haim Elbaz. We keep contribution simple — **no CLA**. Instead, sign off each
commit to certify you wrote the change and may submit it under the project's
licence, per the [Developer Certificate of Origin](https://developercertificate.org/):

```bash
git commit -s -m "your message"      # appends a Signed-off-by line
```

By signing off and contributing, you agree your contribution is licensed under
Apache-2.0. You retain copyright on your own contribution; it joins the project
under the same terms, so the project — and its attribution to its author —
remains open and intact. Please don't add the project's reserved names or
branding to a fork you redistribute (see [TRADEMARK.md](TRADEMARK.md)).
