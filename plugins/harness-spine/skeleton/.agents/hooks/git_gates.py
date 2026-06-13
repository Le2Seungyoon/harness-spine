#!/usr/bin/env python3
"""PreToolUse gates on git invocations -- one script, both harnesses.

usage: git_gates.py push     deny `git push` whose destination is PROTECTED (it changes only
                             through a PR), and deny one unless every base branch (BASES) that
                             exists on `origin` is an ancestor of the pushed tree's HEAD
       git_gates.py commit   deny `git commit` whose message carries an AI-attribution trailer

Enforces `git-workflow.md` -> Commits and -> Before you push; the gate table is `enforcement.md`.
Replaces the inline-shell gates of the `.claude/`-only skeleton: Codex registrations have no `if`
prefix filter, so one script that parses the command serves both harnesses.
    - BASES lists every long-lived branch a push must already contain. A project with a staging
      branch (`develop` <- feature, `main` <- develop) lists both, so a hotfix on the default
      branch cannot be skipped by a branch cut from staging. A base the remote does not have yet
      is skipped and SAID so.
    - No `origin` (a fresh local repo) means the merge state cannot be checked: the gate passes
      (environment failure) and says so on stderr.
Tests: `test_git_gates.py`, beside this file.

WHY THE COMMAND IS PARSED, NOT GREPPED (measured 2026-09-17)
    1. `git -C <dir> commit` and `git -C <dir> push` matched neither the old `git commit` grep nor
       the `Bash(git commit:*)` prefix filter, so a commit carrying the trailer landed.
    2. The push gate asked the SESSION's tree. A session rooted in worktree A that ran
       `cd B && git push` was judged against A -- and denied, though B contained origin/main.
       The target is where the command acts: `cd <dir>` chained before it, then each `-C <dir>`.
    3. Grepping the whole command text for the trailer denied commands that only MENTION a commit
       and the trailer -- a lane prompt, a heredoc into a file. Only the invocation's own message
       (`-m`, `-F`, `--trailer`) is inspected; when the message cannot be seen (`-F -` from a
       heredoc) that invocation's own words and heredoc body are.
    4. That fallback once read to the END of the command, so a clean heredoc commit followed by a
       `grep` for the trailer names was denied. It stops at the invocation's separator; only a
       heredoc the invocation opens extends it, and only to that heredoc's delimiter line.

PUSH TO THE PROTECTED BRANCH: it changes through a PR, never a push. The host's branch protection
is the server-side half; this is the local half, so the mistake is caught before the network. The
destination is read from each refspec (`[+]src[:dst]`, `dst` = `src` when absent;
`refs/heads/main` == `main`), and `HEAD` or no refspec at all means the target tree's current
branch. `--all`/`--mirror` would push it too. A branch merely named like it (`main-fix`,
`feature/main`) passes.

Payload: both harnesses send `tool_input.command` as one string for a shell call, and a top-level
`cwd`; Codex's `apply_patch` also arrives in `command`, but never parses as a git invocation.
Environment failure exits 0 (`enforcement.md` -> Hook contracts); a push gate that could not
fetch says so on stderr rather than passing quietly.
"""
import json
import os
import re
import shlex
import subprocess
import sys

# Print UTF-8 whatever the console code page is (cp949, cp1252, ...): a hook that dies on an
# em dash or a non-ASCII path tells the session nothing.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

