---
name: investigate
description: Use FIRST for any investigation — "why is X broken", a red build, prod triage, code archaeology, a bug chase — before reaching for tools, so a fan-out beats serial queries.
---

# Investigation Playbook

When the user asks "why is X broken / what's happening / who touched this / what
changed" — read this before reaching for tools. It tells you which sources to
query, in what order, and in parallel; it stops you running five serial queries
when one fan-out would answer.

Platform-specific sources (a particular event store, CI system, or service map)
come from the active pack's skills — engage those alongside this method.

## When to use

| Intent | Trigger phrases |
|--------|-----------------|
| **Incident triage** | "errors in prod", "X is broken", "why is Y failing", "5xx spike", "users can't…" |
| **Red build / CI failure** | "CI is red", "build failed", "fix the CI", "tests broke" |
| **Code archaeology** | "why does X exist", "who wrote this", "what calls Y", "where is Z used" |
| **Bug repro chase** | "reproduce this", "track down a bug", multi-step debugging |

If the request is a single-tool lookup ("read this file", "grep for X"), skip
this — it's overhead.

## The core rule: fan out, don't walk

The most common investigation failure is **serial queries**: read one source,
wait, read the next, wait. Each round-trip costs latency and budget; worse, by
the fifth you've forgotten the first.

**Rule:** for any symptom touching 2+ sources, fire all the source queries in a
**single tool-use block** (multiple tool calls in one response). Synthesise once,
all results in hand.

If results from query A would meaningfully change query B (you need a name from
the logs before you know which build to check), then serial is correct — but say
so in one sentence before doing it.

## Decision tree

### A. Incident triage
Fan out in parallel:
1. **Logs / events** — the most recent errors in the affected environment (your
   platform's event/log source; see the active pack).
2. **Recent deploys / changes** — the last deploy to that environment, or
   `git log --since="2 days ago" --oneline` in the suspect repo. A change in the
   last hour is the prime suspect.
3. **Service health** — `docker ps` / a health endpoint to rule out a local
   problem masquerading as a real one.

Synthesis: correlate error timestamps to deploy timestamps first. A spike that
begins minutes after a deploy is a regression until proven otherwise.

### B. Red CI build
Fan out: the failed build's problems + failed test names; the build-log tail
(the stack trace is usually there); `git log <last-green>..HEAD --stat` for what
changed. Only then, serially, try to reproduce the failing test locally.

Synthesis: failed test name → grep it in the diff → if it's in changed code,
that's your culprit; if not, look for environmental causes in the log.

### C. Code archaeology
Fan out: `Grep` the symbol for its **definition**; a second `Grep` for its
**callers/imports**; `git log --all --oneline -- <file>` plus
`git log -S "<symbol>"` for when it appeared; the issue key from the commit
message and the PR that introduced it (`gh pr list --search …`).

Synthesis: definition + callers gives scope; git history + the linked issue
gives intent. Lead with intent — the user usually cares *why* more than *where*.

### D. Bug repro chase
The one case where serial is unavoidable: each hypothesis depends on the last.
Keep the hypotheses register explicit (below), and still **fan out within each
hypothesis** wherever you can.

## Findings format (gated)

Render structured findings when the investigation touched **2+ sources**, took
**3+ evidence-gathering calls**, or the user asked for a write-up. Otherwise
answer in plain prose — don't force the template on a one-grep lookup.

```
## Findings: <one-line symptom>

**Symptom.** What was reported / observed (1-2 lines).

**Hypotheses considered.**
- ✗ <ruled-out> — evidence: <what disproved it>
- ✓ <surviving> — evidence: <what supports it>

**Conclusion.** Root cause in plain English (2-3 lines). Reference file:line.

**Open threads.** Anything unverified this session. Omit if none.
```

The ✗/✓ markers matter: what was ruled out is as informative as the conclusion,
and stops the next person re-walking the same dead ends.

## Anti-patterns

- **Don't ask a clarifying question that grep would answer.** "Which module
  handles X?" is a search, not a question.
- **Don't run independent queries serially.** One fan-out, not three round-trips.
- **Don't read huge logs into the main context** when a `tail` or a delegated
  sub-agent with a tight charter will do.
- **Don't conclude on a single source.** Cross-check at least one other before
  claiming root cause.
- **Don't skip the negative result.** "No matching errors in the last 6 hours"
  is a useful conclusion, not a failure to report.

## Delegation

For investigations that will clearly read a lot of raw output (long build logs,
large result sets, cross-repo callsite walks), delegate to a sub-agent if your
host agent supports it, and have it return a short synthesis. Charter it like a
colleague: state the symptom, list the sources, name the report shape you want,
give it a budget. Investigation only — don't ask it to fix anything.
