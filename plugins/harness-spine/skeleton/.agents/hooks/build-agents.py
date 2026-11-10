#!/usr/bin/env python3
"""Generate the per-harness agent definitions from `.agents/agents/**`.

**Why generation and not routing.** Both harnesses deliver an agent definition by putting it in
the lane's system prompt, and neither of them dereferences a path for you:

  - A Claude Code subagent file's body *becomes* the system prompt. `@path` imports are not
    expanded there (verified) — an `@.agents/agents/x.md` line would arrive as literal text.
  - Codex's `developer_instructions` is a literal TOML string. Same story.

So a pure "one file, two pointers" layout would replace a guaranteed injection with "the model
has to remember to open a file" on **both** sides. Instead the source of truth stays single and
the per-harness files are build artifacts of it, committed so the harnesses can read them
directly.

Layout:

    .agents/agents/<name>.md          source of truth: harness-neutral frontmatter + shared body
      |
      +--> .claude/agents/<name>.md   frontmatter (name, description, model.claude) + body
      +--> .codex/agents/<name>.toml  name, description, model.codex, nickname_candidates,
                                      developer_instructions = body
    .agents/skills/<name>/**          copied verbatim to .claude/skills/<name>/ and .codex/skills/<name>/

Harness differences are frontmatter keys (`model.claude`, `model.codex`, `nickname_candidates`),
never sidecar files: a sidecar invites harness-shaped prose to accumulate, and instructions almost
never differ between harnesses -- when they seem to, write both variants as labelled paragraphs in
the one body (`harness.md` -> Where a thing lives). A generated Codex role is inert until an
`[agents.*]` entry in `.codex/config.toml` registers it; `test_harness_parity.py` flags one that
nothing registers.

Run: python3 .agents/hooks/build-agents.py            # regenerate (writes)
     python3 .agents/hooks/build-agents.py --check    # compare only (writes nothing)
     python3 .agents/hooks/build-agents.py --hook     # PostToolUse: rebuild iff the edit was a source

`--check` exists because a generated file that nobody regenerates drifts silently
(`enforcement.md` -> Keeping a generated artifact alive). First stdout line is a
machine-readable marker so a caller cannot mistake a Python traceback for drift:

    AGENTS_FRESH            exit 0
    AGENTS_STALE            exit 1   (and every drifted path is named)
    AGENTS_UNKNOWN: <why>   exit 2   (cannot judge -- not the same thing as drift)
"""
import difflib
import json
import os
import re
import sys

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

SRC_DIR = ".agents/agents"
CLAUDE_DIR = ".claude/agents"
CODEX_DIR = ".codex/agents"

# Skills are copied verbatim to both harnesses -- no per-harness delta, because a skill body is
# read by both and anything true of only one belongs in a labelled paragraph inside it.
SKILLS_SRC = ".agents/skills"
SKILL_OUT = (".claude/skills", ".codex/skills")

# Codex validates SKILL.md frontmatter strictly and rejects unknown keys, so the source is held to
# the intersection both harnesses accept. Measured 2026-08-28: the two harnesses disagree on which
# field is the skill's identity -- Claude Code uses the DIRECTORY name and ignores `name:`, Codex
# uses `name:` and ignores the directory. Neither errors on a mismatch; the skill just registers
# under two different names. `load_skill` therefore requires them to be equal.
SKILL_KEYS = ("name", "description")

# Frontmatter keys understood in the source of truth. An unknown key is a hard error rather than
# a silent drop: the whole point of this file is that the source is the only place to edit, so a
# key that generates nothing would be an edit that appears to work and does not.
# Harness-specific values live here as dotted keys, not in a sidecar file. A sidecar invites
# harness-shaped prose to accumulate in it, and two of the three sections that were once in one
# turned out to describe both harnesses equally. Metadata differs between harnesses; instructions
# almost never do — and when they seem to, check before believing it.
SRC_KEYS = ("name", "description", "model.claude", "model.codex", "nickname_candidates")
CLAUDE_ONLY = ("model.claude",)
CODEX_ONLY = ("model.codex", "nickname_candidates")



