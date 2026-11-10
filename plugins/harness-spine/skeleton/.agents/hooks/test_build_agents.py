#!/usr/bin/env python3
"""Tests for `.agents/hooks/build-agents.py`.

Run: python3 .agents/hooks/test_build_agents.py

Every test runs the script as a subprocess against a **copy** of the tree under `--root`, so a
failing test can never dirty the real `.claude/**` or `.codex/**`.

A freshly scaffolded project defines no dispatched lane (`.agents/agents/` is absent), so the lane
half of the generator is exercised with a FIXTURE source written into the copy. That keeps the
mechanism tested while the repo has nothing to feed it; the day a real lane lands, it is covered by
`test_committed_tree_is_already_the_build_output` with no change here.

The properties that matter, and what breaks if each is lost:

  round-trip    Building an unmodified tree must change nothing. If it does not hold, the
                PostToolUse hook rewrites files on every unrelated edit and the drift it is
                supposed to prevent shows up in every diff instead.
  --check       Must fail, and name the file, on a hand-edit of a generated file. The generated
                files are committed and therefore editable; without this, editing the artifact
                instead of the source is a silent no-op that survives review.
  no leak       Harness-only metadata (`model.codex`, `nickname_candidates` / `model.claude`)
                must stay on its own side, and the body must be identical in both outputs.
  skills        A skill source is copied to both harnesses; a `name:` that differs from its
                directory is refused (one skill, two names, no error from either harness).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, ".agents", "hooks", "build-agents.py")
COPIED = (".agents/agents", ".claude/agents", ".codex/agents",
          ".agents/skills", ".claude/skills", ".codex/skills")

NAME = "fixture-lane"
SRC = f".agents/agents/{NAME}.md"
CLAUDE_OUT = f".claude/agents/{NAME}.md"
CODEX_OUT = f".codex/agents/{NAME}.toml"
FIXTURE = (
    "---\n"
    f"name: {NAME}\n"
    "description: Test-only lane, not in the real tree — non-ASCII stays verbatim: é 한글.\n"
    "model.claude: opus\n"
    "model.codex: gpt-test\n"
    'nickname_candidates: ["fixture lane", "fixture"]\n'
    "---\n\n"
    "You review one module against the rules. Open the repo's own rules yourself.\n"
    'A body may contain """ triple quotes and a trailing quote"\n'
)
SKILL = "refactor-agent-rules"


def run(root, *args, stdin=None):
    return subprocess.run([sys.executable, SCRIPT, "--root", root, *args],
                          input=stdin, capture_output=True, text=True, encoding="utf-8")


def read(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8") as fh:
        return fh.read()


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def snapshot(root):
    out = {}
    for rel in COPIED:
        d = os.path.join(root, rel)
        for dirpath, _, files in os.walk(d):
            for f in sorted(files):
                p = os.path.join(dirpath, f)
                out[os.path.relpath(p, root)] = read(root, os.path.relpath(p, root))
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="build-agents-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for rel in COPIED:
            src = os.path.join(ROOT, rel)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(self.tmp, rel))


class CommittedTreeTest(Base):
    def test_committed_tree_is_already_the_build_output(self):
        """The files in git must equal what the sources generate -- no drift at rest."""
        r = run(self.tmp, "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("AGENTS_FRESH"), r.stdout)

    def test_build_of_a_clean_tree_changes_nothing(self):
        before = snapshot(self.tmp)
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(snapshot(self.tmp), before)
        self.assertIn("already current", r.stdout)

    def test_an_empty_tree_is_unknown_not_fresh(self):
        empty = tempfile.mkdtemp(prefix="build-agents-empty-")
        self.addCleanup(shutil.rmtree, empty, True)
        r = run(empty, "--check")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("AGENTS_UNKNOWN"), r.stdout)


