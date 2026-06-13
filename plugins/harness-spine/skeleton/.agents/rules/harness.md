# Changing the harness

Read this before touching anything that configures an agent: `AGENTS.md`, `CLAUDE.md`,
`.agents/` (rules, skills, agents, hooks, scripts), `.claude/settings.json`, `.codex/config.toml`.

**More than one agent harness works in this repo.** Claude Code and Codex read the same
instructions and run the same hooks. A change that works in the harness you happen to be running
is not finished — it is half done, and the half you did not check is where the failures hide.

## The invariant

**One copy of the content and the logic; per-harness registration only.**

| Shared — never fork it | Per-harness — necessarily different |
|---|---|
| `AGENTS.md`, `.agents/rules/`, `.agents/agents/` | `CLAUDE.md` (one line: an `@` import of AGENTS.md) |
| `.agents/skills/**` — the source | `.claude/skills/`, `.codex/skills/` — **generated** |
| `.agents/hooks/`, `.agents/scripts/` — executable code | `.claude/settings.json`, `.codex/config.toml` `[hooks]` — **hand-written** |

Generated copies come from `build-agents.py`; the two registrations cannot be generated (the
schemas are unrelated), so `test_harness_parity.py` holds them together instead.
<!-- FILL: add a row per further harness this project supports (e.g. GEMINI.md importing
AGENTS.md); each one is another registration the parity test must learn. -->

## Where a thing lives

**Everything shared lives under the one `.agents/` root, split by subdirectory into prose and
code** — `rules/` and `skills/` are read by agents, `agents/` defines dispatched lanes,
`hooks/` implements event checks, scanners and generators (each with `test_<name>.py` beside it),
and `scripts/` coordinates agent workflows. Ask of any script: *would it still exist without the
harness?* If yes it is operator tooling and belongs in the project's own `scripts/`; workflow
scripts reuse operator tools rather than copying them. Scanner scopes stay narrow on purpose:
size and link checks govern `.agents/rules` + `AGENTS.md` only, and `build-agents.py` reads
`.agents/agents` + `.agents/skills` only; each test asserts its scope.

**Per-harness directories hold registration only.** Name a rule file by its topic, never by a
harness, and write the variants as adjacent paragraphs:

```markdown
**Claude Code —** `/context` lists the memory files that actually loaded.
**Codex —** `codex debug prompt-input` renders the same thing, with no model call.
```

Inline emphasis, not headings: a heading level collides with the file's own structure. Both
harnesses read both labels, which buys the only thing that matters — **a rule and its variant
cannot be read apart.** A file that would be one harness's paragraphs belongs beside the neutral
rule it modifies, or in `runtime.md` (launching and debugging).

**Skills follow the same rule and add one trap.** `.agents/skills/<name>/SKILL.md` is the source
and `build-agents.py` copies it to both harnesses; never hand-edit a copy. **Claude Code keys a
skill on its DIRECTORY name and Codex on `name:` in the frontmatter**, and neither errors when they
disagree — an instruction that says "use the X skill" then works in one harness and silently does
nothing in the other. The build refuses a mismatch. Codex rejects unknown frontmatter keys, so the
source stays to `name` and `description`.

**Dispatched lanes** (`.agents/agents/<name>.md` → `.claude/agents/`, `.codex/agents/` + an
`[agents.*]` entry in `.codex/config.toml`) follow the same generation. Harness differences are
frontmatter keys (`model.claude`, `model.codex`, `nickname_candidates`), never sidecar files.

## Before you call a harness change done

When rule responsibilities change, review AGENTS.md descriptions/read triggers and affected
rule cross-references together (`refactor-agent-rules`). Link checks prove existence, not that
the entry point still sends a reader to the right content; report that semantic judgment.

1. **Both registrations updated?** Changing one and not the other leaves that harness silently
   unprotected.
2. **Does the shared logic still handle the other harness's input?** Payload shapes differ — a
   Codex file edit arrives as `apply_patch` with the whole patch in `tool_input.command` and no
   `file_path` at all. Adding a branch for one is fine; replacing the other's is not.
3. **Did you verify, or assume?** Registration syntax cannot be tested offline, and an unverified
   change is reported as unverified.

Run before committing (all stdlib, Python ≥ 3.11, no venv; the loop is in AGENTS.md → Commands):

```bash
python3 .agents/hooks/test_harness_parity.py     # registrations + skills symmetric (Codex trust = WARN only)
python3 .agents/hooks/build-agents.py --check    # AGENTS_FRESH — generated lanes and skills match
python3 .agents/hooks/check_rule_links.py        # every pointer resolves
```

## Harness work fails silently — so verify the effect, not the input

**A thing that is configured but does nothing looks exactly like a thing that works.** The
distinction is *accepted* versus *resolved*: a key the parser tolerates but never acts on, a hook
registered but untrusted. Never conclude a layer works because nothing complained — make it *do*
something and watch that happen.

**Prove the check can fail before trusting it to pass.** A probe that cannot discriminate is
worse than none, because it manufactures confidence. Run the negative case first — a hook test
takes an env var pointing it at another implementation (`GIT_GATES_HOOK`) for exactly this.

**Verify one step past where the change lives.** Extracting the right path is not the hook firing;
the hook firing is not the harness honouring its verdict.

**Test every dimension you did not choose** — the shell a hook is handed (`/bin/sh` may be dash),
the payload shape, the OS path separator, the harness itself. When you add a dimension to a test,
parameterise it; swapping the value looks like coverage and removes it.

**"Harness-specific" and "unportable" are claims.** Check before applying the label, and when a
claim survives, write down what would falsify it.

## An empty result is not proof

A checker that reports nothing has five ways to be lying: the count fell below its threshold when
all but one instance was fixed; a promotion masked an unrelated repetition sharing the same
signature; near-matches were never grouped at all; **a backticked path wrapped across a line
break is never scanned** (`check_rule_links.py` matches newline-free — watch the `N references`
figure move, not just the verdict); and the quietest, **the thing was never in scope** — a
directory outside both the canon and the scan accumulates copies while the check stays green.
**Judge completion by searching the source, not by the checker being quiet.** Green means "not in
scope", never "not there".