# ---------------------------------------------------------------- source parsing


class BuildError(Exception):
    """Something in `.agents/agents/**` cannot be turned into an output file."""


def split_frontmatter(text, path):
    """Return (ordered [(key, raw_value)], body).

    Deliberately not a YAML parser. The values here are plain scalars and one inline list, and a
    real YAML round-trip would requote the Korean descriptions -- which would make the generated
    `.claude/agents/*.md` differ from the hand-written originals for no reason. Raw text in, raw
    text out.
    """
    if not text.startswith("---\n"):
        raise BuildError(f"{path}: must start with a `---` frontmatter fence")
    end = text.find("\n---\n", 3)
    if end == -1:
        raise BuildError(f"{path}: frontmatter fence is never closed")
    block = text[4:end + 1]
    body = text[end + len("\n---\n"):]

    fields = []
    for lineno, line in enumerate(block.splitlines(), start=2):
        if not line.strip():
            continue
        if ":" not in line:
            raise BuildError(f"{path}:{lineno}: frontmatter line is not `key: value`")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if not key or line[0].isspace():
            raise BuildError(f"{path}:{lineno}: nested frontmatter is not supported")
        fields.append((key, value))
    return fields, body


def parse_list(raw, path, key):
    """Parse an inline JSON list frontmatter value, e.g. `["a", "b"]`."""
    try:
        value = json.loads(raw)
    except ValueError:
        raise BuildError(f"{path}: `{key}` must be an inline JSON list, got {raw!r}")
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise BuildError(f"{path}: `{key}` must be a list of strings, got {raw!r}")
    return value


def load_source(root, name):
    """Load `<name>.md` — the single source; harness deltas are frontmatter keys."""
    src_path = os.path.join(root, SRC_DIR, f"{name}.md")
    with open(src_path, encoding="utf-8") as fh:
        fields, body = split_frontmatter(fh.read(), src_path)

    for key, _ in fields:
        if key not in SRC_KEYS:
            raise BuildError(
                f"{src_path}: unknown frontmatter key `{key}` "
                f"(known: {', '.join(SRC_KEYS)}). Nothing would generate it."
            )
    meta = dict(fields)
    if meta.get("name", name) != name:
        raise BuildError(f"{src_path}: frontmatter `name: {meta.get('name')}` != filename `{name}`")
    for required in ("name", "description"):
        if required not in meta:
            raise BuildError(f"{src_path}: frontmatter is missing `{required}`")
    if not body.strip():
        raise BuildError(f"{src_path}: body is empty")

    if 'nickname_candidates' in meta:
        meta['nickname_candidates'] = parse_list(
            meta['nickname_candidates'], src_path, 'nickname_candidates')
    return fields, body, meta


def source_names(root):
    """Agent sources, possibly none.

    A project with no dispatched lane yet has no `.agents/agents/`, and that is a legal state,
    not an error. The empty-target contract (`enforcement.md` -> Hook contracts) is kept one level up: `render_all` refuses when
    agents AND skills together generate nothing.
    """
    d = os.path.join(root, SRC_DIR)
    if not os.path.isdir(d):
        return []
    return sorted(
        f[: -len(".md")]
        for f in os.listdir(d)
        if f.endswith(".md") and not f.endswith(".codex.md")
    )


# ---------------------------------------------------------------- renderers


