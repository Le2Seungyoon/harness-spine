#!/usr/bin/env python3
"""Fail when the two harnesses' registrations drift apart.

Run directly: python3 .agents/hooks/test_harness_parity.py

`.claude/settings.json` and `.codex/config.toml` cannot be one file — the schemas are unrelated
and neither is derived from the other. So a hook added to one and forgotten in the other leaves
that harness silently unprotected, and nothing about the repo looks wrong. harness.md has asked
for both registrations since it was written; this turns the asking into a check.

The failures it catches, each one measured in a real repo before this check existed:

1. A hook registered on one harness only.
2. A registered script that does not exist or is not executable — a rename that updated one
   caller.
3. A generated Codex role file that no `[agents.*]` entry registers — it exists, it is fresh, and
   it is inert.
4. A deny gate in REQUIRED missing from either harness — symmetry alone passes when one is
   dropped from both files at once.
5. A skill live on one harness only, or one whose directory and `name:` disagree.

Rule links are NOT checked here: `check_rule_links.py` owns that judgment, and two
implementations of one check drift apart (`self-review.md` -> Gates).
"""
import json
import os
import re
import sys
import tomllib

# Print UTF-8 whatever the console code page is (cp949, cp1252, ...): a hook that dies on an
# em dash or a non-ASCII path tells the session nothing.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


