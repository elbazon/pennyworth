---
name: worth_it
description: Use when asked whether a shipped or in-flight change earned its keep — "was it worth it?", "did X pay off?" — to weigh measured cost against observed value and return an advisory verdict.
---

# Was It Worth It? — retrospective ROI on a change

Engage when someone asks, of a shipped or in-flight change, whether it earned its
keep: "was it worth it?", "did X pay off?", "what did this cost vs deliver?". The
`lean_product_reviewer` skill asks this **before** building (*should we?*); this
one asks it **after or in-flight** (*did/does it pay off?*).

**The honest stance.** A verdict is only as credible as its inputs. You do not
hold the project's real dollar ROI, and you must not invent one. So: measure the
cost you *can* measure, reason about the value you *can* observe, label which is
which, and return an **advisory** verdict — never a fabricated number dressed as
fact.

## Gather the cost signals (the measurable side)

- **Change size** — `git -C <repo> diff --shortstat <base>...<head>` (or
  `gh pr view <n> --json additions,deletions,changedFiles`). Lines and files
  touched proxy build + review + future-maintenance cost.
- **Build cost** — if the change came from an assistant session, the session's
  token cost ($) is a real, known number. Quote it.
- **CI cost** — build minutes for the branch, if your CI exposes them; otherwise
  mark it unmeasured.
- **Maintenance surface** — new files, dependencies, config, or public API =
  ongoing cost; one-off scripts and deletions are nearly free. A net-negative
  diff (removing more than it adds) is a *saving*, not a cost.

State these as measured. Where a signal is missing, say "unmeasured" — don't
guess a figure.

## Weigh the contribution (the judgement side)

- **Who it helps, and how often** — everyone every day, or one team once a
  quarter? Frequency × population is the lever.
- **What kind of value** — user-facing capability · operational leverage / time
  saved · reliability / risk reduced · developer productivity · compliance. Name
  it; "Unknown/speculative" is a valid and important answer.
- **Reversibility & lock-in** — low-commitment work is cheap to have been wrong
  about; an architectural commitment is not.
- **Counterfactual** — did it replace a worse manual process, or gold-plate
  something already fine?

## The verdict

Return one of **Worth it · Marginal · Not worth it · Too early to tell**, then:

- the measured cost (size, $ tokens, CI) — with "unmeasured" where honest;
- the observed value and its type (or "speculative");
- a one-line *why*; and
- if Marginal / Not worth it: the smaller version that would have flipped it.

Keep it short and senior — an honest gut-check the user can act on, not a
spreadsheet, and never a precise-looking ROI you can't stand behind. When the
value is genuinely unknowable yet, say "too early — re-ask after real usage."

## Reconciling with the user's call

This **informs**, it does not overrule. If they shipped it, the verdict is
feedback for next time, not a demand to revert. Be the dry, candid second opinion
— "worth it, though half the diff was scaffolding you'll maintain forever" — not
a scold.
