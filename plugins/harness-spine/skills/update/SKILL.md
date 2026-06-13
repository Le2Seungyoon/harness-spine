---
name: update
description: Reconcile a repo that already has the harness against this plugin's current skeleton — migrate a legacy `.claude/rules` harness to the cross-provider `.agents/` layout, add what is missing, propose section-level changes for files the project has since rewritten, and never overwrite project-authored rules. Use when the user asks to "update the harness", "sync the rules", "migrate to AGENTS.md", or after this plugin itself has changed.
---

# update — reconcile an existing harness against the current skeleton

Reads the target repo's harness **as it actually is**, compares it against
`${CLAUDE_PLUGIN_ROOT}/skeleton/`, and lands only what the project is missing — section by
section, with the human deciding each one.

There is no version stamp to trust and none is required: **the repo's current files are the
baseline.** A repo scaffolded before this skill existed, or hand-edited for months, reconciles
the same way as a fresh one.

## What this skill is not

- **Not `init`.** If the repo has no harness, stop and hand off — scaffolding is that skill's job.
- **Not an audit of the project's own rules.** Rules this project wrote are out of scope; the
  question here is only *"what does the skeleton now have that this repo doesn't."*

## Checklist (create a todo per step)

### 1. Pre-flight
- Identify the layout:
  - **Current** — `AGENTS.md` + `.agents/rules/` (+ `CLAUDE.md` importing it). Go to step 3.
  - **Legacy** — `CLAUDE.md` + `.claude/rules/`, hooks in `.claude/hooks/` / `.claude/scripts/`,
    Claude Code only. Step 2 first.
  - **Neither** → `init`, not this.
- Branch-First: this step writes files. `git branch --show-current` and offer a branch. A legacy
  migration is its own branch and its own PR — never mixed with section reconciles.
- Read the repo's rules table (AGENTS.md, or CLAUDE.md on the legacy layout) first — it names
  which rules files the project treats as live, which is not always what is on disk.

### 2. Migrate a legacy layout — propose it as one unit, then apply it
The target is `harness.md` → The invariant: one shared source under `.agents/`, per-harness
registration only. Use `git mv` so history follows each file. Propose the whole plan, get one
approval, then apply:

| From | To | Watch for |
|------|----|-----------|
| `CLAUDE.md` (content) | `AGENTS.md` | `CLAUDE.md` becomes exactly `@AGENTS.md`; `.claude/rules/` → `.agents/rules/` in the table text |
| `.claude/rules/*.md` | `.agents/rules/*.md` | **strip `paths:` frontmatter and move each glob into that file's AGENTS.md read trigger** — nothing auto-loads under `.agents/`, so a dropped glob is a rule that stops firing (`runtime.md` → Rule delivery) |
| `.claude/hooks/*`, `.claude/scripts/*` | `.agents/hooks/*` | the project's own hooks too; every registration path and in-script path (`project_root()` depth stays three `dirname`s) |
| inline-shell PR-gate / commit-attribution hooks in `settings.json` | `git_gates.py push` / `commit` registrations | carry over the project's default branch into `PROTECTED` / `BASES` |
| `.claude/skills/<name>/` the project wrote | `.agents/skills/<name>/` | then `build-agents.py` regenerates both copies; `name:` must equal the directory |
| — | `.codex/config.toml` | **every** hook the project registers in `settings.json`, mirrored; each project PreToolUse guard added to `REQUIRED` in `test_harness_parity.py` |
| `claude-md-management` in `enabledPlugins` | removed (ask) | superseded by `refactor-agent-rules` |

After applying: sweep for residual references **unfiltered** — `grep -rn -e '.claude/rules' -e
'.claude/hooks' -e '.claude/scripts' .` (not `--include`), excluding generated copies — and fix
each. `check_rule_links.py` finds the broken pointers in rules; it does not see code or docs.

### 3. Classify every skeleton file — before proposing anything

| Class | Test | Action |
|-------|------|--------|
| **Missing** | skeleton has it, repo doesn't | propose the whole file |
| **Pristine** | the repo's copy is still the shipped stub | whole-file replace is safe |
| **Diverged** | the project filled or rewrote it | **never replace** — section-level proposals only |
| **Project-only** | the repo has it, the skeleton doesn't | leave untouched; never delete |