class LaneTest(Base):
    def setUp(self):
        super().setUp()
        write(self.tmp, SRC, FIXTURE)
        r = run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_fixture_builds_both_outputs_and_checks_fresh(self):
        self.assertTrue(os.path.exists(os.path.join(self.tmp, CLAUDE_OUT)))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, CODEX_OUT)))
        self.assertEqual(run(self.tmp, "--check").returncode, 0)

    def test_build_is_idempotent_after_a_hand_edit_is_repaired(self):
        write(self.tmp, CLAUDE_OUT, "---\nname: wrong\n---\n\nclobbered\n")
        write(self.tmp, CODEX_OUT, 'name = "wrong"\n')
        self.assertEqual(run(self.tmp).returncode, 0)
        once = snapshot(self.tmp)
        self.assertEqual(run(self.tmp).returncode, 0)
        self.assertEqual(snapshot(self.tmp), once)
        self.assertEqual(run(self.tmp, "--check").returncode, 0)

    def test_source_edit_propagates_to_both_harnesses(self):
        write(self.tmp, SRC, read(self.tmp, SRC).replace("one module", "ONE MODULE"))
        self.assertEqual(run(self.tmp, "--check").returncode, 1)
        self.assertEqual(run(self.tmp).returncode, 0)
        self.assertIn("ONE MODULE", read(self.tmp, CLAUDE_OUT))
        self.assertIn("ONE MODULE", read(self.tmp, CODEX_OUT))

    def test_check_catches_hand_edit_of_claude_output(self):
        write(self.tmp, CLAUDE_OUT, read(self.tmp, CLAUDE_OUT) + "\nhand-edited\n")
        r = run(self.tmp, "--check")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("AGENTS_STALE"), r.stdout)
        self.assertIn(CLAUDE_OUT, r.stdout)
        self.assertIn("hand-edited", r.stdout)  # the diff is shown, not just the verdict

    def test_check_catches_hand_edit_of_codex_output(self):
        write(self.tmp, CODEX_OUT, read(self.tmp, CODEX_OUT).replace("fixture lane", "nope"))
        r = run(self.tmp, "--check")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(CODEX_OUT, r.stdout)

    def test_check_catches_a_deleted_generated_file(self):
        os.remove(os.path.join(self.tmp, CODEX_OUT))
        r = run(self.tmp, "--check")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(CODEX_OUT, r.stdout)

    def test_check_writes_nothing(self):
        write(self.tmp, CLAUDE_OUT, "clobbered\n")
        before = snapshot(self.tmp)
        run(self.tmp, "--check")
        self.assertEqual(snapshot(self.tmp), before)

    def test_codex_only_metadata_absent_from_claude_output(self):
        out = read(self.tmp, CLAUDE_OUT)
        for key in ("nickname_candidates", "model.codex", "gpt-test"):
            self.assertNotIn(key, out)
        self.assertIn("model: opus", out)

    def test_claude_only_metadata_absent_from_codex_output(self):
        out = read(self.tmp, CODEX_OUT)
        self.assertNotIn("opus", out)
        self.assertIn('model = "gpt-test"', out)

    def test_body_is_identical_in_both_outputs(self):
        import tomllib
        claude = read(self.tmp, CLAUDE_OUT).split("---", 2)[2].strip()
        codex = tomllib.loads(read(self.tmp, CODEX_OUT))["developer_instructions"].strip()
        self.assertEqual(claude, codex)

    def test_generated_codex_toml_parses(self):
        import tomllib
        data = tomllib.loads(read(self.tmp, CODEX_OUT))
        self.assertEqual(data["name"], NAME)
        self.assertEqual(data["nickname_candidates"], ["fixture lane", "fixture"])
        self.assertTrue(data["description"])
        self.assertIn('"""', data["developer_instructions"])

    def test_unknown_source_frontmatter_key_is_a_loud_error(self):
        write(self.tmp, SRC, FIXTURE.replace("model.claude: opus", "model.claude: opus\ntools: Read"))
        before = snapshot(self.tmp)
        r = run(self.tmp)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("AGENTS_UNKNOWN"), r.stdout)
        self.assertEqual(snapshot(self.tmp), before)

    def test_hook_rebuilds_only_for_a_source_edit(self):
        write(self.tmp, CLAUDE_OUT, "clobbered\n")
        for payload, expect_rebuild in (
            ('{"tool_input": {"file_path": "/x/some-other-repo/CLAUDE.md"}}', False),
            (json.dumps({"tool_input": {"file_path": f"/x/{SRC}"}}), True),
        ):
            r = run(self.tmp, "--hook", stdin=payload)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(read(self.tmp, CLAUDE_OUT) != "clobbered\n", expect_rebuild, payload)

    def test_hook_rebuilds_for_codex_apply_patch(self):
        write(self.tmp, CLAUDE_OUT, "clobbered\n")
        payload = json.dumps({"tool_input": {"command": (
            f"*** Begin Patch\n*** Update File: {SRC}\n*** End Patch")}})
        r = run(self.tmp, "--hook", stdin=payload)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotEqual(read(self.tmp, CLAUDE_OUT), "clobbered\n")

    def test_hook_survives_junk_stdin(self):
        r = run(self.tmp, "--hook", stdin="not json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class ScopeTest(Base):
    def test_only_agents_and_skills_are_sources(self):
        """`.agents/hooks/` and `.agents/rules/` sit beside the sources and must generate nothing."""
        write(self.tmp, ".agents/hooks/notes.md", "---\nname: notes\ndescription: x\n---\nbody\n")
        write(self.tmp, ".agents/rules/some-rule.md", "# rule\n")
        r = run(self.tmp, "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, ".claude/agents/notes.md")))
        r = run(self.tmp, "--hook", stdin=json.dumps(
            {"tool_input": {"file_path": "/x/.agents/hooks/notes.md"}}))
        self.assertEqual(r.returncode, 0)
        self.assertEqual(run(self.tmp, "--check").returncode, 0)


class SkillTest(Base):
    def test_skill_is_copied_to_both_harnesses(self):
        src = read(self.tmp, f".agents/skills/{SKILL}/SKILL.md")
        for target in (".claude/skills", ".codex/skills"):
            self.assertEqual(read(self.tmp, f"{target}/{SKILL}/SKILL.md"), src)

    def test_hand_edited_skill_copy_is_stale(self):
        rel = f".codex/skills/{SKILL}/SKILL.md"
        write(self.tmp, rel, read(self.tmp, rel) + "\nedited\n")
        r = run(self.tmp, "--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(rel, r.stdout)

    def test_name_directory_mismatch_is_refused(self):
        rel = f".agents/skills/{SKILL}/SKILL.md"
        write(self.tmp, rel, read(self.tmp, rel).replace(f"name: {SKILL}", "name: other-name", 1))
        r = run(self.tmp, "--check")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("one skill, two names", r.stdout)

    def test_orphaned_skill_copy_is_stale(self):
        write(self.tmp, ".claude/skills/renamed-away/SKILL.md", "---\nname: renamed-away\n---\nx\n")
        r = run(self.tmp, "--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(".claude/skills/renamed-away/", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
