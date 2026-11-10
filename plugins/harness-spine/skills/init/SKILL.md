---
name: init
description: Scaffold THIS plugin's cross-provider harness skeleton (AGENTS.md + .agents/ rules, skills and hooks, registered for both Claude Code and Codex) into a repo that has none. Use when the user asks to "init the harness", "set up agent rules", or "scaffold the harness" — not for writing a CLAUDE.md from scratch (that is the built-in /init), and not for a repo that already has a harness (that is the update skill).
---

# init — bootstrap the harness into a project

Scaffolds a project-agnostic, cross-provider agent harness into the current repository: one
shared source under `.agents/` + `AGENTS.md`, registered for each harness (`CLAUDE.md` →
`@AGENTS.md`, `.claude/settings.json`, `.codex/config.toml`). It fills what it can **detect**,
**interviews** for the rest, and **reports** the FILL markers left for the human.

The files to copy live in the plugin's shared skeleton home, `${CLAUDE_PLUGIN_ROOT}/skeleton/` —
shared with the `update` skill, so **neither skill keeps its own copy**. **Never invent harness
content — copy from `skeleton/` and substitute.**

## Checklist (create a todo per step)

### 1. Safety / pre-flight
- Confirm the CWD is the project root the user wants to scaffold.
- Check for existing harness files: `AGENTS.md`, `CLAUDE.md`, `.agents/`, `.claude/rules/`,
  `.claude/settings.json`, `.codex/config.toml`. **A harness of either layout → offer `update`
  instead** (it also migrates the legacy `.claude/rules` layout). A lone hand-written `CLAUDE.md`
  or `AGENTS.md` with no rules dir: **STOP and ask** merge / overwrite / skip — never clobber it.
- `git branch --show-current` and follow the Branch-First convention (offer a branch) — this step
  writes files.

### 2. Detect (fill what the repo already tells you — read, don't ask)
- **VCS host + default branch**: `git remote -v` (github.com / bitbucket.org / gitlab.com / other);
  default branch via `git symbolic-ref refs/remotes/origin/HEAD` (fallback `main`). Note whether
  `gh` is installed — it decides the PR route named in `git_gates.py`.
- **Package manager + commands**: `uv.lock`/`pyproject.toml` (uv), `package.json` + lockfile
  (npm/pnpm/yarn), `go.mod`, `Cargo.toml`, `poetry.lock`, `requirements.txt`, … → derive
  `{{SETUP_COMMAND}}` and `{{TEST_COMMAND}}`.
- **Source & test globs**: infer `{{SOURCE_GLOB}}` (`src/**`, `include/**`, `app/**`, …) and
  `{{TEST_GLOB}}` (`tests/**`, …) from the tree. They become read triggers in the AGENTS.md rules
  table — nothing auto-loads a rule (`runtime.md` → Rule delivery).
- **Python**: the hooks need `python3` on PATH, **≥ 3.11** (the parity test uses `tomllib`). If
  `python3` is missing or older, say so now — every hook would fail open on the first call.

### 3. Interview (ONE question at a time, ONLY for what you couldn't detect)
- `{{PROJECT_NAME}}` (default: repo dir name) and `{{PROJECT_ONE_LINER}}` (domain, 2-3 lines).
- `{{COMMIT_LANGUAGE}}` / commit style (default: English, single-line subject, no AI attribution).
- **Branch model**: is there a standing staging branch (e.g. `develop`)? It fills `BASES` in
  `git_gates.py` and the staging FILL in `git-workflow.md`.
- Configuration-table surfaces: `{{SECRETS_EXAMPLES}}`, `{{TUNABLES_EXAMPLES}}`,
  `{{CONFIG_LOCATION}}`, `{{DEPS_FILES}}`.
- Whether the **superpowers** plugin is used (keep or drop it from `enabledPlugins`; the
  `workflow.md` method section works without it).
- Confirm the detected package manager / test command.
- Whether `AGENTS.md` → Stack table is worth keeping — fill it or delete the section.
- **"What gets built N times in this project?"** — screens? endpoints? pipeline nodes? reports?
  Whatever they name is what will be copied instead of shared, and later defines the signature a
  counting check would have to match. Record the answer in `coding-patterns.md` → canonical analogs.
- **"Where does a shared one live?"** — for each kind they named, the directory/module it gets
  promoted to. Fills `architecture.md` → Shared homes. A kind with no home is the one that gets
  copied; if they don't have an answer yet, leave the row with an explicit "no home yet".

### 4. Copy + fill
- Copy everything under `skeleton/` into the project root, preserving paths: `AGENTS.md`,
  `CLAUDE.md` (exactly `@AGENTS.md`), `.agents/rules/*.md`, `.agents/skills/**`,
  `.agents/hooks/*` (every script **and its `test_*.py`**), `.claude/settings.json`,
  `.codex/config.toml`.
- **Generate the per-harness copies**: `python3 .agents/hooks/build-agents.py`. It writes
  `.claude/skills/refactor-agent-rules/` and `.codex/skills/refactor-agent-rules/`; commit them —
  both harnesses read the copies, never the source.
