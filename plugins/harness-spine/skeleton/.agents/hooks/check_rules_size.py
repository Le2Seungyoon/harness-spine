#!/usr/bin/env python3
"""PostToolUse nudge: warn when a governed instruction file exceeds its size budget.

Contract — this hook is the template every other hook in this project follows.
See `.agents/rules/enforcement.md` -> Hook contracts.

  Event     PostToolUse only. It ADVISES and never denies; denial belongs to PreToolUse.
  Governed  `.agents/rules/*.md` and the root `AGENTS.md` (see GOVERNED).
  Input     None. It SCANS the governed set and never reads the payload — see below.
  Silence   Means exactly one thing: every governed file was read and is within budget.
            Anything that stopped the check from running says so in one line instead of
            passing quietly, so "all clear" and "never looked" stay distinguishable.
  Failure   Never blocks, never raises. An unreadable file exits 0 with a note.
  Advisory  Detection is deterministic; the fix is judgment, so this reports and lets the
            author choose — see `workflow.md` -> File size budget.
  Tests     `test_check_rules_size.py`, beside this file: must-block and must-pass halves.

WHY IT SCANS INSTEAD OF READING `tool_input.file_path`
    Keying on the payload path meant the nudge only ever saw Write / Edit / MultiEdit. A rules
    file changed through `sed`, a heredoc, or a `python3` one-liner slipped past in silence,
    and a session doing its edits through the shell tripped the hook exactly never. Recovering
    a path by parsing shell commands is the fragile alternative; scanning is not. The governed
    set is under twenty short files, so a full pass costs nothing, and a clean tree prints
    nothing — the nudge stays silent until some file is actually over budget, whoever put it
    there and however it was written. Wire the matcher to include `Bash` for the same reason.

KNOWN GAP (state it rather than let it pass quietly)
    GOVERNED does not walk the tree, so a nested `AGENTS.md` in a subdirectory is not scanned.
    Add its pattern to GOVERNED if this project has one.

This file is project-agnostic; it ships verbatim in every project the harness scaffolds.
Do not hand-edit it here — reconcile with the `harness-spine:update` skill so the copies do not
drift. If this project deliberately diverges, say why in this docstring.
Tune LINE_BUDGET / BYTE_BUDGET below if a project wants different soft caps. The
Codex project-doc cliff is not a preference -- it is read from that harness's config.
"""
import glob
import json
import os
import re
import sys

# --- Budgets -----------------------------------------------------------------
# A file is over budget when it exceeds EITHER limit. Lines catch sprawl; bytes catch a
# file that is short but dense -- tables, Korean prose (3 bytes/char in UTF-8), and long
# SQL blocks all pack far more context into a line than English prose does, so a
# line-only check reads such a file as smaller than it is.
LINE_BUDGET = 150
BYTE_BUDGET = 10240        # ~10 KB; roughly what 150 lines of this repo's prose weighs
GOVERNED = (".agents/rules/*.md", "AGENTS.md")

# Separate, and NOT a style budget: Codex truncates the project doc at
# `project_doc_max_bytes` SILENTLY -- no warning, and the tail simply is not there in that
# harness. It applies to AGENTS.md alone (rules files are opened on demand, not injected).
# Both harnesses run this as PostToolUse; the payload is not parsed, so it re-checks after
# every tool call, file edit or not (Codex's PreToolUse is measured to receive `apply_patch` in
# probe.log; its PostToolUse on `apply_patch` is not yet measured). No test or CI step checks the
# real AGENTS.md against the cliff, so this nudge is the only warning before the tail goes missing.
# A line overrun costs adherence; this one costs correctness.
PROJECT_DOC = "AGENTS.md"
CODEX_CONFIG = ".codex/config.toml"
CODEX_BYTE_FALLBACK = 32768    # used only when .codex/config.toml does not declare it
BYTE_WARN_RATIO = 0.80         # warn before the cliff, not after

# A generated file is not hand-edited, so the four options below do not apply to it.
GENERATED_MARKERS = ("<!-- generated", "<!--generated")
HEAD_LINES = 5  # how far into a file to look for the marker

AUTHORED_ADVICE = (
    "REVIEW THE WHOLE FILE -- never just shave the line you added. Apply "
    "workflow.md -> 'File size budget', in order: (1) RELOCATE -- a section that's really "
    "another rules file's topic belongs there; move it and leave a one-line pointer. "
    "(2) SPLIT is your judgment -- only a distinct sub-topic that earns its own read trigger in "
    "the AGENTS.md rules table moves to its own rules file, and that row is added with it; "
    "splitting just to hit the number moves the bloat. (3) ABSTRACT -- if "
    "several concrete items are instances of one generative principle, state the principle "
    "and delete the examples it regenerates; keep only examples with a non-derivable why. "
    "(4) COMPRESS -- wording only; it buys the least, which is why it is last. The whole "
    "procedure is the `refactor-agent-rules` skill, live in both harnesses. Reconcile AGENTS.md "
    "descriptions, read triggers and affected rule cross-references with the final ownership; "
    "link existence checks do not prove semantic agreement. Advisory: a "
    "tight single-topic file slightly over is fine."
)

GENERATED_ADVICE = (
    "GENERATED -- do NOT hand-edit it and do NOT run a compression skill over it; the next "
    "regeneration discards both. The only lever is the generator: narrow its scope, or cap "
    "how many entries it emits and have it state how many were truncated. See "
    "enforcement.md -> Keeping a generated artifact alive."
)