def render_claude(fields, body):
    """`.claude/agents/<name>.md` -- frontmatter then the shared body, and nothing else.

    Emitted in source order so the generated file is byte-identical to the hand-written one it
    replaces. `model:` in particular must survive: it was pinned to `opus` on purpose, because a
    lane that inherits the session model reviews unevenly.
    """
    lines = ["---"]
    for k, v in fields:
        if k in CODEX_ONLY:
            continue
        lines.append(f"model: {v}" if k == "model.claude" else f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.lstrip("\n")


def toml_basic_string(s):
    out = s.replace("\\", "\\\\").replace('"', '\\"')
    out = out.replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
    return f'"{out}"'


def toml_multiline_string(s):
    """A TOML `\"\"\"...\"\"\"` literal. Escapes so that no body text can terminate it early."""
    out = s.replace("\\", "\\\\").replace('"""', '""\\"')
    if out.endswith('"'):
        out = out[:-1] + '\\"'
    return '"""\n' + out + '\n"""'


def render_codex(fields, body, meta):
    """`.codex/agents/<name>.toml` -- the same body Claude gets, no delta appended."""
    lines = [
        f"name = {toml_basic_string(meta['name'])}",
        f"description = {toml_basic_string(meta['description'])}",
    ]
    if "model.codex" in meta:
        lines.append(f"model = {toml_basic_string(meta['model.codex'])}")
    if "nickname_candidates" in meta:
        rendered = ", ".join(toml_basic_string(v) for v in meta["nickname_candidates"])
        lines.append(f"nickname_candidates = [{rendered}]")
    lines.append("")
    lines.append(f"developer_instructions = {toml_multiline_string(body.strip(chr(10)))}")
    return "\n".join(lines) + "\n"


def load_skill(root, name):
    """Validate one skill source directory and return {relative path: text} for its files."""
    src_dir = os.path.join(root, SKILLS_SRC, name)
    entry = os.path.join(src_dir, "SKILL.md")
    if not os.path.isfile(entry):
        raise BuildError(f"{SKILLS_SRC}/{name}: no SKILL.md -- both harnesses require that name")
    with open(entry, encoding="utf-8") as fh:
        fields, body = split_frontmatter(fh.read(), entry)
    meta = dict(fields)
    for key, _ in fields:
        if key not in SKILL_KEYS:
            raise BuildError(
                f"{entry}: frontmatter key `{key}` is not accepted by both harnesses "
                f"(allowed: {', '.join(SKILL_KEYS)}). Codex rejects the file outright."
            )
    for required in SKILL_KEYS:
        if not meta.get(required):
            raise BuildError(f"{entry}: frontmatter is missing `{required}`")
    if meta["name"] != name:
        raise BuildError(
            f"{entry}: frontmatter `name: {meta['name']}` != directory `{name}`. Claude Code would "
            f"register it as `{name}` and Codex as `{meta['name']}` -- one skill, two names, "
            f"no error from either."
        )
    if not body.strip():
        raise BuildError(f"{entry}: body is empty")

    files = {}
    for dirpath, _, filenames in os.walk(src_dir):
        for filename in sorted(filenames):
            abspath = os.path.join(dirpath, filename)
            rel = os.path.relpath(abspath, src_dir).replace(os.sep, "/")
            try:
                with open(abspath, encoding="utf-8") as fh:
                    files[rel] = fh.read()
            except UnicodeDecodeError:
                raise BuildError(f"{SKILLS_SRC}/{name}/{rel}: not UTF-8 text; cannot be copied")
    return files


def skill_names(root):
    d = os.path.join(root, SKILLS_SRC)
    if not os.path.isdir(d):
        return []
    return sorted(n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n)))


def render_skills(root):
    out = {}
    for name in skill_names(root):
        for rel, text in load_skill(root, name).items():
            for target in SKILL_OUT:
                out[f"{target}/{name}/{rel}"] = text
    return out


def orphan_skill_dirs(root):
    """Generated skill directories with no source -- a rename leaves the old name registered."""
    live = set(skill_names(root))
    stale = []
    for target in SKILL_OUT:
        d = os.path.join(root, target)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if os.path.isdir(os.path.join(d, name)) and name not in live:
                stale.append(f"{target}/{name}")
    return stale


def render_all(root):
    """Return {relative path: intended contents} for every generated file."""
    out = {}
    for name in source_names(root):
        fields, body, meta = load_source(root, name)
        out[f"{CLAUDE_DIR}/{name}.md"] = render_claude(fields, body)
        out[f"{CODEX_DIR}/{name}.toml"] = render_codex(fields, body, meta)
    out.update(render_skills(root))
    if not out:
        raise BuildError(f"neither {SRC_DIR} nor {SKILLS_SRC} holds a source under {root} -- "
                         f"nothing to generate is a moved directory, not a clean tree")
    return out


