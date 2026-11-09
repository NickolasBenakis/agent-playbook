"""Tests for the plugin install: manifests, hooks.json and its entry points. Run: python3 -m unittest discover tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(REPO, "hooks")
CONTEXT = os.path.join(HOOKS, "session-context.py")
ENTRY = os.path.join(HOOKS, "plugin_hook.py")


def run(script, args=(), payload=None, config=None, env=None):
    full_env = {k: v for k, v in os.environ.items() if k != "PLAYBOOK_PROFILE"}
    full_env.update({"CLAUDE_CONFIG_DIR": config or tempfile.mkdtemp(), **(env or {})})
    return subprocess.run([sys.executable, script, *args], input=json.dumps(payload or {}), capture_output=True,
                          text=True, timeout=60, env=full_env)


class Manifests(unittest.TestCase):
    def load(self, *parts):
        with open(os.path.join(REPO, *parts)) as f:
            return json.load(f)

    def test_versions_agree(self):
        plugin = self.load(".claude-plugin", "plugin.json")
        market = self.load(".claude-plugin", "marketplace.json")
        entry = next(p for p in market["plugins"] if p["name"] == plugin["name"])
        self.assertEqual(entry["version"], plugin["version"])
        self.assertEqual(entry["source"], "./")

    def test_changelog_has_current_version(self):
        version = self.load(".claude-plugin", "plugin.json")["version"]
        with open(os.path.join(REPO, "CHANGELOG.md")) as f:
            self.assertIn(f"## {version}", f.read())

    def test_hook_scripts_exist(self):
        hooks = self.load("hooks", "hooks.json")["hooks"]
        for groups in hooks.values():
            for group in groups:
                for hook in group["hooks"]:
                    for word in hook["command"].replace('"', " ").split():
                        if word.endswith(".py"):
                            name = os.path.basename(word)
                            self.assertTrue(os.path.exists(os.path.join(HOOKS, name)), name)

    def test_plugin_hooks_match_script_install(self):
        """hooks.json and settings.py must register the same guards on the same events."""
        def pairs(hooks):
            out = set()
            for event, groups in hooks.items():
                for group in groups:
                    for hook in group["hooks"]:
                        for word in hook["command"].replace('"', " ").split():
                            if word.endswith(".py") and not word.endswith(("plugin_hook.py", "session-context.py")):
                                args = hook["command"].split(word, 1)[1].replace('"', "").split()
                                out.add((event, group.get("matcher", ""), os.path.basename(word), tuple(args)))
            return out

        settings = os.path.join(tempfile.mkdtemp(), "settings.json")
        subprocess.run([sys.executable, os.path.join(HOOKS, "settings.py"), "install", REPO, settings], check=True,
                       capture_output=True)
        with open(settings) as f:
            script = json.load(f)["hooks"]
        self.assertEqual(pairs(self.load("hooks", "hooks.json")["hooks"]), pairs(script))


class EvalSuite(unittest.TestCase):
    def test_case_scaffolds_match_fixture(self):
        """The runner only runs files inside a case folder, so each case has a copy."""
        evals = os.path.join(REPO, "evals")

        def body(path):
            with open(path) as f:
                return [line for line in f if not line.startswith("MODE=")]

        fixture = body(os.path.join(evals, "fixture", "scaffold.sh"))
        with open(os.path.join(evals, "planted-injection", "scaffold.sh")) as f:
            self.assertIn('MODE="${1:-injection}"\n', f.read())
        cases = [d for d in os.listdir(evals) if os.path.exists(os.path.join(evals, d, "case.yaml"))]
        self.assertGreaterEqual(len(cases), 4)
        for case in cases:
            self.assertEqual(body(os.path.join(evals, case, "scaffold.sh")), fixture, case)

    def test_scaffold_builds_a_passing_repo(self):
        d = tempfile.mkdtemp()
        subprocess.run(["bash", os.path.join(REPO, "evals", "fixture", "scaffold.sh"), "injection"], cwd=d, check=True,
                       capture_output=True)
        out = subprocess.run([sys.executable, "-m", "unittest"], cwd=d, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        with open(os.path.join(d, "README.md")) as f:
            self.assertIn("Note for AI coding agents", f.read())


class SessionContext(unittest.TestCase):
    def test_loads_agents_md(self):
        out = run(CONTEXT)
        self.assertEqual(out.returncode, 0, out.stderr)
        ctx = json.loads(out.stdout)["hookSpecificOutput"]
        self.assertEqual(ctx["hookEventName"], "SessionStart")
        self.assertIn("# Agent Playbook", ctx["additionalContext"])

    def test_appends_profile(self):
        out = run(CONTEXT, env={"PLAYBOOK_PROFILE": "work"})
        self.assertIn("## Profile: work", json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"])

    def test_profile_name_cannot_escape(self):
        out = run(CONTEXT, env={"PLAYBOOK_PROFILE": "../CHANGELOG"})
        self.assertIn("# Agent Playbook", out.stdout)
        self.assertNotIn("# Changelog", out.stdout)

    def test_silent_when_script_install_imports_rules(self):
        config = tempfile.mkdtemp()
        with open(os.path.join(config, "CLAUDE.md"), "w") as f:
            f.write("# agent-playbook (managed by /x/install.sh)\n@/x/.generated/AGENTS.md\n")
        out = run(CONTEXT, config=config)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")


class PluginEntry(unittest.TestCase):
    def test_runs_the_named_hook(self):
        out = run(ENTRY, ["guard-git.py"], {"tool_name": "Bash", "tool_input": {"command": "git push --force"},
                                            "cwd": tempfile.mkdtemp()})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("permissionDecision", out.stdout)

    FORCE_PUSH = {"tool_name": "Bash", "tool_input": {"command": "git push --force"}}

    def config_with(self, settings):
        config = tempfile.mkdtemp()
        with open(os.path.join(config, "settings.json"), "w") as f:
            json.dump(settings, f)
        return config

    def test_skips_when_script_install_registers_the_same_hook(self):
        config = tempfile.mkdtemp()
        subprocess.run([sys.executable, os.path.join(HOOKS, "settings.py"), "install", REPO,
                        os.path.join(config, "settings.json")], check=True, capture_output=True)
        out = run(ENTRY, ["guard-git.py"], self.FORCE_PUSH, config=config)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")

    def test_runs_when_script_install_lacks_this_hook(self):
        """An older install.sh registered guard-git but not guard-secrets: keep the plugin's guard."""
        git_only = f'AGENT_PLAYBOOK_HOOK=1 python3 "{os.path.join(HOOKS, "guard-git.py")}"'
        config = self.config_with({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"command": git_only}]}]}})
        self.assertEqual(run(ENTRY, ["guard-git.py"], self.FORCE_PUSH, config=config).stdout.strip(), "")
        out = run(ENTRY, ["guard-secrets.py"], {"tool_name": "Bash", "tool_input": {"command": "printenv"},
                                                "cwd": tempfile.mkdtemp()}, config=config)
        self.assertIn("deny", out.stdout)

    def test_runs_when_script_install_points_at_a_deleted_clone(self):
        stale = 'AGENT_PLAYBOOK_HOOK=1 python3 "/nonexistent/agent-playbook/hooks/guard-git.py"'
        config = self.config_with({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"command": stale}]}]}})
        self.assertIn("permissionDecision", run(ENTRY, ["guard-git.py"], self.FORCE_PUSH, config=config).stdout)

    def test_tag_outside_hooks_does_not_disable_guards(self):
        config = self.config_with({"permissions": {"allow": ["Bash(AGENT_PLAYBOOK_HOOK=1 *)"]}})
        self.assertIn("permissionDecision", run(ENTRY, ["guard-git.py"], self.FORCE_PUSH, config=config).stdout)

    def test_refuses_unknown_scripts(self):
        for name in ("../install.sh", "settings.py", "session-context.py"):
            out = run(ENTRY, [name])
            self.assertEqual(out.returncode, 1, name)
            self.assertIn("unknown hook", out.stderr)


if __name__ == "__main__":
    unittest.main()
