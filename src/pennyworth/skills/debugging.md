---
name: debugging
description: Use before systematic debugging — narrowing a failure to its root cause, working across a call stack, or diagnosing production issues from logs and traces. NOT for casual "why doesn't this work" questions answered from obvious code inspection.
---

# Debugging — systematic root-cause investigation

## The debugging loop

Effective debugging is hypothesis-driven, not thrash-and-pray:

1. **Reproduce** — nail down the exact inputs that trigger the failure. A bug you can't reproduce reliably you can't confidently fix.
2. **Observe** — read the actual error: stack trace, log line, wrong output. Don't skim; read it completely before forming a hypothesis.
3. **Hypothesize** — propose the simplest explanation consistent with all observations. One hypothesis at a time.
4. **Test** — design an experiment that would *disprove* the hypothesis (not just confirm it). Confirmation bias kills debugging sessions.
5. **Narrow** — binary-search the failure. Does the bug exist at the midpoint? That halves the search space every step.
6. **Fix and verify** — the fix should follow directly from the root cause. If you're not sure why the fix works, you haven't found the root cause.

## Reproduce before anything else

A non-reproducible bug is not debuggable. Before writing any code:
- Write a **failing test** (or a minimal script) that triggers the bug.
- Confirm the test *fails* on the current code and *passes* after the fix.
- A test doubles as proof the bug is real and the fix is verified.

Flaky failures (sometimes fails, sometimes not) indicate non-determinism: race conditions, time-dependent code, or external service instability. Reproduce the flakiness in isolation before debugging the logic.

## Read the error — completely

The full stack trace points to the actual failure site, not just where the exception was caught. Before reading any code:
- Read from the *bottom* of the stack trace (the origin) upward (toward the caller).
- Identify the first frame *in your own code* — that's usually where to look.
- Note the error type and message precisely — "null pointer" and "key not found" have different root causes even if they crash at the same line.

## Binary search the call stack

When the failure origin is unknown:
```
# Is the bug in subsystem A or B?
→ Add a checkpoint between A and B.
→ Is the state correct at the checkpoint?
  Yes → bug is in B (or later). No → bug is in A (or earlier).
→ Repeat, halving the search space each time.
```

`git bisect` does this for regressions across commit history:
```bash
git bisect start
git bisect bad HEAD       # current commit is broken
git bisect good v1.2.0    # this commit was fine
# git will check out midpoints — run your test and mark each:
git bisect good           # or: git bisect bad
git bisect reset          # done
```

## Isolate to a minimal reproduction

Strip away everything that isn't necessary to trigger the bug. The smaller the reproduction:
- The clearer the root cause (less noise).
- The easier to write a regression test.
- The faster others can help.

Work top-down: comment out large sections and check whether the bug persists. When it disappears, the root cause is in what you just commented out.

## Logging and instrumentation

Add logging *at the hypothesis*, not everywhere:
```python
# Wrong: scatter prints across the file hoping to spot something
# Right: log the specific value your hypothesis predicts is wrong
logger.debug("user_id=%s role=%s expected=admin", user.id, user.role)
```

Structured logging (key=value or JSON) is grep-able; unstructured print statements aren't.

When debugging in production: **read before you write**. Pull recent logs first (`tail -f`, CloudWatch Logs Insights, OpenSearch). A second look at existing telemetry often answers the question without a deploy.

## Production debugging principles

- **Read-only first.** Diagnose fully before changing anything. A poorly-targeted fix in production can make things worse.
- **One variable at a time.** Don't deploy a fix and a config change simultaneously — you won't know which one helped.
- **Blast radius awareness.** Know what a change affects before applying it. A config change that fixes one user might break another.
- **Reproduce in staging first** when the bug is reproducible there. Only debug in production when it isn't.
- **Preserve state.** Before fixing, capture the bad state (log snapshot, thread dump, heap dump) — it may be the only evidence.

## Common root causes by symptom

| Symptom | Likely cause |
|---|---|
| Works locally, fails in CI | Environment difference: env var, file path, timezone, locale, seed data |
| Works for one user, not another | Authorization, tenant isolation, per-user state, feature flag |
| Intermittent failure | Race condition, timeout, network flap, resource exhaustion |
| Regression (worked before) | `git bisect` to find the commit; check changelog of any upgraded dependency |
| Off-by-one | Loop bounds, index vs. length, inclusive vs. exclusive range |
| Silent failure | Exception swallowed somewhere (`catch (e) {}`); check error handlers |
| Memory leak | Objects accumulating in a cache, listener not removed, circular reference |
| Slow query | Missing index, N+1 query, unbounded result set — check the query plan |

## Tools by runtime

- **Python:** `pdb` / `breakpoint()` for interactive stepping; `logging` module; `py-spy` for profiling without restart; `tracemalloc` for memory leaks.
- **Node.js / TypeScript:** `node --inspect` + Chrome DevTools; `console.trace()`; `clinic.js` for performance.
- **Browser JS:** DevTools Sources tab for breakpoints; Network tab for request/response inspection; `performance.mark()` for custom timing.
- **Go:** `dlv` (Delve) debugger; `pprof` for profiling.
- **PHP:** `xdebug` for step-debugging; `var_dump()` + `error_log()` for quick inspection.