def emit(message: str) -> None:
    """Speak to the session. The only channel this hook has; it never changes the outcome."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": message,
                }
            }
        )
    )


def project_root() -> str:
    """`__file__`-based, not cwd: this file is `<root>/.agents/hooks/`, so the root is derivable
    wherever the hook is invoked from. cwd is wrong from any subdirectory."""
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return os.environ["CLAUDE_PROJECT_DIR"]
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def is_generated(head: "list[str]") -> bool:
    return any(line.lstrip().lower().startswith(GENERATED_MARKERS) for line in head)


def codex_doc_budget(root: str) -> "tuple[int, bool]":
    """(limit, declared). Regex rather than tomllib: this must not fail on a config using a
    syntax the local Python cannot parse -- a hook that raises tells the session nothing."""
    try:
        with open(os.path.join(root, CODEX_CONFIG), "r", encoding="utf-8") as f:
            m = re.search(r"^\s*project_doc_max_bytes\s*=\s*(\d+)", f.read(), re.M)
        if m:
            return int(m.group(1)), True
    except OSError:
        pass
    return CODEX_BYTE_FALLBACK, False


def scan(root: str):
    """Return (over_budget, unreadable, n_examined). Every governed file is accounted for."""
    paths = set()
    for pattern in GOVERNED:
        paths.update(glob.glob(os.path.join(root, pattern)))

    over, unreadable = [], []
    for path in sorted(paths):
        rel = os.path.relpath(path, root).replace("\\", "/")
        try:
            # Read as bytes: the budget Codex enforces is bytes, and under UTF-8 a
            # character count would under-report every Korean line by a factor of three.
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as exc:
            unreadable.append((rel, exc.strerror))
            continue
        text = raw.decode("utf-8", errors="replace")
        n_bytes, n_lines = len(raw), text.count("\n")
        if text and not text.endswith("\n"):
            n_lines += 1
        if n_lines > LINE_BUDGET or n_bytes > BYTE_BUDGET:
            head = text.splitlines(keepends=True)[:HEAD_LINES]
            over.append((rel, n_lines, n_bytes, is_generated(head)))
    return over, unreadable, len(paths)


def drain_stdin(idle: float = 0.2) -> None:
    """Read whatever payload is already waiting, and never wait for one that is not coming.

    A bare `sys.stdin.read()` blocks until EOF. Run by hand from an agent's shell, stdin is a pipe
    nobody closes, and two lanes hung on it on 2026-09-17 -- one for 42 minutes. A harness writes
    the payload and closes, so EOF arrives at once; an idle pipe or a TTY is abandoned after
    `idle` seconds. Draining at all is kept so a harness never sees a broken pipe.
    """
    try:
        import select
        fd = sys.stdin.fileno()
        if os.isatty(fd):
            return
        while select.select([fd], [], [], idle)[0]:
            if not os.read(fd, 65536):
                return
    except Exception:  # noqa: BLE001 - a hook never raises into the session
        pass


def main() -> None:
    # The payload is drained and deliberately NOT parsed: what was edited, and by which tool,
    # no longer decides whether this check runs. Removing that coupling is the whole point.
    drain_stdin()

    root = project_root()
    over, unreadable, n_examined = scan(root)

    if n_examined == 0:
        emit(
            f"[rules-size] the governed set is EMPTY ({', '.join(GOVERNED)} under {root}) -- "
            "size budget NOT checked. A glob that stopped matching looks exactly like a clean "
            "tree; that is why this says so instead of passing."
        )
        return

    notes = []
    if unreadable:
        listed = ", ".join(f"{rel} ({why})" for rel, why in unreadable)
        notes.append(f"could not read {listed} -- those were NOT checked.")

    if over:
        parts = []
        for rel, n_lines, n_bytes, _ in over:
            how = []
            if n_lines > LINE_BUDGET:
                how.append(f"{n_lines} lines vs {LINE_BUDGET}")
            if n_bytes > BYTE_BUDGET:
                how.append(f"{n_bytes:,} bytes vs {BYTE_BUDGET:,}")
            parts.append(f"{rel} ({' and '.join(how)})")
        notes.append("over the soft budget: " + ", ".join(parts) + ".")
        if any(not gen for *_, gen in over):
            notes.append(AUTHORED_ADVICE)
        if any(gen for *_, gen in over):
            gen_list = ", ".join(rel for rel, _, _, gen in over if gen)
            notes.append(f"{gen_list}: {GENERATED_ADVICE}")

    # The Codex truncation cliff -- a correctness limit, reported even when the soft
    # budgets are clean, because passing it silently costs the tail of the file.
    doc = os.path.join(root, PROJECT_DOC)
    if os.path.exists(doc):
        limit, declared = codex_doc_budget(root)
        n_bytes = os.path.getsize(doc)
        src = f"{CODEX_CONFIG} project_doc_max_bytes" if declared else (
            f"the {CODEX_BYTE_FALLBACK:,}-byte default ({CODEX_CONFIG} does not declare "
            "project_doc_max_bytes)")
        if n_bytes > limit:
            notes.append(
                f"{PROJECT_DOC} is {n_bytes:,} bytes, OVER {src} ({limit:,}). Codex "
                "truncates it there with no warning, so the tail is missing in that harness "
                "-- move a section to a rules file, or raise the declared limit.")
        elif n_bytes > limit * BYTE_WARN_RATIO:
            notes.append(
                f"{PROJECT_DOC} is {n_bytes:,} bytes, {100 * n_bytes / limit:.0f}% of {src} "
                f"({limit:,}). Past it, Codex truncates silently.")

    if notes:
        emit("[rules-size] " + " ".join(notes))
    # else: every governed file was read and is within budget -- the one thing silence may mean


if __name__ == "__main__":
    main()
