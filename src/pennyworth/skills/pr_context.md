---
name: pr_context
description: Use before opening or updating a pull request — write a PR body that explains intent (five sections), not just the diff.
---

# PR Context — write the why, not just the diff

When a coding task is wrapping up, you are about to push, or the user asks to
create/update a pull request, write the PR with **context**, not just a diff
summary.

The PR description is what reviewers — human *and* any AI review tool running on
the PR — lean on to understand the change. A body that only restates the diff
gives them nothing to reason about. Write for intent: a consistent, context-rich
shape means the *why* is always there, and a reviewer can pick it up without
re-deriving context.

## When to engage

- Right before `gh pr create` / updating an existing PR.
- When the user says "open a PR", "push this", or finishes a chunk of work and
  the working tree has uncommitted (or unpushed) changes.

## The PR body — five sections, always

```md
Requested by <the human's name and email, from your user block>

## Context
What problem or product/technical context led to this change?

## Why this approach
Why was this solution chosen over simpler/alternative options?

## Assumptions / Tradeoffs
What assumptions were made? What tradeoffs were accepted intentionally?

## Reviewer focus
What should reviewers pay extra attention to?

## Edge cases / Risks
Which edge cases were considered? What could still be risky?
```

Keep each section concise — a few sentences or tight bullets. Empty scaffolding
helps no one; if a section genuinely doesn't apply, say so in one line rather
than padding it.

## Non-negotiables

- **Open as a draft** when your workflow runs CI on PRs — mark ready only after
  review, so you don't trigger premature builds.
- **Attribution.** Carry the `Co-Authored-By: 🎩 Pennyworth (Claude <your actual
  model>)` trailer on the PR body and every commit. Keep a `Requested by
  <human>` line at the top when commits are authored by a bot account, so the
  real requester stays visible.
- **Title:** short and human-readable; don't duplicate an issue key the branch
  already carries.
- **Docs travel with the code.** If the change makes a README, an architecture
  note, or a command/API doc inaccurate, fold the update into the *same* PR.
  Scope it to what changed — don't rewrite docs wholesale.

## Flow

1. Inspect the change (`git -C <path> status` / `diff`) so the body reflects what
   actually changed and why.
2. Draft the five sections from the session's intent — what the user asked for,
   the decisions made, what was deliberately left out.
3. Offer it to the user, then create the PR with the body and the co-author
   trailer. Report the PR URL.
