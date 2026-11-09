# harness-spine

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A reusable, project-agnostic **Claude Code harness** — `CLAUDE.md` + `.claude/rules/*` +
enforcement hooks — distributed as a Claude Code plugin and scaffolded into any repo by one command.

## Features

- **Self-growing rules** — gotchas and conventions discovered mid-task get written into
  `.claude/rules/*` at the end of every task, instead of staying lost in chat.
- **Auto file-size enforcement** — a hook nudges the moment a rules file crosses ~150 lines,
  triggering a relocate / split / abstract / compress pass (in that priority order) before it
  turns into noise.
- **Self-correcting** — a rule that's gone stale or wrong gets fixed as part of the task that
  exposed it, not left to rot.
- **Active edits, not append-only** — updates land in the matching section of the existing file,
  pruning anything now-dead in the same pass.
- **Convention-following by default** — before writing new code, find the nearest existing analog
  and mirror it (naming, layout, imports, return shape) instead of inventing a new pattern.
- **…paired with a counting question** — "what does this resemble?" is always asked alongside "how
  many times has this been written by now?", because the first question alone manufactures copies.
  Structural repetition is treated as hardcoding, extraction is due on the **second** occurrence,
  and `architecture.md` names the shared home it gets promoted to.
- **Four enforcement layers, routed on purpose** — `enforcement.md` decides whether a rule becomes
  prose, a hook, a test invariant, or a `permissions.deny`, and carries the contracts every hook
  honors. Hooks only see the current session's edits; anything that must hold on every authoring
  path is routed to a test instead.

## Built on the Claude Code Ecosystem

`harness-spine` is a harness that orchestrates Claude Code plugins:

- **[superpowers](https://claude.com/plugins/superpowers)** — the scaffolded `workflow.md` calls
  its `brainstorming` / `test-driven-development` / `verification-before-completion` skills before
  any new feature or 3+ file change. Optional: `init` drops the section if superpowers isn't installed.
- **[claude-md-management](https://claude.com/plugins/claude-md-management)** — once a rules file
  crosses the ~150-line budget, cleanup is delegated to its `claude-md-improver` skill rather than
  hand-trimmed prose.

## Plugins in This Marketplace

| Name | Description | Contents |
|------|-------------|----------|
| [harness-spine](plugins/harness-spine/) | Scaffold a project-agnostic Claude Code harness into any repo, and keep it in sync as the spine evolves | **Skills:** `init` — detect/interview/copy/fill/verify · `update` — classify/reconcile/verify against the current skeleton<br>**Skeleton:** `CLAUDE.md`, `.claude/rules/*` (incl. `enforcement.md`), `.claude/settings.json`, `.claude/hooks/` (hook + its test), `.claude/scripts/` (scanner + its test) |

## What you get

Running `/harness-spine:init` in a project scaffolds:

- `CLAUDE.md` — router skeleton (optional Stack table / Commands / Configuration / Rules /
  Enforcement hooks summary / References).
- `.claude/rules/` — the meta-process spine (`workflow.md`, `git-workflow.md`, `enforcement.md`)
  plus stubbed tech-stack rules (`coding-patterns.md`, `architecture.md`, `testing.md`) to fill
  per project.
- `.claude/settings.json` — a **PR-gate** hook (blocks push/PR until the default branch is merged),
  a **commit-attribution** hook (denies `git commit` carrying AI-signature trailers), and a
  **file-size-budget** hook (nudges when an instruction file exceeds ~150 lines).
- `.claude/scripts/check_rule_links.py` — scans every rules pointer and fails on one that no
  longer resolves; the layer a hook cannot reach. Shipped with its own test.
- `.claude/hooks/check_rules_size.py` — the file-size nudge (project-agnostic), shipped with
  `test_check_rules_size.py` beside it: a hook is code, so it arrives with a test covering both the
  must-block and the must-pass half.

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

`update` reads the repo's harness as it actually is — no version stamp required — classifies every
skeleton file as *missing / pristine / diverged / project-only*, and proposes the gap **section by
section**. Files the project has since written in its own words are never overwritten.

## Layout

```
├── .claude-plugin/marketplace.json          # declares this repo's plugins
└── plugins/
    └── harness-spine/
        ├── .claude-plugin/plugin.json        # plugin manifest
        ├── README.md                         # plugin usage doc
        ├── skills/
        │   ├── init/SKILL.md                 # scaffold into a repo with no harness
        │   └── update/SKILL.md               # reconcile an existing harness against the skeleton
        └── skeleton/                         # shared home — both skills read it, neither owns it
            ├── CLAUDE.md                     # router skeleton (Stack/Commands/Configuration/Rules/Enforcement hooks/References)
            └── .claude/
                ├── settings.json             # PR-gate + commit-attribution + file-size-budget hooks
                ├── hooks/
                │   ├── check_rules_size.py   # the file-size nudge hook (contract template)
                │   └── test_check_rules_size.py  # its test — must-block and must-pass halves
                ├── scripts/
                │   ├── check_rule_links.py   # scanner: rules pointers must resolve (test layer)
                │   └── test_check_rule_links.py  # its test
                └── rules/
                    ├── workflow.md           # planning, bug fixing, capturing learnings, file-size budget
                    ├── git-workflow.md       # branch-first, protected commands, syncing main, PR conventions
                    ├── enforcement.md        # prose vs hook vs test vs deny; hook contracts; generated-artifact lifecycle
                    ├── self-review.md        # end-of-task checklist: gates to run + judgments no gate can make
                    ├── coding-patterns.md    # stub: conventions, when to extract, derive-don't-restate
                    ├── architecture.md       # stub: layers/boundaries + shared homes to fill per project
                    └── testing.md            # stub: test conventions, invariant + freshness tests
```
