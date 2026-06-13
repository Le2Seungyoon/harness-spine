# Enforcement

Where a rule lives is a design decision, not a formatting one. This file is the routing
function — prose vs hook vs test vs `permissions.deny` — plus the contracts every hook in
this project honors. Route a rule **before** writing it: a rule in the wrong layer is not a
weaker rule, it is a rule that never runs.

## Four layers

| Layer | Use when | How it fails |
|-------|----------|--------------|
| **Prose** (`.agents/rules/*.md`) | context-dependent advice; the *why* behind a ban | quietly ignored under deadline |
| **Hook** (`.agents/hooks/*.py`) | deterministic check, fast feedback, this session's edits | one false positive and it gets switched off |
| **Test / CI invariant** | must hold no matter who authored the code | slow feedback; needs a real assertion |
| **`permissions.deny`** | absolute in every context (person · solo/team · time) | blocks legitimate work with no escape — and **Claude Code only**: Codex has no equivalent, so a rule that must hold there too is a hook (`runtime.md` → Sandbox and approval) |

## Hooks only see this session's edits

A hook fires on this session's tool calls. Code authored in an IDE, by another agent, or by a
teammate bypasses every hook here. **A rule that must hold on every authoring path needs a test
layer** — the hook is fast feedback, the test is the guarantee.

A hook can widen its own reach: **scan the governed set instead of reading the payload's file
path.** Keying on the path means edits made through the shell (`sed`, a heredoc, a one-liner)
are invisible, and no matcher list fixes that. Scanning closes the shell hole and costs nothing
on a small set — but it still does not see the IDE, so it does not replace the test layer.

## Hook contracts

Breaking one of these is how a hook stops being trusted, and an untrusted hook gets removed.

- **One script, both harnesses.** Logic lives in `.agents/hooks/`; each harness only registers it
  (`harness.md` → The invariant). The script self-filters — Codex registrations have no prefix
  filter — and handles both payload shapes (Codex edits arrive as `apply_patch` in `command`).
- **PreToolUse may deny; PostToolUse never does.** One script may serve both events (branch on
  `hook_event_name`), but the PostToolUse path only advises.
- **Declare failure policy.** Advisory failures report and exit 0. A required guard missing at
  the registration boundary refuses the call. An executed check lacking external context (no
  remote, a timed-out fetch) states what was not checked; its own contract decides whether that
  condition blocks. A hook must never block an edit for a reason unrelated to what it checks.
- **Silence means exactly one thing: "checked, and it passes."** If the check could not run,
  emit one line saying so. Otherwise "all clear" and "never looked" are indistinguishable.
- **Timeouts nest**: any subprocess timeout stays below the hook's own registered `timeout`, so
  the hook controls its own outcome instead of being killed mid-write.
- **A hook is code — it ships with `test_<name>.py` beside it.** Cover the must-block and the
  must-pass halves; the must-pass half is what keeps false positives from creeping in.
- **Judge where the command acts, not where the session sits.** `cd <dir> &&` and `git -C <dir>`
  retarget a call; a prefix filter or a `git push` grep misses both. Parse it.
- **A deny message says what to do instead**: why it fired, the canonical alternative, the
  escape hatch, and the rule file it enforces.
- **Account for every item in scope.** Compare it, or list it as unresolved with a stated
  reason. An item that is neither fails. Silently skipping what it cannot parse is how a
  checker ships inert while reading as protection.
- **An empty target set is a failure, not a pass.** A glob that stops matching — a moved
  directory, a pinned path depth — takes a check from N files to zero with no error and no
  output. Assert the set is non-empty, and say how many things were examined.

**The `deny` boundary cuts both ways.** A rule someone could *legitimately* override — a solo
admin authorizing direct git on their own machine — is a convention and stays prose; denying it
trains everyone to route around denies. An invariant left as prose is the reverse error: a gate
you did not build. Both cases are worked through in `git-workflow.md`.

## Before promoting a check to deny

- **Measure the false-positive rate first.** Run the candidate rule over the existing tree and
  classify every hit. A rule that blocks legitimate work trains everyone to route around it.
- **Set the gate one occurrence later than the rule asks for.** If the convention says "extract
  on the second copy", gate the third. The gap is deliberate: it is where judgment lives.