- Substitute all `{{VARS}}` with detected/interviewed values across the copied files.
- **`git_gates.py` FILL slots** (`# FILL`, Python): `PROTECTED` (the branch that changes only by
  PR — usually the default branch), `BASES` (every long-lived branch a push must contain), and
  `PR_ROUTE` (`gh pr create` when GitHub + `gh`, else "the host's web UI"). Keep
  `FETCH_TIMEOUT × len(BASES)` below the 30 s registration timeout.
- **`check_rule_links.py` → `SEARCH_DIRS`**: add the project's source roots when source is not at
  the repo root (rules name modules the way code imports them).
- **Permissions — leave `allow` empty by default.** The harnesses already allow the common
  read-only commands, so most hand-written entries are dead weight: in a measured audit, 104 of 144
  accumulated rules had never matched anything. Add an entry only for a command the user is
  actually being prompted for repeatedly.
- **`deny` is Claude Code only.** Codex has no equivalent, so a rule that must hold in both
  harnesses is a PreToolUse hook registered in both files. `Write(<path>)` denies are accepted but
  never match — write file denials as `Edit(<path>)`, and verify any deny by triggering it once.
- **enabledPlugins**: declare team-mandatory plugins ONLY from official/default-known marketplaces
  (teammates get an auto-install prompt on open). Never put personal-marketplace plugins —
  including this harness plugin itself — into project settings.

### 5. Verify
- `python3 -c "import json,tomllib; json.load(open('.claude/settings.json')); tomllib.load(open('.codex/config.toml','rb'))"`
  — both registrations parse.
- The harness loop from AGENTS.md → Commands: every `.agents/hooks/test_*.py` passes, then
  `build-agents.py --check` prints `AGENTS_FRESH`, `test_harness_parity.py` prints `PASS`, and
  `check_rule_links.py` prints `RULE_LINKS_CLEAN` on the **filled** tree (substitution can leave a
  pointer aimed at a file this project deleted). A Codex-trust `WARN` from the parity test is
  expected until step 6.
- **Prove a gate can fail**: pipe a `git commit -m "x\n\nCo-Authored-By: …"` payload through
  `git_gates.py commit` and confirm it denies, and a trailer-free one passes; pipe a push to the
  protected branch through `git_gates.py push` and confirm it denies.
- Wire the parity test, `build-agents.py --check` and `check_rule_links.py` into the project's own
  test suite or CI before finishing — as shipped scripts nothing calls, they are inert
  (`enforcement.md` → Four layers).
- `grep -rnE '\{\{[A-Z_]+\}\}' AGENTS.md .agents/rules/` — no raw `{{VAR}}` may ship (hook code
  and its tests carry `{{` legitimately, so they are out of this grep). Any value you couldn't fill → convert to a
  FILL marker instead of leaving a bare `{{VAR}}`.

### 6. Report
- List every remaining FILL marker (file + line) as a checklist for the human. **Grep both forms**
  — `grep -rn -e '<!-- FILL' -e '# FILL' AGENTS.md .agents/ .claude/ .codex/` — because markers in
  `.py`/`.toml` files carry the comment form.
- Especially: the stub rules (`coding-patterns.md`, `architecture.md`, `testing.md`) whose deep
  project rules only the human / a later session can write; `self-review.md` ① — an unfilled gates
  table leaves half that checklist inert; and `check_rule_links.py` → `SEARCH_DIRS`.
- **Codex hook trust is the human's step**: hooks in `.codex/config.toml` do not run until someone
  opens the `codex` CLI in this checkout once and accepts "Trust all and continue" — an IDE-only
  session never shows the prompt (`runtime.md` → Codex hook trust). Then re-run the parity test.
- Remind: add topic/tool rules files as the project grows, each with a row and a read trigger in
  the AGENTS.md table; keep each under the ~150-line budget (`check_rules_size.py` nudges, and
  `refactor-agent-rules` is the procedure).
- **State plainly what was not installed: there is no counting layer.** The harness ships the
  convention ("extract on the second occurrence") and the place to put it (Shared homes), but
  nothing that counts occurrences — that detector has to be defined against this project's own
  material and cannot be inherited.
- **Warn before anyone builds one**: measure its false-positive rate over the existing tree first,
  and gate one occurrence later than the convention asks. A candidate signature measured elsewhere
  ran at 12.5% / 25% / 75% false positives depending on the shape chosen — promoting such a check
  straight to a deny is how a hook gets switched off for good (`enforcement.md` → Before promoting
  a check to deny).

## Notes
- The harness is intentionally minimal — the meta-process spine kept, tech-stack rules stubbed,
  tool-specific rules dropped. Grow it per-project via Capturing Learnings, not by bloating the
  template.
- **One source, per-harness registration** (`harness.md` → The invariant). Supporting a further
  harness later means another registration file and teaching the parity test about it — never a
  second copy of the rules.
- **`init` is for a repo with no harness.** Reconciling an existing one against a newer skeleton —
  including migrating a `.claude/rules` harness to `.agents/` — is the `update` skill's job.
