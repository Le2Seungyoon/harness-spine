# {{PROJECT_NAME}}

{{PROJECT_ONE_LINER}}
<!-- FILL: 2-3 lines on what this project does and its domain. -->

## Stack

<!-- FILL (optional — delete this section if a version table doesn't earn its keep here):
runtime/framework + major versions the project pins to, one line each. Note any cross-repo
version sync this project must respect and the bar for adding a new dependency (e.g. "requires
PR justification"). -->

## Commands

```bash
{{SETUP_COMMAND}}          # reproduce env / install deps
{{TEST_COMMAND}}           # tests (must pass before declaring done)

# harness: hook/scanner tests, parity, generated copies, rule links (stdlib python3 >= 3.11, no venv)
for t in .agents/hooks/test_*.py; do python3 "$t" >/dev/null || echo "FAIL $t"; done
python3 .agents/hooks/build-agents.py --check
python3 .agents/hooks/check_rule_links.py
```
<!-- FILL: key build / run / deploy commands, copy-paste ready. -->

Gates before declaring done: `self-review.md` ①.

## Configuration

| What | Where |
|------|-------|
| Secrets ({{SECRETS_EXAMPLES}}) | `.env` (copy `.env.template`) |
| Tunable values ({{TUNABLES_EXAMPLES}}) | {{CONFIG_LOCATION}} |
| Dependencies | {{DEPS_FILES}} |
<!-- FILL: rows for this project's real config surfaces. -->

IMPORTANT: Don't hardcode tunable values; put them in config.
<!-- FILL: dependency-management rule (the one correct command) if the project has one. -->

## Docs convention

- **User-facing docs** — `docs/`, written in the team's language, filename `YYYY-MM-DD-<name>.md`
  (the date prefix keeps the project timeline scannable).
  <!-- FILL: set the language / location / naming for this team, or delete if N/A. -->
- **The date prefix encodes how the file is maintained.** Dated = a snapshot of one moment, never
  rewritten. **Undated = a living document, overwritten in place** — and inside one, the three
  parts age differently: current state is *overwritten*, traps and prerequisites *accumulate*, and
  decisions belong in whatever ledger records decisions, not here.
- **Agent-facing files** (this file, the one-line `CLAUDE.md` that imports it, `.agents/**/*.md`)
  — written in **English**. Domain string literals (menu labels, error constants, column names)
  stay in their original language — they are data, not prose.
- **Name the action, never the harness** — per-harness variants: `harness.md` → Where a thing lives.

## Rules

Read the relevant rule in `.agents/rules/` before writing code. **Nothing here is loaded for you**
— this table is the whole delivery mechanism, so a trigger you skim past is a rule that does not
exist for that turn. When one fires and you have not opened the file this session, open it first.

| File | When to read |
|------|--------------|
| `git-workflow.md` | before any task that changes files — branches, commits, pushing, PRs |
| `workflow.md` | when planning a feature or a patch touching 3+ files; when user corrections, recurring problems or stale instructions reveal a harness improvement — capture lessons, update and organize rules |
| `coding-patterns.md` | when touching source (`{{SOURCE_GLOB}}`) — the analog to copy, when to extract |
| `architecture.md` | when adding a module or a shared helper — layers, boundaries, shared homes |
| `testing.md` | when writing/editing tests (`{{TEST_GLOB}}`) — conventions, invariant and freshness tests |
| `self-review.md` | at the end of every task, before declaring done or pushing |
| `enforcement.md` | before adding a rule, a hook, or a deny — it decides which layer it goes in |
| `harness.md` | **before changing anything that configures an agent** — instructions, rules, skills, hooks, registrations |
| `runtime.md` | when launching or debugging a harness — loaded instructions, config reload, Codex hook trust, sandbox |
<!-- FILL: add rows for topic/tool rules files you create (e.g. a service integration). Mark any
generated file as `<name> (generated — regenerate with <cmd>)`; never hand-edit one. -->

**Write FILL entries as pointers, not inventories.** A hand-copied list ("the components are A, B,
C") is stale by the next commit — name the file or command that *is* the current answer instead.

**Evolve this harness continuously, as part of every task.** Actively learn from user corrections,
failures, repeated friction and stale instructions. Without waiting for a separate request, update,
extend and reorganize `.agents/rules/` so later tasks benefit (`workflow.md` → Capturing Learnings).
Before declaring done, capture reusable conventions, rationale, contracts and gotchas in their
owning rules, rather than leaving them in chat or memory. Prefer improving existing rules; use
`refactor-agent-rules` when they need restructuring, and prune obsolete or duplicated guidance.
Tell the user what changed and why. When a rule conflicts with a request or reality, surface the
conflict rather than silently working around it (`workflow.md` → Rule Conflicts).

## Enforcement hooks

Hooks and scanners live in `.agents/hooks/` — one copy, registered by each harness in its own file
(`.claude/settings.json`, `.codex/config.toml`). `git_gates.py` denies AI-attribution trailers, a
push to the protected branch, and a push missing a base branch; `check_rules_size.py` nudges on an
oversized instruction file; `build-agents.py` regenerates the per-harness skill copies.
Which gates exist, what each blocks and how it fails: `enforcement.md` → This project's gates.
Changing any of it — a script, a registration, a skill: `harness.md`.

**Hooks only see this session's edits** — code written in an IDE, by a teammate, or by another
agent passes none of them, and a silent hook is not proof a check ran. Rules that must hold on
every authoring path need a test instead; see `enforcement.md`.

## References

<!-- FILL: pointers to design docs / specs / dashboards, or delete this section. -->
