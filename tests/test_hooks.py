"""Tests for the playbook's hooks and helpers. Run: python3 -m unittest discover tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(REPO, "hooks", "guard-git.py")
STOP = os.path.join(REPO, "hooks", "stop-check.py")
SETTINGS = os.path.join(REPO, "hooks", "settings.py")
SUMMARIZE = os.path.join(REPO, "skills", "audit", "summarize.py")


def run(script, payload):
    out = subprocess.run([sys.executable, script], input=json.dumps(payload), capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout) if out.stdout.strip() else None


def git_repo(branch):
    d = tempfile.mkdtemp()
    for args in (["init", "-q", "-b", branch], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"],
                 ["commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run(["git", "-C", d, *args], check=True, capture_output=True)
    return d


class GuardGit(unittest.TestCase):
    def decision(self, command, cwd):
        out = run(GUARD, {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd})
        return out and out["hookSpecificOutput"]["permissionDecision"]

    def test_asks_for_risky_commands(self):
        feature, main = git_repo("feature"), git_repo("main")
        for cmd, cwd in [
            ("git push origin main", feature),
            ("git push origin HEAD:main", feature),
            ("git push origin feature:refs/heads/master", feature),
            ("git push", main),
            ("git push -u origin", main),
            ("git push --force origin feature", feature),
            ("git push -uf origin feature", feature),
            ("git push origin +feature", feature),
            ("git push origin --delete main", feature),
            ("git push --mirror origin", feature),
            ("npm test && git push origin main", feature),
            (f"git -C {main} push", feature),
            (f"cd {main} && git push", feature),
            ('bash -c "git push origin main"', feature),
            ("sudo git push origin main", feature),
            ("timeout 60 git push origin main", feature),
            ("FOO=1 env BAR=2 git push origin main", feature),
            ("gh pr merge 12 --squash", feature),
            ("gh -R owner/repo pr merge 12", feature),
        ]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.decision(cmd, cwd), "ask")

    def test_allows_normal_commands(self):
        feature, main = git_repo("feature"), git_repo("main")
        for cmd, cwd in [
            ("git push -u origin feature", feature),
            ("git push", feature),
            ("git push --force-with-lease origin feature", feature),
            (f"cd {feature} && git push", main),
            ("git status", feature),
            ("echo push main", feature),
            ("gh pr create --title x --body y", feature),
            ("git log --grep 'push origin main'", feature),
            ("git merge main", feature),
        ]:
            with self.subTest(cmd=cmd):
                self.assertIsNone(self.decision(cmd, cwd))

    def test_never_crashes_on_odd_input(self):
        for payload in ([1], "x", {"tool_input": "x"}, {"tool_input": {"command": 5}}, {}):
            with self.subTest(payload=payload):
                self.assertIsNone(run(GUARD, payload))


class StopCheck(unittest.TestCase):
    def hook(self, repo, *args, session="s1"):
        out = subprocess.run([sys.executable, STOP, *args], input=json.dumps({"session_id": session, "cwd": repo}),
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else None

    def opted_in(self, check):
        repo = git_repo("main")
        subprocess.run(["git", "-C", repo, "config", "playbook.check", check], check=True)
        return repo

    def write(self, repo, name, text):
        with open(os.path.join(repo, name), "w") as f:
            f.write(text)

    def test_skips_repos_without_a_check_and_ignores_files_in_the_repo(self):
        repo = git_repo("main")
        self.write(repo, ".agent-check", "false")
        self.write(repo, "x.txt", "changed")
        self.assertIsNone(self.hook(repo))
        self.assertIsNone(self.hook(tempfile.mkdtemp()))
        self.assertIsNone(run(STOP, [1]))

    def test_only_checks_turns_that_changed_files(self):
        repo = self.opted_in("false")
        self.write(repo, "x.txt", "human's red work")
        self.hook(repo, "--baseline")
        self.assertIsNone(self.hook(repo))  # nothing changed this turn: Q&A is not blocked

    def test_blocks_until_the_check_passes_including_untracked_edits(self):
        repo = self.opted_in("grep -q good new.txt")
        self.hook(repo, "--baseline")
        self.write(repo, "new.txt", "bad")
        out = self.hook(repo)
        self.assertEqual(out["decision"], "block")
        self.assertIn("attempt 1 of 3", out["reason"])
        self.write(repo, "new.txt", "good")
        self.assertIsNone(self.hook(repo))
        self.write(repo, "new.txt", "bad again")  # untracked content change must be seen
        self.assertEqual(self.hook(repo)["decision"], "block")

    def test_gives_up_after_three_attempts_and_resets_next_turn(self):
        repo = self.opted_in("false")
        self.hook(repo, "--baseline")
        self.write(repo, "x.txt", "1")
        self.assertEqual(self.hook(repo)["decision"], "block")
        self.assertEqual(self.hook(repo)["decision"], "block")
        self.assertIn("systemMessage", self.hook(repo))
        self.hook(repo, "--baseline")
        self.write(repo, "x.txt", "2")
        self.assertEqual(self.hook(repo)["decision"], "block")


class Settings(unittest.TestCase):
    def install(self, action, repo, path):
        subprocess.run([sys.executable, SETTINGS, action, repo, path], check=True, capture_output=True)

    def test_install_is_idempotent_and_uninstall_keeps_other_settings(self):
        d = tempfile.mkdtemp()
        real, link = os.path.join(d, "real.json"), os.path.join(d, "settings.json")
        other = {"matcher": "Write", "hooks": [{"type": "command", "command": "prettier"}]}
        with open(real, "w") as f:
            json.dump({"theme": "dark", "hooks": {"PreToolUse": [other]}}, f)
        os.symlink(real, link)
        self.install("install", REPO, link)
        self.install("install", "/moved/agent-playbook", link)  # repo moved: replaced, not duplicated
        self.assertTrue(os.path.islink(link))
        with open(real) as f:
            s = json.load(f)
        self.assertEqual(len(s["hooks"]["PreToolUse"]), 2)
        self.assertIn("/moved/agent-playbook/hooks/guard-git.py", s["hooks"]["PreToolUse"][1]["hooks"][0]["command"])
        for event in ("Stop", "SessionStart", "UserPromptSubmit"):
            self.assertEqual(len(s["hooks"][event]), 1)
        self.install("uninstall", REPO, link)
        with open(real) as f:
            self.assertEqual(json.load(f), {"theme": "dark", "hooks": {"PreToolUse": [other]}})

    def test_uninstall_without_settings_creates_nothing(self):
        path = os.path.join(tempfile.mkdtemp(), "settings.json")
        self.install("uninstall", REPO, path)
        self.assertFalse(os.path.exists(path))


class Summarize(unittest.TestCase):
    def test_counts_tools_tokens_and_loops(self):
        lines = [
            {"type": "user", "timestamp": "2026-11-05T10:00:00Z", "message": {"content": "do it"}},
            *[{"type": "assistant", "timestamp": f"2026-11-05T10:0{i}:00Z", "requestId": f"r{i}",
               "message": {"usage": {"input_tokens": 10, "output_tokens": 5},
                           "content": [{"type": "tool_use", "id": f"t{i}", "name": "Bash", "input": {"command": "npm test"}}]}}
              for i in range(3)],
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t2", "is_error": True, "content": "boom"}]}},
        ]
        path = os.path.join(tempfile.mkdtemp(), "s.jsonl")
        with open(path, "w") as f:
            f.write("\n".join(json.dumps(l) for l in lines))
        out = subprocess.run([sys.executable, SUMMARIZE, path], capture_output=True, text=True, check=True).stdout
        self.assertIn("wall clock: 2 min", out)
        self.assertIn("30 new input", out)
        self.assertIn("Bash 3", out)
        self.assertIn("3x npm test", out)
        self.assertIn("Bash: boom", out)


if __name__ == "__main__":
    unittest.main()
