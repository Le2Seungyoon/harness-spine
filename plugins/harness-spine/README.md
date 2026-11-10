# harness-spine

Scaffold a project-agnostic, cross-provider agent harness — `AGENTS.md` + `.agents/` rules,
skills and enforcement hooks, registered for both Claude Code and Codex — into any repo, and
reconcile it later as this plugin's skeleton evolves.

## Usage

```
/harness-spine:init      # repo has no harness yet
/harness-spine:update    # repo has one (either layout); pull in what the skeleton has since gained
```

`init` detects what your repo already reveals (VCS host, package manager, test command, source
globs), interviews you for the rest, copies the skeleton in, generates the per-harness skill
copies, and reports the FILL markers left for you to complete.

`update` takes the repo's harness **as it is** — no version stamp needed. A legacy
`CLAUDE.md` + `.claude/rules/` harness is migrated to `.agents/` first, as one reviewed unit.
Then every skeleton file is classified as *missing / pristine / diverged / project-only*, and the
difference is proposed section by section. Rules you have since written are never overwritten;
conflicts are reported, not resolved.

## Contents

| Component | Description |
|-----------|--------------|
| `skills/init/SKILL.md` | Scaffold: detect → interview → copy → generate → fill → verify → report |
| `skills/update/SKILL.md` | Reconcile: (migrate legacy) → classify → section-level proposals → budget check → verify → report |
| `skeleton/AGENTS.md`, `skeleton/CLAUDE.md` | Router — the one source every harness reads; `CLAUDE.md` imports it |
| `skeleton/.agents/rules/workflow.md`, `git-workflow.md`, `self-review.md` | Meta-process rules, kept generic |
| `skeleton/.agents/rules/enforcement.md` | Routing (prose / hook / test / deny), hook contracts, what to measure before a deny |
| `skeleton/.agents/rules/harness.md`, `runtime.md` | The cross-provider invariant and where things live; what differs per harness at runtime |
| `skeleton/.agents/rules/coding-patterns.md`, `architecture.md`, `testing.md` | Tech-stack rules, shipped as stubs to fill per project |
| `skeleton/.agents/skills/refactor-agent-rules/` | The restructuring procedure the size nudge points to — generated into both harnesses |
| `skeleton/.agents/hooks/` | `git_gates.py`, `check_rules_size.py`, `check_rule_links.py`, `build-agents.py`, each with its test, plus `test_harness_parity.py` |
| `skeleton/.claude/settings.json`, `skeleton/.codex/config.toml` | Per-harness registrations of the same hooks |

`skeleton/` sits at the plugin root, not inside a skill: both skills read it and neither owns a
second copy. The generated `.claude/skills/` and `.codex/skills/` copies are not in the skeleton
— `init` builds them in the target repo.

## Which skill

`init` refuses to clobber an existing harness and hands off to `update`; `update` refuses a repo
with no harness and hands back to `init`. Neither is the built-in `/init`, which writes a
`CLAUDE.md` from a codebase scan and knows nothing about this skeleton.
