# Workflow

## Planning

- Plan first for work that changes module/layer boundaries or affects 3+ files.
  <!-- FILL: where in-flight plans live (e.g. `docs/plans/`), if this project keeps them. -->
- If you hit an unexpected blocker mid-implementation, stop and redesign — don't force it through.
- Before a non-trivial change, ask once "is there a more elegant way?". If it's hacky, do it properly.
- In pre-finalized stages (config values still undecided), only make values easy to change via
  config — don't hard-couple logic to a specific value.

## High-impact tasks — choose a proportionate method

For a **new feature** or a **3+ file patch**, consider clarifying intent/design first, test-first
development, and gathering evidence before declaring done. Use available skills when useful (e.g.
superpowers' `brainstorming` / `test-driven-development` / `verification-before-completion`), or
apply the method directly; this guidance never requires installing a plugin. Follow decisions
already made in the session. Skip extra process for trivial edits and doc-only changes.

## Bug Fixing

- Investigate → fix → verify. Reproduce first; point at logs/errors directly rather than
  guessing from symptoms.
- If a fix feels hacky, implement the proper solution instead. Skip for obvious one-liners.

## Task Completion

- Don't mark done without proving behavior. Bugs: reproduce → fix → confirm it's gone.
- After a structural change, compare behavior against the previous state (tests + a real run).
- Test suites verify code correctness, not feature correctness. When the change has a runtime
  surface (a UI, a CLI, an endpoint, a running service), exercise it directly — start it and drive
  the actual path — before declaring done, not just its automated tests.
- **A quiet checker is not evidence.** A hook or linter can be silent because it passed, because
  it never ran, or because its target set went empty (`harness.md` → An empty result is not proof).
- When sweeping for residual references (a renamed/removed file, setting, path), don't filter
  `grep` by extension — `--include=*.py,*.md` skips `Dockerfile`, shell scripts and dotfiles.

## Self-review

At the end of every task, before declaring done: work `self-review.md` — ① this project's
gates, and ② the judgments no gate can make (escape hatches, allowlist lines, re-invented
equivalents, both halves of a mirror). Write the answers where the task is reported.

## Writing a file through the shell erases the read-first guard

`cat > path <<EOF`, `> path`, `tee path` and a Python `write_text` replace a file whole and say
nothing about what was there. The editing tools refuse to overwrite a file this session has not
read; a shell redirect has no such gate, so **the safety is in the tool, not in you**. Measured
(2026-09-07): a "new" test file written with `cat >` silently deleted an existing one, and the
suite stayed green — the deleted test is not there to fail. Before a shell write to a path you
have not read, look first (`test -e`); prefer the editing tools.

## Capturing Learnings

At the end of every task, before declaring done: **did anything reusable/recurring emerge this
session?** If so, don't leave it in chat — capture it.

Route first — the layer decides whether the rule ever runs (`enforcement.md` → Four layers):
- Anyone touching this repo (convention · contract · gotcha) → a committed `.agents/rules/` file.
- This machine/session only (local path, personal taste, one-off setup) → the agent's local memory.
- Deterministic, and checkable on this session's edits → a **hook** (+ its test).
- Must hold on every authoring path (IDE · teammate · another agent) → a **test/CI invariant**;
  absolute in every context → `permissions.deny` (Claude Code only). Contracts: `enforcement.md`.

Qualifies for a rules file: a convention decided this time · non-obvious design rationale · a
contract (an interface other modules depend on) or a change to one · a gotcha that will bite
again · a missing step in a "how to add …" checklist. **Not** one-off facts already in
code/tests/commit, or anything code/git already makes self-evident.

Format:
- Instruction files (`AGENTS.md`, `.agents/**/*.md`) are **English** — clarity + tokens. Domain
  literals stay as written.
- Pick the file by topic; **read the target file first** and update the relevant section — don't
  append a duplicate. Terse and actionable. Stage it with the code change.
- **Prune as you add**: when adding a rule, check whether an existing item is now dead —
  absorbed into a default, or promoted to enforcement — and delete it in the same change.
- **A new rules file is a new route.** Add its row to the AGENTS.md rules table with a read
  trigger, or nothing delivers it (`runtime.md` → Rule delivery).

## File size budget (keep each instruction file dense)

Gotchas accumulate; a bloated rules file dilutes signal. Soft budget: **150 lines and 10,240
bytes per file** (`AGENTS.md` and each `.agents/rules/*.md`). A PostToolUse hook
(`.agents/hooks/check_rules_size.py`) nudges when either is crossed, and also warns before
AGENTS.md reaches Codex's `project_doc_max_bytes`, where Codex truncates silently. The response is
a **four-option judgment, in priority order** — review the whole file, never just shave the line
you added; the hook restates all four, so what this keeps is why each ranks where:

- **① Relocate** — content ownership beats file convenience; `check_rule_links.py` keeps the
  pointer you leave behind honest.
  <!-- FILL: record precedents as they happen ("<section> moved <fileA> → <fileB>"). -->
- **② Split** — only for a sub-topic with its own trigger in the AGENTS.md table; splitting to hit
  the number just moves the bloat.
- **③ Abstract** — highest leverage: a stated principle regenerates the examples it replaces.
- **④ Compress** — wording only; buys the least.

**The procedure is the `refactor-agent-rules` skill** — one source in `.agents/skills/`, copied to
both harnesses by `build-agents.py`. It reports before it changes anything, and reconciles the
AGENTS.md routing with the moved content. **A generated file takes none of the four**; the only
lever is its generator (`enforcement.md` → Keeping a generated artifact alive). A tight
single-topic file slightly over budget is fine.

## Rule Conflicts & Harness Improvement

The harness (`AGENTS.md` · `.agents/` · registrations) is not a static document — it keeps
growing and getting corrected. **Never resolve a mismatch silently:**

- **Rule ↔ request conflict**: name the item and file, say what the rule protects, and confirm
  which wins. User instructions override rules, but present the rationale so it isn't lost.
- **Rule wrong or stale**: fixing it is part of this task; apply it and tell the user.
- **Screen every revision**: *was the rule wrong, or did this change just make it inconvenient?*
  Only the first justifies rewriting it; editing on the second is how a harness argues itself out
  of its own constraints.
- **An unsupported claim is an assumption.** A statement with no test, generated artifact or
  re-check command is marked as an assumption or deleted — a self-growing harness accumulates its
  own folklore otherwise.
- **Harness defect** (missing trigger, dead rule, bloated file): fix it alongside Capturing
  Learnings, following `harness.md`.

## Verification Commands

```bash
{{TEST_COMMAND}}      # must pass before declaring done
```
<!-- FILL: project verification commands (test / build / e2e / lint). -->
