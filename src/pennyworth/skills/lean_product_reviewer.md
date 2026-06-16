---
name: lean_product_reviewer
description: Use before ADDING anything (a feature, flag, skill, abstraction, behaviour), or when asked "is this worth building" — a short lean review that shapes how minimal to build.
---

# Lean Product Review

Run this **before** building an addition — a new flag, skill, prompt section,
abstraction, behaviour, or piece of tooling. AI makes building cheap;
cheap-to-build is not the same as worth-building. This review is the discipline
that stops you bolting on features just because you can.

## When to run it

- Whenever the request *adds* something (feature, flag, skill, abstraction,
  behaviour).
- On demand — "lean-review this", "is this worth building", "challenge this".

**Skip it for pure bug-fixes.** Fixing broken behaviour is obviously valid;
wrapping it in ceremony would itself be the overbuild this skill prevents.

## The review (produce this before writing code)

- **Task** — one sentence.
- **Primary value** — pick one: User value · Operational value · Developer
  productivity · Reliability · Compliance/risk reduction · Unknown/speculative.
- **Risk classification** — pick one: Valid core work · Possible overbuild ·
  Premature scaling · Scope creep · Weak justification · Missing operational
  guardrail · Balanced tradeoff.
- **Strongest argument against** — why this may be unnecessary, premature, or
  distracting right now. Max 5 sentences.
- **Strongest argument for** — why it may still be worth doing. Favour
  operational leverage, debugging, traceability, future migration cost,
  sensitive domains, supportability. Max 5 sentences.
- **Recommendation** — pick one: Proceed · Proceed, but keep it minimal · Defer
  until stronger signal · Add only the operational hook · Add measurement first ·
  Split into phases · Revisit after adoption.
- **Minimal acceptable implementation** — the smallest useful version. No
  platforms, no configurable engines, no speculative extensibility.

**Scale the review to the change.** A substantial addition earns the full review
above. A trivial one earns a single line: *lean check: minimal version, proceed.*
Don't let the review become the ceremony it exists to prevent.

## Principles

- **Small hooks ≠ platforms.** A flag, a metadata field, a log line, an audit
  marker can be reasonable very early. A governance layer, reporting suite,
  configurable framework, or orchestration system needs much stronger
  justification.
- **Telemetry is not always enough.** An event/analytics stream is great for
  history and audit — but runtime operations sometimes need direct querying,
  stable metadata, or fast debugging a firehose doesn't give cheaply.
- **Prefer reversible.** Easy to remove, no lock-in, minimal migration cost.
- **Prefer narrow.** If the work is justified, ship the narrowest useful version
  first and let real usage pull the rest.
- **Sensitive domains earn their hooks early.** Finance, health, anything with
  audit/compliance weight — that is exactly where a cheap traceability hook is
  worth keeping before scale, because retrofitting it later is expensive.

## Reconciling with the user's direction

The review shapes **scope**; it does not veto the user's **decision**.

- When the user has chosen an approach, the default recommendation is **"Proceed,
  but keep it minimal"** — your job is to find the smallest version that delivers
  what they asked, not to relitigate whether they should have asked.
- Surface **"Defer"** or **"Add measurement first"** only when you see a genuine
  overbuild they cannot see — never as a reflex, never as a posture.
- For improvements **you** propose (self-directed), be stricter. That is where
  AI-cheap-to-build scope creep actually originates.

## Tone

Pragmatic, balanced, skeptical, senior, concise. Don't blindly reject; don't
rubber-stamp. The goal is high-signal execution with sustainable discipline — not
maximal minimalism for its own sake.
