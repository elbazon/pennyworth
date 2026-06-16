---
name: testing
description: Use before writing or running tests in an unfamiliar repo — find the actual test runner, run the affected subset for a fast loop, match the repo's existing test patterns, and know what "tests pass" really proves. NOT for casual mentions of testing in unrelated chat.
---

# Testing — find the runner, run the right subset, prove the real path

## Find the runner from the repo, don't assume

Discover how this repo tests before running anything:

- **JS/TS** — `package.json` `scripts` (`test`, `test:unit`, `test:e2e`); the
  runner is usually Jest, Vitest, Mocha, or Playwright. Monorepos (NX, Turbo,
  Lerna) wrap these — prefer their affected-only target.
- **Python** — `pyproject.toml` / `tox.ini` / `pytest.ini`; usually pytest.
- **Go** — `go test ./...`. **Rust** — `cargo test`. **PHP** — `composer test`
  / PHPUnit. **Ruby** — `rspec` / `rake test`.
- Fall back to the **CI config** (`.github/workflows/*`, `.gitlab-ci.yml`, or
  your CI's build files) — it names the exact commands that gate merges.

Run tests the way the repo's tooling expects: the right working directory, the
right package manager, any required services up. If a `CLAUDE.md` / `README`
documents the command, trust it over a guess.

## Run the right subset

- During iteration, run the **affected / nearest** tests — the single file or
  the affected target — for a fast loop. Don't run a five-minute suite after
  every edit.
- Before you call a task done, run the **full relevant suite** (and lint) once,
  so you're not green only on a subset.

## Match the repo's patterns

Read a neighbouring test before writing one: mirror its file naming, its
arrange/act/assert shape, its mocking and fixture conventions, and how it sets
up and tears down. A test that doesn't look like the others is friction for the
next reader.

## Know what "pass" proves

- **Never claim tests pass unless you ran them and saw it.** Report failures
  with the actual output, not a paraphrase. If you skipped a step, say so.
- A **green run on a fully-mocked path is not proof the live path works.** Where
  a change crosses a real boundary — a database, the network, a queue, the
  filesystem — add or run an integration test that exercises it, or say plainly
  that you only verified the mocked path.
- Pick the **altitude**: unit tests for logic and edge cases; integration tests
  where components meet; end-to-end sparingly, for the flows that matter most.
