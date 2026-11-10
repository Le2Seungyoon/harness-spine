# Coding Patterns

## Before writing new code (the rule that generates the rest)

Two questions, and they are asked **together**:

1. **"What does this resemble?"** — find the nearest existing analog and copy its conventions:
   file naming, layout, import order, config loading, return shape.
2. **"How many times has this been written by now?"** — if the answer is *two*, you are not
   writing new code, you are producing a duplicate. Go to **When to extract**.

Question 1 on its own reliably manufactures copies. What you mirror from a sibling file is its
**conventions**, never its **implementation block**: copying the shape of a handler is following a
convention, copying the handler's body is hardcoding it a second time. When unsure, don't invent —
read a sibling file. Canonical analogs:

<!-- FILL: list 2-4 canonical files new code should mirror. For each, name the evidence that makes
it canonical and how to re-check it — an analog asserted without evidence is where duplication
starts, and the assertion outlives the fact. Shape:
- New <layer> module → `<path/to/module>` (`<fn>(...)`). Evidence: <N of M modules follow it, as of
  <date>> — re-verify with `<command>` before relying on this line.
- <External service> access code → `<path/to/client>`.
- Reading config → `<config loader call>`.
- Tests → `tests/<module>/test_*.py` (see `testing.md`).
-->

Prefer a proven library over a hand-rolled implementation. Don't borrow a library's metric/API name
for a different custom implementation.

**1:1 correspondence is the design default** — artifacts describing the same thing map 1:1 in name
and unit, so the counterpart's location is derivable without search (visibility + maintainability):
config entry — implementing module · pipeline node — component file · test dir — source package.
<!-- FILL: point at the file that *is* the current list of pairs; don't transcribe the list here. -->
Adding one side of a pair without the other is a smell — wire both in the same change, and add a
correspondence test when the mapping is enumerable.

## When to extract

- **The second occurrence is the obligation point**, not the third. The first copy is cheap and
  invisible; the second is where "fix it in N places" begins.
- **The obligation falls on the second arrival** — whoever writes the copy, not whoever wrote the
  original. They are the first person in a position to see both call sites.
- **Promotion path**: module-owned → shared home (`architecture.md` → Shared homes). **Read both
  call sites before designing the API.** An interface shaped around only one of them won't fit the
  other, and the second caller will fork it straight back into a copy.
- **"It was never shared to begin with" is not a licence.** A structure with no canonical home is
  precisely the case no canonical-diff gate can see — which makes placing it your job, not
  something the absence of a rule excuses.
- If extraction genuinely cannot happen in this change (scope, risk, a release in flight), **don't
  copy silently**: copy and say so in the PR — what was duplicated, why, and what would make
  extraction possible. A copy a reviewer can see is a decision; a silent one is a defect.
- **Shadowing is a separate defect from copying, and counting cannot find it.** Re-declaring a
  name a shared home already exports makes one name mean two things depending on which file you
  are in — and the more the bodies have drifted, the worse it is. It is caught on the *name*,
  not the body; both fixes are fine (import the canon, or rename the local one).

**Reading a repetition count.** A count of two says *promote this*. A high count usually says
something else: the thing repeating is a symptom, and what is missing is one level up — a shared
handler, not a shared string. Promoting the fragment there just freezes the wrong shape. And
keep the two layers apart: **no canonical home yet → an advisory ledger a human rules on; a
canon exists and was copied anyway → a hard failure**, because that one needs no judgment.

## Derive, don't restate

Hardcoding is not only about scalars.

- **Secrets** → environment variables (e.g. `.env` + `os.getenv()` or the language's equivalent).
  Never hardcode or commit secrets.
- **Tunable values** (thresholds · windows · hyperparameters · feature flags) → config, not code.
- **Structure counts as hardcoding too.** Repeating a block of markup / query / handler / config
  N times means fixing it in N places — which is the definition. The only difference from a magic
  number is that nothing is counting the repeats for you.
- Don't couple logic to specific value names/counts — behave off the config lists / thresholds.
- **Where a value genuinely cannot be derived, gate the drift instead of banning the copy.** Some
  boundaries have no import (a document export with no access to the stylesheet, a generated
  artifact, a wire format). Banning the literal there is the wrong target — the literal is
  unavoidable, the divergence is not. Have the constant **name its source**, and check it still
  equals it (`enforcement.md` → Four layers).
- Imports/ordering: stdlib → third-party → local, blank-line separated. Type hints on signatures.
  <!-- FILL: adjust to this project's language / style conventions. -->

## Gotchas (non-obvious — mirroring won't catch these)

<!-- FILL: record project footguns as they bite (capture the "why", not just the "what"). Shape:
- **<config auto-load behavior>** — <what surprises, why it's done this way>.
- **<dependency-management rule>** — <the one correct command; what breaks otherwise>.
- **<a subtle default that flips behavior>** — <the trap + the regression test that pins it>.
-->

> For tests, see `testing.md`; for how a rule here becomes a hook or a test, see `enforcement.md`.
> Add topic-scoped rules files (a service/tool rule) as the project grows; keep each file under the
> ~150-line budget (see `workflow.md` → File size budget).