# ---------------------------------------------------------------- commands


def read_if_exists(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def run_build(root):
    rendered = render_all(root)
    written = []
    for rel, text in sorted(rendered.items()):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if read_if_exists(path) == text:
            continue
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        written.append(rel)
    if written:
        print("build-agents: rewrote " + ", ".join(written))
    else:
        print(f"build-agents: {len(rendered)} generated file(s) already current")
    for rel in orphan_skill_dirs(root):
        print(f"build-agents: WARNING {rel}/ has no source -- delete it by hand")
    return 0


def run_check(root):
    rendered = render_all(root)
    drifted = []
    for rel, text in sorted(rendered.items()):
        actual = read_if_exists(os.path.join(root, rel))
        if actual != text:
            drifted.append((rel, actual, text))
    orphans = orphan_skill_dirs(root)
    if not drifted and not orphans:
        print(f"AGENTS_FRESH — {len(rendered)} generated file(s) match {SRC_DIR} + {SKILLS_SRC}")
        return 0
    print(
        f"AGENTS_STALE — {len(drifted)} generated file(s) differ, "
        f"{len(orphans)} orphaned skill dir(s):"
    )
    for rel, _, _ in drifted:
        print(f"  {rel}")
    for rel in orphans:
        print(f"  {rel}/  (no source under {SKILLS_SRC}/ -- renamed or deleted; remove it)")
    print("Edit the source under `.agents/agents/` or `.agents/skills/`, never the generated")
    print("file, then run")
    print("`python3 .agents/hooks/build-agents.py` and commit both.")
    for rel, actual, text in drifted:
        print(f"\n--- diff: {rel} (on disk -> would generate)")
        if actual is None:
            print("  (missing on disk)")
            continue
        diff = difflib.unified_diff(
            actual.splitlines(keepends=True),
            text.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
        sys.stdout.writelines(diff)
    return 1


def run_hook(root):
    """PostToolUse: rebuild only when the edited file was one of the sources.

    The hook matcher can only select on tool name, so the path test lives here. Advisory --
    a build failure is reported to the session, never used to block the edit.
    """
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    tool_input = data.get("tool_input") or {}
    paths = [tool_input.get("file_path") or ""]
    paths.extend(re.findall(
        r"^\*\*\* (?:Update|Add|Delete) File: (.+)$",
        tool_input.get("command") or "",
        re.M,
    ))
    paths = [path.strip().replace("\\", "/") for path in paths if path.strip()]
    def is_source(path):
        for src in (SRC_DIR, SKILLS_SRC):
            if (f"/{src}/" in path or path.startswith(f"{src}/")) and path.endswith(".md"):
                return True
        return False

    source_edited = any(is_source(path) for path in paths)
    if not source_edited:
        return 0
    try:
        run_build(root)
        return 0
    except (BuildError, OSError) as exc:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": (
                            f"[build-agents] {SRC_DIR} changed but the per-harness files could "
                            f"NOT be regenerated: {exc}. `.claude/agents/**` and "
                            f"`.codex/agents/**` are now stale -- fix the source and run "
                            f"`python3 .agents/hooks/build-agents.py`."
                        ),
                    }
                }
            )
        )
        return 0


def main(argv):
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    args = list(argv)
    if "--root" in args:
        i = args.index("--root")
        try:
            root = os.path.abspath(args[i + 1])
        except IndexError:
            print("AGENTS_UNKNOWN: --root needs a path")
            return 2
        del args[i:i + 2]

    mode = "build"
    for flag in ("--check", "--hook"):
        if flag in args:
            mode = flag[2:]
            args.remove(flag)
    if args:
        print(f"AGENTS_UNKNOWN: unrecognised argument(s) {args}")
        return 2

    try:
        if mode == "check":
            return run_check(root)
        if mode == "hook":
            return run_hook(root)
        return run_build(root)
    except BuildError as exc:
        print(f"AGENTS_UNKNOWN: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