Classify by **reading both files**, not by timestamps or hashes — a stub with one filled FILL slot
is already Diverged, and a reformatted-but-untouched file is still Pristine. Generated copies
(`.claude/skills/`, `.codex/skills/`, `.claude/agents/`, `.codex/agents/`) are never classified —
regenerate them with `build-agents.py` after their source changes.

### 4. Reconcile — by section, not by file
- For **Diverged** files, match on heading text and propose only the skeleton sections with no
  counterpart. Where both sides have the section and disagree, **report the conflict; do not
  resolve it silently** — the project's wording usually encodes a decision this skill can't see.
- Never re-insert a FILL marker into a slot the project already filled — in **either** form:
  `<!-- FILL -->` in instruction files, `# FILL` in hooks, scripts and TOML.
- `settings.json` and `config.toml` are not text-mergeable. Compare **key by key** — hook
  entries, `permissions`, `enabledPlugins`, `project_doc_max_bytes` — and name each key-level
  change on its own. **A hook added to one registration is added to the other in the same
  proposal**; the parity test fails otherwise.
- Hook and script files: if the repo's copy differs, show the diff and **ask which way it should
  go** — a project may have hardened its copy deliberately, or may simply have drifted. Never
  assume either. A deliberate divergence says so in a `DIVERGENCE (<date>): <why>` line in that
  file's docstring; read those first, and when one describes a fix the skeleton should have, say
  so in the report — that is an upstream candidate, not a local quirk.
- **Check every read trigger against where its rule is actually executed.** A rule routed by the
  directory its subject is *stored* in goes unread by the sessions that *run* it — one repo gated
  its warehouse rules to `dbt/**` while half that contract executed in a Python loader, so the
  loader's own rules never loaded. A heading diff cannot see this; read the trigger, not just the
  body.
- Ask per proposal: **apply / skip / defer**, and record the reason for every skip.

### 5. Budget check — the update itself can blow the budget
- After applying, `wc -l` every instruction file. The skeleton grows over time, and a project that
  already filled a stub can cross the ~150-line budget the moment new sections land on top of it.
- If one crosses: run `refactor-agent-rules` on it **in this pass**.

### 6. Verify
- Both registrations parse (`json` / `tomllib`), then the harness loop from AGENTS.md → Commands:
  every `.agents/hooks/test_*.py`, `build-agents.py --check` (`AGENTS_FRESH`),
  `test_harness_parity.py` (`PASS`), `check_rule_links.py` (`RULE_LINKS_CLEAN`). Relocating a
  section and migrating a layout are exactly what orphan a pointer.
- For any hook this update touched, re-run it against both a must-block and a must-pass sample.
  A check that only ever fires is a false-positive factory.
- `grep -rnE '\{\{[A-Z_]+\}\}' AGENTS.md .agents/rules/` — no raw `{{VAR}}` may ship (hook code
  and its tests carry `{{` legitimately).
- After a legacy migration, Codex hooks are untrusted until a person opens the `codex` CLI in the
  checkout once (`runtime.md` → Codex hook trust) — say so; the parity test only WARNs.

### 7. Report
- Table of **applied / skipped (+reason) / deferred**, plus every conflict left for the human.
- **"Nothing to apply" is not proof the harness is current.** Section matching fails by design on a
  file the project rewrote in its own words: the change can be real and simply unmatched. Say that
  in the report instead of issuing a clean bill of health.
- **Divergence is the defect, and only a check that sees both sides finds it.** List every file
  whose copy differs from the skeleton, even the ones left alone on purpose — an unlisted
  divergence is one nobody re-decides — and every upstream candidate found in a DIVERGENCE line.
- Any check this update introduced stays advisory until someone **measures its false-positive rate
  against this repo's existing tree**. Do not promote it to a deny on the same day.

## Notes
- The skeleton is a **shared home**, not this skill's property: `init` copies it, `update`
  reconciles against it, and neither keeps a second copy.
- Skeleton changes that only *add* (a new rules file, a new hook + its test) are the safe majority.
  The expensive ones are edits to files every project was expected to fill — treat those as
  proposals to a human, always.