- **Checks with legitimate exceptions need an explicit reason** (`<gate-name>-exempt: <reason>`);
  an empty or near-empty reason must not pass. Absolute invariants have no bypass. The goal is
  not prohibition, it is surfacing: turn a silent copy into an explicit decision a reviewer sees.
- **When a hook takes over a rule, delete the prose it replaced.** Keep only what the hook
  cannot check — it blocks the import, but it cannot say why the ban exists.

## Answers, not lookup procedures

A rule that says *"check X first"* makes the reader perform a lookup, and every point where
that lookup fails is an incident. Where the answer is derivable from the tree, **generate it**:

- The generated file carries a `do not edit by hand — regenerate with <cmd>` header and is
  committed, so it is readable without running anything.
- An index of **what exists yet** reads the **default branch** (a long-lived branch otherwise
  reports "this does not exist yet" about something shared while it was away); a same-branch
  scan + freshness test reads the working tree.
- A **freshness test** fails when the committed artifact is stale. Hooks cannot cover this:
  the artifact goes stale through edits they never see.
- A hand-maintained list of the same information rots. Do not keep one beside the generated one.
- **Its headings are an interface, not prose.** The generator re-parses its own output, and gates
  key on section titles. Rename one and the reader silently finds zero entries — move the anchor
  in the same change.

## Keeping a generated artifact alive

Generating the answer moves the problem, it does not end it: **triggering the regeneration is
still a procedure someone has to remember** — the same defect one level up.

- **A freshness test is the only lever that covers every authoring path.** A PostToolUse
  staleness warning is a complement, never a substitute (it sees this session's edits only);
  re-checking where a merge hook already fires is nearly free.
- **Never regenerate as a side effect of an unrelated edit.** Cost is not the objection; a tracked
  file modified by a write that had nothing to do with it leaves a diff nobody can trace.
- **Regenerate in the same change that invalidates it.** Otherwise the default branch goes stale
  the moment the PR merges, with the PR that caused it already closed.
- **A gate whose input is a generated file must distinguish three states**: nothing registered
  yet · stale · unreadable. Failing open on all three is right for *blocking* and wrong for
  *reporting* — "no violations" and "never looked" collapse into one silence, and the defect
  stays dormant until the first real entry arrives.
- **Prove staleness is caught by causing it**: delete an entry, delete a section, add a real
  occurrence without regenerating. Then name the authoring paths that still bypass the check.

Where harness code lives, and why an empty result is not proof: `harness.md`.

## This project's gates

| Gate | Layer | What it checks | Escape hatch |
|------|-------|----------------|--------------|
| PR gate | PreToolUse hook (`git_gates.py push`) | a push whose destination is `PROTECTED`; else a HEAD lacking an existing `origin/<base>` for each of `BASES` (no `origin` → passes, says `NOT checked`) | protected branch: none — a PR; base: merge it (`git-workflow.md` → Before you push) |
| Commit attribution | PreToolUse hook (`git_gates.py commit`) | a `git commit` message with a `Co-Authored-By` / `Generated with` trailer | none — invariant (`git-workflow.md` → Commits) |
| Rules size | PostToolUse hook (`check_rules_size.py`) | `.agents/rules/*.md`, `AGENTS.md` within **150 lines / 10,240 bytes**; AGENTS.md below Codex's `project_doc_max_bytes` | advisory, never denies (`workflow.md` → File size budget) |
| Generated copies | PostToolUse hook + `build-agents.py --check` | harness skill/lane copies equal their `.agents/` source | none — edit the source |
| Registration parity | test (`test_harness_parity.py`) | both harnesses register the same hooks, every required gate, every skill | none — register on both |
| Rule links | scanner (`check_rule_links.py`) | every harness-internal file path a rules file points at exists | narrow by construction — globs/placeholders out of scope |
<!-- FILL: one row per gate as it is added — gate | layer | what it checks | escape hatch. Wire
the scanners and the parity test into this project's own test suite / CI, or they run only when
someone remembers to. -->

Hook/scanner tests are stdlib-only and run directly (AGENTS.md → Commands); no test runner
collects them.
