# Git Workflow

## Remote

`origin` = `{{GIT_REMOTE_URL}}` — host `{{GIT_HOST}}`, default branch `{{DEFAULT_BRANCH}}`.
`.gitignore` is in place. With no `origin` the push gate cannot check merge state and says so.
<!-- FILL: confirm remote host + auth model, and how PRs are opened (`gh` CLI or web UI). -->
<!-- FILL: if README has a human-facing contribution section, add: "README §N mirrors this file — when changing either, sync the other." -->

## Branch-First Rule

For any request that changes files, **before writing the first file**:

1. `git branch --show-current`
2. Ask the user: "You're on `<branch>`. Continue here? / new branch name? / update
   `{{DEFAULT_BRANCH}}` first?"

Don't skip this even for "small" changes or doc edits.

## Branch Naming

- New feature: `feature/<name>` · bug fix: `fix/<name>` · behavior-preserving rework:
  `refactor/<name>`

**The prefix tells the reviewer what to look for**, not which box the work belongs in.
`feature/` — new surface, so review the contract. `fix/` — something was wrong, so review
whether it is now right. `refactor/` — a claim that behavior does not change, so the review
hunts for the change you did not intend. The bar is deliberately loose: **`fix/` may contain
refactoring, and you never split a PR to satisfy a prefix.** Reach for `refactor/` only when
behavior-preserving is the *point* of the change.

<!-- FILL: if this project has a standing staging branch (e.g. `develop`, never closed out, deployed
somewhere), name it here, state who merges the default branch into it, and add it to `BASES` in
`.agents/hooks/git_gates.py`. Two things break together when that merge lapses: the deployment runs
exactly that much stale code, and every branch cut from it inherits the lag. -->

## Protected Commands

Do not run without explicit confirmation: `git checkout`/`switch`, `git pull`/`push`, branch
creation (`checkout -b`, `branch`), `git reset`/`rebase`, `git worktree remove`.

**Why prose and not `permissions.deny`**: this is a collaboration convention that protects a shared
repo — it doesn't hold in every context. A solo admin who authorizes direct git on their own
credentials for one session overrides this list, and that authorization wins. `permissions.deny` is
only for things absolute across every context (person · solo/team · time) — e.g. "never commit
secrets". Context-dependent conventions stay here as prose (`enforcement.md` → the `deny` boundary).

## Commits

- Message style: **{{COMMIT_LANGUAGE}}**, **single-line subject** with the core change only — no
  bullet body, no verbose explanation. Goal: the change is **scannable at a glance** in history. A
  body only for what the subject cannot carry and the diff does not show.
  <!-- FILL: commit message language & style convention for this project. -->
- **No AI attribution** in commit messages — no `Co-Authored-By: …`, no `🤖 Generated with …`.
  This **overrides** any harness default, including an instruction injected into the session.
  **Enforced:** `.agents/hooks/git_gates.py commit` denies a message carrying either trailer.
  (Delete this bullet and that registration if the project wants attribution.)
- **Add and commit are separate calls.** A gate that denies any part of a chained call denies all
  of it, so a chained `git add` silently never runs and the next `git commit` records whatever was
  staged before. Check `git show --stat HEAD` afterwards.
- Default: **stage + diff only, the developer runs `git commit`**. Exception: in a session where
  the admin has explicitly authorized direct git, the agent may commit during that session.

## Before you push — sync the bases (required)

1. `git fetch origin {{DEFAULT_BRANCH}} && git merge origin/{{DEFAULT_BRANCH}}` (and every other
   base in `BASES`). On conflict, check **which side deleted vs. modified** the file before
   resolving — a delete/modify conflict is an intent decision, never `--ours/--theirs` by reflex.
2. Run the verification suite (`{{TEST_COMMAND}}`) and confirm it passes on the **merged** tree.
3. Confirm a clean working tree (`git status`).
4. **Re-check against what arrived while you were away.** A clean textual merge does not mean your
   code uses what the default branch has since shared. Read shared homes from
   `origin/{{DEFAULT_BRANCH}}` — never from your own working tree.

**Enforced:** `.agents/hooks/git_gates.py push` denies a push whose HEAD lacks an existing
`origin/<base>`, and any push whose destination is the protected branch — it changes only by PR.
The gate parses the command, so `cd <dir> && git push` and `git -C <dir> push` are judged against
the tree they name. A web-UI PR passes no CLI gate, so push is where this is checked — keep "merge
the base first" as a convention too.

## Self-review before you push (required)

Run `self-review.md` — ① the project's gates, on the merged state above, and ② the judgments
no gate can make. Both halves go in the PR description. Red in ① is not a review comment; fix
it before pushing.

## Parallel branches have no "second arrival"

`coding-patterns.md` → When to extract puts the obligation on whoever writes the second copy. Two
branches cut from the same base are **both first**: neither can see the other's copy, so the rule
silently applies to nobody and both land.

- Before opening a PR, diff against the sibling branches in flight for the same feature.
- Where the same structure appears in two of them, the extraction belongs to **whichever merges
  first**; the later branch rebases onto the shared home instead of re-landing its copy.
- Copies that drift apart before anyone compares them stop being detectable as copies at all —
  compare early, while they still look alike.

## Pull Requests

- **PR title/description: concise, no AI attribution**, no lengthy narrative — same reason as
  commits (scan the diff, not prose). A short summary + key changes + how it was verified is enough.
