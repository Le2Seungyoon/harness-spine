# Running this repo — what differs per harness

Facts about launching and debugging an agent here. What to *do* is in the other rules; this is
only the part that changes with the harness.

**Every measurement below carries its date and the build it was taken against.** These describe
the harnesses themselves, not this repo — nothing you edit here will ever put you next to a line
that has gone stale, so the date is the only signal a reader gets. Measured upstream (the
harness-spine source repos) unless a line says otherwise. When one is re-measured here, move the
date; when a claim cannot be re-measured, say so rather than leaving an old one standing.

## Confirming your instructions loaded

**Claude Code —** `/context` lists the memory files that actually loaded. `CLAUDE.md` is one line
(an `@` import of AGENTS.md), so seeing it listed is not enough — confirm the imported content is
there.

**Codex —** `codex debug prompt-input "<prompt>"` renders the model-visible input as JSON, with no
model call and no cost. Prove a config layer loads with it **before** blaming anything downstream.
Other instruments: `--strict-config` (nonzero exit on an unknown field), `--ignore-user-config`,
`codex exec --json -o <file>`.

## Where configuration lives, and when it is read

**Claude Code —** *measured 2026-08-31, VS Code extension.* `.claude/settings.json`
**hot-reloads mid-session**; a changed hook does not need a new session. The boundary is the tool
call: the call that writes the file still runs its own PostToolUse under the old config, and the
next call's PreToolUse already has the new one. So a hook edit that half-lands is normal for one
call and is not evidence the edit failed; re-check on the call after.
`.claude/settings.local.json` holds personal permission allowances and is gitignored.

**Codex —** *measured 2026-08-28, codex-cli 0.150.0-alpha.8.* Hooks go in `.codex/config.toml`
under `[hooks]`; a `.codex/hooks.json` is accepted, well-formed, in a documented location, and
**never read**. Ordinary keys hot-reload per turn, but `[hooks]` is read when `app-server` starts
— and an editor "Reload Window" does not restart it. Kill the `codex … app-server` process, then
reopen the Codex panel.

## Codex hook trust — the failure with no symptom

**Codex only —** *measured 2026-08-28, 0.150.0-alpha.8.* Project hooks do not run until they are
trusted, and the approval UI exists **only in the CLI TUI**. An IDE-only session never sees the
prompt, so the hooks stay untrusted forever with no error, no log line, and a config file that
looks correct. Run the `codex` CLI once from the checkout, accept "Trust all and continue", then
`python3 .agents/hooks/test_harness_parity.py` — it prints a `WARN` (never a failure: trust is
machine state, and PR evidence must depend on the code only) while trust is missing.

**Trust is per checkout path.** Every worktree is a new `projects."<abs path>"` entry, so the
first Codex session in it opens `Hooks need review — N hooks are new or changed`. A dispatched
lane that lands on that prompt stalls before reading its task; a person answers it (hooks then run
outside the sandbox), then the lane is dispatched again. The same path does not ask again.

**What the check can and cannot tell you.** Hook entries with **no** trust record for the project
means it was never trusted — real and actionable. Beyond that, do not infer: *measured 2026-08-31,
0.151.0-alpha.7.2*, `trusted_hash` values did not move across a full rewrite of every hook command
and the hooks still fired. Unmoved hashes prove nothing about whether hooks run.

**Only firing proves firing.** Put an oversized file under `.agents/rules/`, edit through the
harness, and look for the nudge; delete it and confirm the nudge stops. Both directions, or
neither counts — and do it in each harness.

## Rule delivery

**Neither harness auto-loads the rules.** They live in `.agents/rules/` and are reached through
the table in `AGENTS.md`. Claude Code *can* auto-load path-scoped rules from `.claude/rules/`
(`paths:` frontmatter), but a rule delivered that way is silently absent under Codex, so this
layout gives it up: the trigger text in the AGENTS.md table carries the weight the `paths:` globs
would have.

## Sandbox and approval

**Claude Code —** gates on approval prompts; `permissions.deny` in `.claude/settings.json` is
evaluated regardless of what a hook returns. In auto mode a classifier also judges intent and may
refuse editing another harness's config to drop its sandbox, or launching an unsandboxed lane.

**Codex —** gates on the sandbox (`-s read-only|workspace-write|danger-full-access`) and an
approval policy (`-a untrusted|on-failure|on-request|never`); `codex exec` is non-interactive.
`permissions.deny` has no equivalent, so a deny in `.claude/settings.json` protects Claude sessions
only — anything that must hold under Codex needs a PreToolUse hook. Top-level keys in
`~/.codex/config.toml` go **above** the first `[table]`, or TOML files them under it and they are
ignored. Whether the sandbox can start is a property of the host (e.g. a kernel that blocks
unprivileged user namespaces stops bubblewrap); when it cannot, the repo's hooks are Codex's only
guard — trust them in every checkout.
<!-- FILL: this project's host facts (OS, sandbox status, which Codex binary to run) as measured. -->
