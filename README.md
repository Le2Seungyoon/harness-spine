# harness-spine

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A reusable, project-agnostic **agent harness** — `AGENTS.md` + `.agents/` rules, skills and
enforcement hooks — that serves **Claude Code and Codex from one source**. Distributed as a Claude
Code plugin and scaffolded into any repo by one command.

## Features

- **One source, every harness** — `AGENTS.md` and `.agents/` are the single source of truth.
  `CLAUDE.md` is one line that imports `AGENTS.md`; skills are generated into `.claude/skills/`
  and `.codex/skills/` by `build-agents.py`; each harness only *registers* the shared hooks
  (`.claude/settings.json`, `.codex/config.toml`), and a parity test fails when the two
  registrations drift apart.
- **Self-evolving rules** — gotchas and conventions discovered mid-task get written into
  `.agents/rules/*` at the end of every task, instead of staying lost in chat. A rule that's gone
  stale or wrong gets fixed as part of the task that exposed it.
- **…kept compact by a loop, not by discipline** — a hook nudges the moment a rules file crosses
  150 lines / 10 KB, and the bundled `refactor-agent-rules` skill answers it: relocate / split /
  abstract / compress, in that order, then reconciles the `AGENTS.md` routing with what moved. It
  reports before changing anything.
- **Rules are routed, not auto-loaded** — the `AGENTS.md` table is the delivery mechanism, with a
  read trigger per rule, so a rule that fires under one harness can't be silently absent under the
  other. A scanner fails when a pointer in that routing stops resolving.
- **Convention-following by default, paired with a counting question** — "what does this
  resemble?" is always asked alongside "how many times has this been written by now?"; extraction
  is due on the **second** occurrence, and `architecture.md` names the shared home.
- **Four enforcement layers, routed on purpose** — `enforcement.md` decides whether a rule becomes
  prose, a hook, a test invariant, or a `permissions.deny` (Claude Code only — Codex has no
  equivalent), and carries the contracts every hook honors. When a rule is promoted to
  enforcement, the prose it replaced is deleted.

## How the harness evolves

```
task ──► Capturing Learnings ──► .agents/rules/*.md grows
                                        │
            check_rules_size.py ◄───────┘   (PostToolUse, scans every rules file)
                    │ over budget
                    ▼
          refactor-agent-rules ──► relocate / split / abstract / compress
                    │                + reconcile AGENTS.md triggers
                    ▼
     check_rule_links.py · build-agents.py --check · test_harness_parity.py
```

Lessons that become deterministic leave prose entirely: they are promoted to a hook or a test,
and the prose they replaced is pruned (`enforcement.md` → Before promoting a check to deny).

## Plugins in This Marketplace

| Name | Description | Contents |
|------|-------------|----------|
| [harness-spine](plugins/harness-spine/) | Scaffold a cross-provider agent harness into any repo, and keep it in sync as the spine evolves | **Skills:** `init` — detect/interview/copy/generate/verify · `update` — migrate legacy layout, classify/reconcile/verify<br>**Skeleton:** `AGENTS.md`, `CLAUDE.md`, `.agents/{rules,skills,hooks}`, `.claude/settings.json`, `.codex/config.toml` |

## What you get

Running `/harness-spine:init` in a project scaffolds:

- `AGENTS.md` — router (Stack / Commands / Configuration / Rules table with read triggers /
  Enforcement hooks / References); `CLAUDE.md` = `@AGENTS.md`.
- `.agents/rules/` — the meta-process spine (`workflow.md`, `git-workflow.md`, `enforcement.md`,
  `self-review.md`, `harness.md`, `runtime.md`) plus stubbed tech-stack rules
  (`coding-patterns.md`, `architecture.md`, `testing.md`) to fill per project.
- `.agents/skills/refactor-agent-rules/` — the restructuring procedure, generated into both
  harnesses.
- `.agents/hooks/` — every hook and scanner ships with its `test_*.py` (stdlib, Python ≥ 3.11):
  - `git_gates.py` — denies a push to the protected branch, a push missing a base branch, and a
    commit carrying AI-attribution trailers. It parses the command, so `cd <dir> &&` and
    `git -C <dir>` are judged against the tree they name.
  - `check_rules_size.py` — the size nudge, plus a warning before `AGENTS.md` reaches Codex's
    silent truncation limit.
  - `build-agents.py` — generates per-harness skill and lane copies; `--check` is their freshness test.
  - `check_rule_links.py` — every file a rule points at must exist.
  - `test_harness_parity.py` — both harnesses register the same hooks and skills.
- `.claude/settings.json`, `.codex/config.toml` — registrations of those hooks, one per harness.

## Install

```
/plugin marketplace add Le2Seungyoon/harness-spine
/plugin install harness-spine@harness-spine
```

## Use

In a project with no harness yet:

```
/harness-spine:init
```

In a project that already has one, once this plugin has moved on:

```
/harness-spine:update
```

`update` reads the repo's harness as it actually is — no version stamp required. A harness on the
legacy `CLAUDE.md` + `.claude/rules/` layout (harness-spine ≤ 0.2) is first migrated to `.agents/`
as one reviewed unit; then every skeleton file is classified as *missing / pristine / diverged /
project-only* and the gap is proposed **section by section**. Files the project has since written
in its own words are never overwritten.

After either, open the `codex` CLI once in the checkout and accept the hook-trust prompt — Codex
does not run project hooks until a person trusts them, and an IDE-only session never shows the
prompt.

## Optional companion

- **[superpowers](https://claude.com/plugins/superpowers)** — `workflow.md` suggests its
  `brainstorming` / `test-driven-development` / `verification-before-completion` skills for new
  features and 3+ file changes, but never requires them.

## Layout

```
├── .claude-plugin/marketplace.json          # declares this repo's plugins
└── plugins/
    └── harness-spine/
        ├── .claude-plugin/plugin.json        # plugin manifest
        ├── README.md                         # plugin usage doc
        ├── skills/
        │   ├── init/SKILL.md                 # scaffold into a repo with no harness
        │   └── update/SKILL.md               # migrate + reconcile an existing harness
        └── skeleton/                         # shared home — both skills read it, neither owns it
            ├── AGENTS.md                     # router: the single source every harness reads
            ├── CLAUDE.md                     # `@AGENTS.md`
            ├── .claude/settings.json         # Claude Code registration
            ├── .codex/config.toml            # Codex registration
            └── .agents/
                ├── rules/                    # workflow, git-workflow, enforcement, self-review,
                │                             # harness, runtime + stubs: coding-patterns,
                │                             # architecture, testing
                ├── skills/refactor-agent-rules/SKILL.md
                └── hooks/                    # git_gates, check_rules_size, check_rule_links,
                                              # build-agents — each with test_*.py — and
                                              # test_harness_parity.py
```