FETCH_TIMEOUT = 12      # per base; 2 x 12 s stays below the registration's 30 s
# FILL: the branch that changes only by PR, and every long-lived base a push must contain
# (e.g. ("develop", "main") with a staging branch). Keep FETCH_TIMEOUT x len(BASES) below the
# registration's timeout.
PROTECTED = "main"
BASES = ("main",)
# FILL: how a change reaches PROTECTED here -- named in the deny message.
PR_ROUTE = "Push the work branch and open a PR (`gh pr create` or the host's web UI)"
TRAILER = re.compile(r"co-authored-by|generated with", re.I)
SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "\n", ";;"}
# git's global options that take a separate value; `-C` is handled on its own.
VALUED_GLOBALS = {"-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))
    sys.exit(0)


def tokenize(cmd):
    """Shell words plus separators as their own tokens. A newline separates commands but stays
    inside a quoted word. Returns None when the text is not balanced shell."""
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|()\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    try:
        return list(lex)
    except ValueError:
        return None


def invocations(cmd, cwd, depth=0):
    """Yield (subcommand, target_dir, argv_after_subcommand, own_text) for each git call.
    own_text is argv plus the body of any heredoc argv opens -- never a later command."""
    toks = tokenize(cmd)
    if toks is None:
        return
    here, i, start = cwd, 0, True
    while i < len(toks):
        t = toks[i]
        if t in SEPARATORS or all(c in ";&|()\n" for c in t):
            start = True
            i += 1
            continue
        if not start:
            i += 1
            continue
        start = False
        while i < len(toks) and re.fullmatch(r"[A-Za-z_]\w*=.*", toks[i]):   # VAR=x git ...
            i += 1
        if i >= len(toks):
            break
        word = toks[i]
        if word == "cd" and i + 1 < len(toks) and toks[i + 1] not in SEPARATORS:
            here = os.path.normpath(os.path.join(here, os.path.expanduser(toks[i + 1])))
        elif word in ("bash", "sh", "zsh") and depth < 2:
            for j in range(i + 1, len(toks) - 1):
                if toks[j] in SEPARATORS:
                    break
                if toks[j] == "-c" or re.fullmatch(r"-\w*c", toks[j]):
                    yield from invocations(toks[j + 1], here, depth + 1)
                    break
        elif os.path.basename(word) == "git":
            target, j = here, i + 1
            while j < len(toks) and toks[j].startswith("-"):
                if toks[j] == "-C" and j + 1 < len(toks):
                    target = os.path.normpath(os.path.join(target, os.path.expanduser(toks[j + 1])))
                    j += 2
                elif toks[j] in VALUED_GLOBALS and j + 1 < len(toks):
                    j += 2
                else:
                    j += 1
            if j < len(toks) and toks[j] not in SEPARATORS:
                end = j + 1
                while end < len(toks) and toks[end] not in SEPARATORS:
                    end += 1
                yield toks[j], target, toks[j + 1:end], toks[j + 1:end] + heredoc_body(toks, j + 1, end)
        i += 1


def heredoc_body(toks, lo, end):
    """Tokens of the heredoc(s) opened in toks[lo:end]: from the next newline to each delimiter."""
    delims = []
    for k in range(lo, end):
        m = re.fullmatch(r"<<-?(.*)", toks[k])
        if m and not toks[k].startswith("<<<"):
            d = m.group(1) or (toks[k + 1] if k + 1 < end else "")
            if d:
                delims.append(d)
    body, k = [], end
    while delims and k < len(toks) and toks[k] != "\n":
        k += 1
    for d in delims:
        line = []
        k += 1
        while k < len(toks):
            if toks[k] == "\n":
                if line == [d]:
                    break
                body += line
                line = []
            else:
                line.append(toks[k])
            k += 1
        else:
            body += line if line != [d] else []
    return body


def commit_message(args, target):
    """The message text git would use, or None when it cannot be seen from the command."""
    parts, seen = [], False
    k = 0
    while k < len(args):
        a = args[k]
        m = re.fullmatch(r"(-m|--message|-F|--file|--trailer)(?:=(.*))?|(-m|-F)(.+)", a)
        if m:
            flag = m.group(1) or m.group(3)
            val = m.group(2) if m.group(2) is not None else m.group(4)
            if val is None:
                val = args[k + 1] if k + 1 < len(args) else ""
                k += 1
            if flag in ("-F", "--file"):
                if val == "-":
                    return None
                try:
                    with open(os.path.join(target, val), encoding="utf-8", errors="replace") as fh:
                        val = fh.read()
                except OSError:
                    return None
            parts.append(val)
            seen = seen or flag != "--trailer"
        k += 1
    return "\n".join(parts) if seen else None


def gate_commit(cmd, cwd):
    for sub, target, args, tail in invocations(cmd, cwd):
        if sub != "commit":
            continue
        msg = commit_message(args, target)
        text = msg if msg is not None else " ".join(tail)
        if TRAILER.search(text):
            deny("Commit messages must not carry AI attribution trailers (Co-Authored-By / "
                 "Generated with ...). Remove the trailer and commit again. This overrides the "
                 "harness default that adds them. — .agents/hooks/git_gates.py commit, enforcing "
                 "git-workflow.md → Commits")


PUSH_VALUED = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}