ROOT = os.environ.get("CLAUDE_PROJECT_DIR",
                      os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CODEX_HOME = os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex"))
SHARED = re.compile(r"[\w./-]*\.agents/hooks/([\w.-]+)")
# The PreToolUse deny gates every harness must register (enforcement.md -> This project's gates).
# FILL: add each project-specific PreToolUse guard here as it is registered.
REQUIRED = {"PreToolUse": {"git_gates.py"}}


def claude_hooks():
    with open(os.path.join(ROOT, ".claude", "settings.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    out = {}
    for event, entries in (cfg.get("hooks") or {}).items():
        for entry in entries:
            for hook in entry.get("hooks", []):
                for name in SHARED.findall(hook.get("command", "")):
                    out.setdefault(event, set()).add(name)
    return out


def codex_hooks():
    path = os.path.join(ROOT, ".codex", "config.toml")
    with open(path, "rb") as fh:
        cfg = tomllib.load(fh)
    out, total = {}, 0
    for event, entries in (cfg.get("hooks") or {}).items():
        for entry in entries:
            for hook in entry.get("hooks", []):
                total += 1
                for name in SHARED.findall(hook.get("command", "")):
                    out.setdefault(event, set()).add(name)
    return out, total


def trusted_count():
    """How many of this project's hook entries Codex has a trust record for.

    Only the count is read. A stronger check -- "unmoved `trusted_hash` values after a config edit
    mean the hooks stopped" -- was built and REFUTED (2026-08-31, codex-cli 0.151.0-alpha.7.2:
    hashes did not move across a full command rewrite and the hooks still fired). What survives:
    hook entries with NO trust record mean the project was never trusted (`runtime.md` -> Codex
    hook trust).
    """
    path = os.path.join(CODEX_HOME, "config.toml")
    if not os.path.exists(path):
        return None
    marker = os.path.join(ROOT, ".codex", "config.toml")
    with open(path, encoding="utf-8") as fh:
        return sum(1 for line in fh
                   if line.startswith("[hooks.state.") and marker in line)


def main():
    problems = []

    claude = claude_hooks()
    codex, codex_total = codex_hooks()

    for event in sorted(set(claude) | set(codex)):
        a, b = claude.get(event, set()), codex.get(event, set())
        for name in sorted(a - b):
            problems.append(f"{event}: `{name}` is registered on Claude Code but not on Codex")
        for name in sorted(b - a):
            problems.append(f"{event}: `{name}` is registered on Codex but not on Claude Code")

    for event, names in sorted(REQUIRED.items()):
        for name in sorted(names):
            for harness, got in (("Claude Code", claude), ("Codex", codex)):
                if name not in got.get(event, set()):
                    problems.append(f"{event}: required gate `{name}` is not registered on {harness}")

    for event, names in sorted(claude.items()):
        for name in sorted(names | codex.get(event, set())):
            script = os.path.join(ROOT, ".agents", "hooks", name)
            if not os.path.exists(script):
                problems.append(f"{event}: `{name}` is registered but does not exist")
            elif name.endswith(".sh") and not os.access(script, os.X_OK):
                problems.append(f"{event}: `{name}` is registered but is not executable")

    # Generated role files that nothing registers. Registration is what makes a role live, so a
    # file without one is inert -- fine while a lane is not in use, but it should be a decision
    # rather than something nobody noticed.
    roles_dir = os.path.join(ROOT, ".codex", "agents")
    cfg_path = os.path.join(ROOT, ".codex", "config.toml")
    if os.path.isdir(roles_dir) and os.path.exists(cfg_path):
        with open(cfg_path, "rb") as fh:
            agents = tomllib.load(fh).get("agents") or {}
        registered = {
            os.path.basename(str(a.get("config_file", "")))
            for a in agents.values()
            if isinstance(a, dict)
        }
        for name in sorted(os.listdir(roles_dir)):
            if name.endswith(".toml") and name not in registered:
                problems.append(
                    f"`.codex/agents/{name}` is generated but no [agents.*] entry registers it — "
                    f"the role is inert. Register it or stop generating it."
                )


    # Skills ship by copy, and the two harnesses read a skill's identity from different places --
    # Claude Code from the DIRECTORY name, Codex from the frontmatter `name:` (measured 2026-08-28;
    # neither errors on a mismatch, the skill simply registers under two names). Symmetry is this
    # file's question. Whether the copies are *current* is `build-agents.py --check`'s, and the two
    # are not the same: a skill can be byte-identical in one harness and absent from the other.
    skills_src = os.path.join(ROOT, ".agents", "skills")
    skill_names = []
    if os.path.isdir(skills_src):
        for name in sorted(os.listdir(skills_src)):
            entry = os.path.join(skills_src, name, "SKILL.md")
            if not os.path.isfile(entry):
                continue
            skill_names.append(name)
            for target in (".claude/skills", ".codex/skills"):
                if not os.path.isfile(os.path.join(ROOT, target, name, "SKILL.md")):
                    problems.append(
                        f"`{target}/{name}/SKILL.md` is missing — the skill is live on one harness "
                        f"only. Run `python3 .agents/hooks/build-agents.py`."
                    )
            with open(entry, encoding="utf-8") as fh:
                declared = next(
                    (ln.split(":", 1)[1].strip()
                     for ln in fh.read().split("\n---", 1)[0].splitlines()
                     if ln.startswith("name:")),
                    None,
                )
            if declared != name:
                problems.append(
                    f"`.agents/skills/{name}/SKILL.md` declares `name: {declared}` but sits in "
                    f"`{name}/`. Claude Code would register it as `{name}` and Codex as "
                    f"`{declared}` — one skill, two names, no error from either harness."
                )

    # Trust lives in each person's ~/.codex, per checkout path — machine state, not repo state.
    # It is reported, never failed: a PR's evidence must depend on the code only (user, 2026-10-27).
    trusted = trusted_count()
    if trusted is None:
        print("NOTE  no ~/.codex/config.toml — trust not checked")
    elif trusted != codex_total:
        print(
            f"WARN  Codex trust is stale here: {codex_total} hook entries in .codex/config.toml but "
            f"{trusted} trusted in {CODEX_HOME}/config.toml — Codex hooks are NOT running in this "
            f"checkout. Run the Codex CLI once from it and accept 'Trust all and continue' "
            f"(runtime.md → Codex hook trust). Not a failure: machine state, not repo state."
        )

    if problems:
        print("FAIL  harness registrations have drifted\n")
        for p in problems:
            print(f"  - {p}")
        return 1

    shared = sorted({n for names in claude.values() for n in names})
    print(f"PASS  both harnesses register the same {len(shared)} shared hook(s), all present, "
          f"every role registered, {len(skill_names)} skill(s) live on both with matching "
          f"directory/name")
    return 0


if __name__ == "__main__":
    sys.exit(main())
