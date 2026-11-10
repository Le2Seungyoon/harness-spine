#!/usr/bin/env python3
"""Tests for git_gates.py -- run: python3 .agents/hooks/test_git_gates.py

Must-block and must-pass halves for both gates (`enforcement.md` -> Hook contracts). Every
regression case below was a live miss on 2026-09-17 against the grep + `if` prefix registration
this script replaced; `GIT_GATES_HOOK` points the suite at another implementation, which is how
that was shown.

The push cases are hermetic: a bare repo on disk stands in for the remote, so `git fetch` works
with no network and `origin/main` is a real ref. Trailer strings are assembled rather than written
out, so running this file through a gated shell does not trip the gate on its own source.
Stdlib only.

Beyond the regressions: a tree with NO `origin` remote passes and says the check did not run; a
multi-base project (`BASES = ("develop", "main")`, exercised on a patched copy of the hook) denies
a branch that contains main but not develop; and a push whose destination is PROTECTED is denied
in every refspec/directory form (`test_push_main`).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HOOK = os.environ.get("GIT_GATES_HOOK") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "git_gates.py")
COAUTH = "Co-" + "Authored-" + "By: Claude <x@y>"
GENWITH = "Generated " + "with Claude Code"

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


PUSH_HOOK = None   # set in main(): the hook with the fixture branch config


def run(mode, command, cwd, hook=None):
    """Hook process cwd is deliberately NOT the payload cwd: the harness runs hooks from the
    session root, so the payload is the only honest source of where the shell sits."""
    payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": cwd,
                          "tool_input": {"command": command, "description": "x"}})
    hook = hook or (PUSH_HOOK if mode == "push" else HOOK)
    p = subprocess.run([sys.executable, hook, mode], input=payload, capture_output=True,
                       text=True, encoding="utf-8", cwd=tempfile.gettempdir(), timeout=25)
    return '"deny"' in p.stdout, p.stdout + p.stderr


def posix(path):
    """Paths go into shell commands below, where a backslash is an escape, not a separator."""
    return path.replace(os.sep, "/")


def git(cwd, *args):
    return subprocess.run(("git",) + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def test_commit(tmp):
    blocked = {
        "plain -m": f'git commit -m "fix\n\n{COAUTH}"',
        "generated-with line": f'git commit -m "fix\n\n{GENWITH}"',
        "-C <dir> form (was a bypass)": f'git -C /some/tree commit -m "fix\n\n{COAUTH}"',
        "chained after cd": f'cd /tmp && git commit -qm "fix\n\n{COAUTH}"',
        "$(cat <<EOF) message": f"git commit -m \"$(cat <<'EOF'\nfix\n\n{COAUTH}\nEOF\n)\"",
        "-F - from a heredoc": f"git commit -F - <<'EOF'\nfix\n\n{COAUTH}\nEOF",
        "--trailer": f'git commit -m fix --trailer "{COAUTH}"',
        "inside bash -c": f"bash -c 'git add -A && git commit -m \"fix\n\n{COAUTH}\"'",
        "env prefix": f'GIT_AUTHOR_NAME=x git commit -m "fix\n\n{COAUTH}"',
        "-F - heredoc followed by another command":
            f"git commit -F - <<'EOF'\nfix\n\n{COAUTH}\nEOF\ngit log -1 --oneline",
        "-F - from a spaced heredoc (<< EOF)": f"git commit -F - << EOF\nfix\n\n{COAUTH}\nEOF",
    }
    for name, cmd in blocked.items():
        denied, out = run("commit", cmd, tmp)
        check(f"commit: blocks {name}", denied, out)

    msgfile = os.path.join(tmp, "msg.txt")
    with open(msgfile, "w", encoding="utf-8") as fh:
        fh.write(f"fix\n\n{COAUTH}\n")
    check("commit: blocks -F <file> carrying the trailer", run("commit", "git commit -F msg.txt", tmp)[0])

    passed = {
        "a clean message": 'git commit -m "규칙을 정한다"',
        "commit-tree": f'git commit-tree HEAD^{{tree}} -m "{COAUTH}"',
        "git log --grep": f'git log --grep "{COAUTH}"',
        "a prompt that mentions a commit and the trailer":
            f'agent-cli dispatch --spec "commit (no AI trailer). git commit must not carry {COAUTH}"',
        "a heredoc into a file mentioning both":
            f"cat > notes.md <<'EOF'\nrun git commit -m x; never add {COAUTH}\nEOF",
        "a clean commit followed by an unrelated echo":
            f'git commit -m "fix" && echo "the gate refuses {COAUTH}"',
        # Measured 2026-09-17: the unseen-message fallback read past the commit into these.
        "a heredoc commit, then a grep for the trailer names":
            f"git commit -F - <<'EOF'\nfix\nEOF\ngit log -1 --format=%B | grep -ci '{COAUTH[:14]}'",
        "a heredoc commit, then an echo that mentions them":
            f"git commit -F - <<'EOF' && echo 'no {COAUTH} / {GENWITH} added'\nfix\nEOF",
        "a -F - commit fed by a pipe, then a grep on the next line":
            f"printf fix | git commit -F -\ngrep -rn '{COAUTH}' .",
    }
    for name, cmd in passed.items():
        denied, out = run("commit", cmd, tmp)
        check(f"commit: passes {name}", not denied, out)


def build(tmp):
    """`behind` lacks origin/main; `ahead` contains it. Both are worktrees of one repo."""
    remote, work = os.path.join(tmp, "remote.git"), os.path.join(tmp, "behind")
    subprocess.run(["git", "init", "--bare", "-q", remote], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", work], check=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        git(work, "config", k, v)
    for name in ("a", "b"):
        open(os.path.join(work, name), "w").write(name)
        git(work, "add", "-A"), git(work, "commit", "-qm", name)
        if name == "a":
            base = git(work, "rev-parse", "HEAD").stdout.strip()
            git(work, "remote", "add", "origin", remote)
        git(work, "push", "-q", "origin", "main")
    ahead = os.path.join(tmp, "ahead")
    git(work, "worktree", "add", "-q", "-b", "merged", ahead, "main")
    git(work, "checkout", "-q", "-b", "feat", base)
    return posix(work), posix(ahead)


def test_push(tmp):
    behind, ahead = build(tmp)
    push = "git push -u origin HEAD"

    check("push: a command that is not a push is untouched", not run("push", "git status", behind)[0])
    check("push: HEAD behind origin/main is denied", run("push", push, behind)[0])
    check("push: HEAD containing origin/main is allowed", not run("push", push, ahead)[0])

    # The regression: the session sits in one tree, the command acts in another.
    for form in (f"cd {ahead} && {push}", f"git -C {ahead} push -u origin HEAD", "cd ../ahead; git push"):
        denied, out = run("push", form, behind)
        check(f"push: a merged tree named by the command is allowed from a behind session ({form[:12]})",
              not denied, out)
    for form in (f"cd {behind} && {push}", f"git -C {behind} push"):
        denied, out = run("push", form, ahead)
        check(f"push: a behind tree named by the command is denied from a merged session ({form[:12]})",
              denied, out)
    check("push: `echo git push` is not a push", not run("push", "echo git push", behind)[0])

    git(behind, "remote", "set-url", "origin", os.path.join(tmp, "gone.git"))
    denied, out = run("push", push, behind)
    check("push: an unreachable remote does not block", not denied, out)
    check("push: an unreachable remote says the check did not run", "NOT checked" in out, out)


def test_push_no_remote(tmp):
    lone = os.path.join(tmp, "lone")
    subprocess.run(["git", "init", "-q", "-b", "main", lone], check=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        git(lone, "config", k, v)
    open(os.path.join(lone, "a"), "w").write("a")
    git(lone, "add", "-A"), git(lone, "commit", "-qm", "a")
    git(lone, "checkout", "-q", "-b", "feat")   # on main, the push-to-main gate would deny first
    denied, out = run("push", "git push -u origin HEAD", lone)
    check("push: a tree with no origin remote is not blocked", not denied, out)
    check("push: ...and says the merge state was NOT checked", "no `origin` remote" in out, out)


def configured_hook(tmp, bases):
    """A copy of the hook with the fixture branch config: PROTECTED = main, BASES = `bases`.

    The push fixtures below build repos on `main`, but PROTECTED / BASES are FILL slots a project
    sets to its own branches -- so the suite must not depend on what this project filled in. When
    the implementation under test has no such constants (`GIT_GATES_HOOK` pointing elsewhere), it
    is used as-is and the run says so.
    """
    with open(HOOK, encoding="utf-8") as fh:
        src = fh.read()
    patched, n_p = re.subn(r"^PROTECTED = .*$", 'PROTECTED = "main"', src, flags=re.M)
    patched, n_b = re.subn(r"^BASES = .*$", f"BASES = {tuple(bases)!r}", patched, flags=re.M)
    if not (n_p and n_b):
        print(f"NOTE  {HOOK} has no PROTECTED/BASES constants -- push cases run it unpatched")
        return HOOK
    path = os.path.join(tmp, f"git_gates_{'_'.join(bases)}.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(patched)
    return path


def test_push_develop_base(tmp):
    """origin has develop ahead of main; a branch holding main but not develop is denied."""
    hook = configured_hook(tmp, ("develop", "main"))
    remote, work = os.path.join(tmp, "r2.git"), os.path.join(tmp, "w2")
    subprocess.run(["git", "init", "--bare", "-q", remote], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", work], check=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        git(work, "config", k, v)
    git(work, "remote", "add", "origin", remote)
    open(os.path.join(work, "a"), "w").write("a")
    git(work, "add", "-A"), git(work, "commit", "-qm", "a")
    git(work, "push", "-q", "origin", "main")
    git(work, "checkout", "-q", "-b", "develop")
    open(os.path.join(work, "d"), "w").write("d")
    git(work, "add", "-A"), git(work, "commit", "-qm", "d")
    git(work, "push", "-q", "origin", "develop")
    git(work, "checkout", "-q", "-b", "feature/x", "main")
    denied, out = run("push", "git push -u origin HEAD", work, hook)
    check("push: a branch missing origin/develop is denied", denied, out)
    check("push: ...and the reason names origin/develop", "origin/develop" in out, out)
    git(work, "merge", "-q", "--no-edit", "develop")
    denied, out = run("push", "git push -u origin HEAD", work, hook)
    check("push: after merging develop it is allowed", not denied, out)


def test_push_main(tmp):
    """Main changes only through a PR: a push whose destination is `main` is denied, whatever
    the refspec spelling or the directory form; a branch merely NAMED like main passes."""
    d = os.path.join(tmp, "m")
    os.mkdir(d)
    _, ahead = build(d)          # `ahead` is on `merged` and contains origin/main
    blocked = {
        "git push origin main": ahead,
        "git push origin HEAD:main": ahead,
        "git push origin HEAD:refs/heads/main": ahead,
        "git push origin +main": ahead,
        "git push -f origin +HEAD:main": ahead,
        "git push origin :main": ahead,
        "git push --force-with-lease origin feature/x:main": ahead,
        f"git -C {ahead} push origin HEAD:refs/heads/main": tmp,
        f"cd {ahead} && git push origin HEAD:main": tmp,
        f"git -C {ahead} push -u origin main": tmp,
        "git push --all origin": ahead,
        "git push --mirror origin": ahead,
    }
    for cmd, cwd in blocked.items():
        denied, out = run("push", cmd, cwd)
        check(f"push-main: blocks `{cmd[:48]}`", denied, out)
        check(f"push-main: ...reason names the PR route ({cmd[:24]})", "changes only through a PR" in out, out)
    git(ahead, "checkout", "-q", "main")
    denied, out = run("push", "git push origin HEAD", ahead)
    check("push-main: blocks `git push origin HEAD` while on main", denied, out)
    denied, out = run("push", "git push", ahead)
    check("push-main: blocks a bare `git push` while on main", denied, out)
    git(ahead, "checkout", "-q", "merged")
    passed = {
        "git push origin HEAD:develop": ahead,
        "git push -u origin HEAD": ahead,
        "git push origin main-fix": ahead,
        "git push origin HEAD:main-fix": ahead,
        "git push origin feature/main": ahead,
        "git push origin HEAD:refs/heads/feature/main": ahead,
        f"git -C {ahead} push -u origin HEAD:develop": tmp,
        f"cd {ahead} && git push origin feature/main": tmp,
        "git push": ahead,
    }
    for cmd, cwd in passed.items():
        denied, out = run("push", cmd, cwd)
        check(f"push-main: passes `{cmd[:48]}`", not denied, out)


def main():
    global PUSH_HOOK
    tmp = posix(tempfile.mkdtemp(prefix="git-gates-"))
    try:
        PUSH_HOOK = configured_hook(tmp, ("main",))
        test_commit(tmp)
        test_push(tmp)
        test_push_no_remote(tmp)
        test_push_develop_base(tmp)
        test_push_main(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    if failures:
        print(f"{len(failures)} FAILED: " + ", ".join(failures))
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