def current_branch(target):
    p = subprocess.run(["git", "-C", target, "symbolic-ref", "-q", "--short", "HEAD"],
                       capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else ""


def pushes_protected(args, target):
    """True when this push's destination includes the PROTECTED branch."""
    positional, repo_given, k = [], False, 0
    while k < len(args):
        a = args[k]
        if a in ("--all", "--mirror"):
            return True
        if a in PUSH_VALUED:
            repo_given = repo_given or a == "--repo"
            k += 2
            continue
        if a.startswith("--repo="):
            repo_given = True
        elif not a.startswith("-") or a == "-":
            positional.append(a)
        k += 1
    refspecs = positional if repo_given else positional[1:]
    if not refspecs:
        refspecs = ["HEAD"]
    for spec in refspecs:
        spec = spec.lstrip("+")
        dst = spec.split(":", 1)[1] if ":" in spec else spec
        if dst == "HEAD":
            dst = current_branch(target)
        if dst.removeprefix("refs/heads/") == PROTECTED:
            return True
    return False


def gate_push(cmd, cwd):
    for sub, target, args, _ in invocations(cmd, cwd):
        if sub != "push":
            continue
        if pushes_protected(args, target):
            deny(f"This push to `{PROTECTED}` from {target} is refused: {PROTECTED} changes only "
                 f"through a PR. {PR_ROUTE}. — .agents/hooks/git_gates.py push, enforcing "
                 "git-workflow.md")
        git = ["git", "-C", target]
        if subprocess.run(git + ["rev-parse", "--git-dir"], capture_output=True).returncode:
            print(f"[pr-gate] {target} is not a git tree -- merge state NOT checked.", file=sys.stderr)
            continue
        if subprocess.run(git + ["remote", "get-url", "origin"], capture_output=True).returncode:
            print(f"[pr-gate] {target} has no `origin` remote -- merge state NOT checked before push "
                  "(git-workflow.md -> Remote).", file=sys.stderr)
            continue
        missing = []
        for base in BASES:
            try:
                fetched = subprocess.run(git + ["fetch", "origin", base, "-q"], capture_output=True,
                                         timeout=FETCH_TIMEOUT).returncode == 0
            except subprocess.TimeoutExpired:
                fetched = False
            if not fetched:
                print(f"[pr-gate] could not fetch origin/{base} in {target} -- that base NOT checked "
                      "before push.", file=sys.stderr)
                continue
            if subprocess.run(git + ["merge-base", "--is-ancestor", f"origin/{base}", "HEAD"],
                              capture_output=True).returncode:
                missing.append(base)
        if missing:
            names = " and ".join(f"origin/{b}" for b in missing)
            deny(f"{names} is not merged into {target}. Run `git fetch origin && git merge "
                 f"origin/{missing[0]}` there before pushing, and resolve conflicts locally rather "
                 "than at PR time. A web-UI PR passes no CLI gate, so push is where this is checked. "
                 "— .agents/hooks/git_gates.py push, enforcing git-workflow.md")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        cmd = (payload.get("tool_input") or {}).get("command")
    except Exception:  # noqa: BLE001 - unreadable payload is an environment failure: pass
        return
    if not isinstance(cmd, str) or "git" not in cmd:
        return
    cwd = payload.get("cwd") or os.getcwd()
    {"push": gate_push, "commit": gate_commit}.get(mode, lambda *_: None)(cmd, cwd)


if __name__ == "__main__":
    main()
