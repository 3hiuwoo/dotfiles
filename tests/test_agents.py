"""Exercise agent deployment and state preservation in isolated homes."""

import json
import os
import sys
import tomllib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]
CHEZMOI = shutil.which("chezmoi")


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dotfiles-agents-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.source = self.root / "source"
        self.source.mkdir()
        for name in ["dot_agents", "private_dot_claude", "private_dot_codex",
                     ".chezmoitemplates", ".chezmoidata"]:
            shutil.copytree(SOURCE / name, self.source / name)
        shutil.copytree(SOURCE / "dot_config/ccstatusline",
                        self.source / "dot_config/ccstatusline")
        for name in [".chezmoiignore", "run_after_install-agent-skills.sh.tmpl"]:
            shutil.copy2(SOURCE / name, self.source / name)

        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls"
        self.env = dict(os.environ, HOME=str(self.home),
                        PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        SKILL_TEST_LOG=str(self.log))
        fake_npx = self.bin / "npx"
        fake_npx.write_text("#!" + sys.executable + "\n" + r'''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ["SKILL_TEST_LOG"], "a") as log:
    log.write(json.dumps(args) + "\n")
if os.environ.get("SKILL_TEST_FAIL"):
    sys.exit(1)
assert args[:3] == ["--yes", "skills@latest", "add"]
assert args[4:7] == ["--global", "--agent", "claude-code"]
source = args[3]
names = args[args.index("--skill") + 1:-1]
assert args[-1] == "--yes"
home = Path.home()
lock_path = home / ".agents/.skill-lock.json"
lock = json.loads(lock_path.read_text()) if lock_path.exists() else {"version": 3, "skills": {}}
for name in names:
    target = home / ".agents/skills" / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text("installed " + name + "\n")
    lock["skills"][name] = {"source": source, "skillFolderHash": "installed"}
lock_path.write_text(json.dumps(lock))
''')
        fake_npx.chmod(0o755)
        fake_hf = self.bin / "hf"
        fake_hf.write_text("#!" + sys.executable + "\n" + r'''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ["SKILL_TEST_LOG"], "a") as log:
    log.write(json.dumps(["hf"] + args) + "\n")
assert args[:2] == ["skills", "add"] and args[3:] == ["--global"], args
target = Path.home() / ".agents/skills" / args[2]
target.mkdir(parents=True, exist_ok=True)
(target / "SKILL.md").write_text("hf skill\n")
(target / ".hf-skill-manifest.json").write_text("")
''')
        fake_hf.chmod(0o755)

    def base(self, platform="darwin"):
        return [
            CHEZMOI, "--source", str(self.source), "--destination", str(self.home),
            "--persistent-state", str(self.root / "state"), "--no-tty",
            "--override-data", json.dumps({"chezmoi": {
                "os": platform, "homeDir": str(self.home),
            }}),
        ]

    def apply(self, platform="darwin", success=True, install=False):
        options = ["apply", "--force"]
        if not install:
            options.append("--exclude=scripts")
        result = subprocess.run(
            self.base(platform) + options, env=self.env,
            capture_output=True, text=True, timeout=30,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def write_json(self, relative, value):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=4) + "\n")
        return path

    def read_json(self, relative):
        return json.loads((self.home / relative).read_text())

    def test_fresh_mac_has_shared_skills_and_no_runtime_state(self):
        self.apply(install=True)
        skills = list((self.home / ".agents/skills").iterdir())
        self.assertEqual(len(skills), 54)
        for skill in skills:
            link = self.home / ".claude/skills" / skill.name
            self.assertTrue(link.is_symlink())
            self.assertFalse(link.readlink().is_absolute())
            self.assertEqual(link.resolve(), skill.resolve())
            self.assertTrue((link / "SKILL.md").is_file())
        for name in [".claude/CLAUDE.md", ".codex/AGENTS.md"]:
            self.assertEqual((self.home / name).resolve(),
                             self.home / ".agents/AGENTS.md")
        self.assertFalse((self.home / ".claude.json").exists())
        self.assertEqual(self.read_json(".claude/settings.json")["env"]["TZ"],
                         "America/New_York")
        self.assertTrue((self.home / ".config/ccstatusline/settings.json").is_file())
        self.assertEqual((self.home / ".claude/settings.json").stat().st_mode & 0o777, 0o600)
        for name in [".mcp.json", ".claude/mcp.json", ".codex/config.toml",
                     ".codex/auth.json", ".claude/plugins", ".claude/skills/synced"]:
            self.assertFalse((self.home / name).exists(), name)

    def test_repo_skills_come_from_github_and_hf_skills_from_hf(self):
        self.apply(install=True)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        miaa = [c for c in calls if "3hiuwoo/miaa-bibtex" in c]
        self.assertEqual(len(miaa), 1)
        self.assertEqual(len(miaa[0][miaa[0].index("--skill") + 1:-1]), 13)
        hf = sorted(c[3] for c in calls if c[0] == "hf")
        self.assertEqual(hf, ["hf-cli", "huggingface-papers"])
        lock = self.read_json(".agents/.skill-lock.json")["skills"]
        self.assertNotIn("hf-cli", lock)
        managed = subprocess.check_output(self.base() + ["managed"], text=True)
        self.assertNotIn("miaa-bibtex", managed)

    def test_local_checkout_symlinks_are_left_alone(self):
        checkout = self.home / "miaa-bibtex/skills/miaa-bibtex-core"
        checkout.mkdir(parents=True)
        (checkout / "SKILL.md").write_text("local repo skill\n")
        link = self.home / ".agents/skills/miaa-bibtex-core"
        link.parent.mkdir(parents=True)
        link.symlink_to("../../miaa-bibtex/skills/miaa-bibtex-core")
        self.apply(install=True)
        self.assertTrue(link.is_symlink())
        self.assertEqual((link / "SKILL.md").read_text(), "local repo skill\n")
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        miaa = next(c for c in calls if "3hiuwoo/miaa-bibtex" in c)
        self.assertNotIn("miaa-bibtex-core", miaa)
        self.assertEqual((self.home / ".claude/skills/miaa-bibtex-core").resolve(),
                         checkout)

    def test_linux_preserves_local_agents_without_deploying_any(self):
        local = self.write_json(".claude/settings.json", {"local": True})
        before = local.read_bytes()
        self.apply("linux", install=True)
        self.assertEqual(local.read_bytes(), before)
        for name in [".agents", ".codex", ".claude.json", ".claude/skills",
                     ".config/ccstatusline"]:
            self.assertFalse((self.home / name).exists(), name)

    def test_settings_merge_preserves_secrets_and_local_state_idempotently(self):
        self.write_json(".claude/settings.json", {
            "env": {"ANTHROPIC_AUTH_TOKEN": "test-only-token",
                    "ANTHROPIC_BASE_URL": "http://localhost:9999", "TZ": "bad"},
            "enabledPlugins": {"local-only@local": True},
            "machinePreference": {"keep": True},
        })
        state = self.write_json(".claude.json", {
            "userID": "test-account", "projects": {"/local/project": {"trusted": True}},
            "mcpServers": {"local": {"type": "http", "url": "http://localhost"}},
        })
        original_state = state.read_bytes()
        extra = self.home / ".claude/skills/synced/keep/SKILL.md"
        extra.parent.mkdir(parents=True)
        extra.write_text("cloud skill\n")
        self.apply()
        settings = self.read_json(".claude/settings.json")
        self.assertEqual(settings["env"]["ANTHROPIC_AUTH_TOKEN"], "test-only-token")
        self.assertEqual(settings["env"]["ANTHROPIC_BASE_URL"], "http://localhost:9999")
        self.assertTrue(settings["enabledPlugins"]["local-only@local"])
        self.assertEqual(settings["machinePreference"], {"keep": True})
        self.assertEqual(state.read_bytes(), original_state)
        first = (self.home / ".claude/settings.json").read_bytes()
        self.apply()
        self.assertEqual((self.home / ".claude/settings.json").read_bytes(), first)
        self.assertEqual(state.read_bytes(), original_state)
        self.assertEqual(extra.read_text(), "cloud skill\n")

    def test_invalid_existing_settings_are_not_overwritten(self):
        path = self.home / ".claude/settings.json"
        path.parent.mkdir()
        original = '{"unfinished": '
        path.write_text(original)
        self.apply(success=False)
        self.assertEqual(path.read_text(), original)

    def test_skill_updates_and_registry_are_never_rolled_back(self):
        self.apply(install=True)
        path = self.home / ".agents/skills/agent-browser/SKILL.md"
        path.write_text("UPDATED upstream skill\n")
        lock = self.read_json(".agents/.skill-lock.json")
        lock["skills"]["agent-browser"]["skillFolderHash"] = "UPDATED"
        lock["dismissed"] = {"prompt": True}
        lock_path = self.write_json(".agents/.skill-lock.json", lock)
        original = lock_path.read_bytes()
        calls = self.log.read_bytes()
        extra = self.home / ".agents/skills/extra/SKILL.md"
        extra.parent.mkdir()
        extra.write_text("extra skill\n")
        self.apply(install=True)
        self.assertEqual(path.read_text(), "UPDATED upstream skill\n")
        self.assertEqual(lock_path.read_bytes(), original)
        self.assertEqual(self.log.read_bytes(), calls)
        self.assertEqual((self.home / ".claude/skills/extra").resolve(), extra.parent)
        managed = subprocess.check_output(self.base() + ["managed"], text=True)
        self.assertNotIn(".agents/.skill-lock.json", managed)
        self.assertNotIn(".agents/skills/agent-browser", managed)
        self.assertNotIn(".claude/skills/", managed)

    def test_missing_skill_is_restored_without_reinstalling_others(self):
        self.apply(install=True)
        path = self.home / ".agents/skills/exa-search/SKILL.md"
        path.unlink()
        self.log.write_text("")
        self.apply(install=True)
        self.assertTrue(path.is_file())
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][calls[0].index("--skill") + 1:-1], ["exa-search"])

    def test_failed_install_can_be_retried(self):
        self.env["SKILL_TEST_FAIL"] = "1"
        self.apply(install=True, success=False)
        del self.env["SKILL_TEST_FAIL"]
        self.apply(install=True)
        self.assertEqual(len(list((self.home / ".agents/skills").iterdir())), 54)

    def test_conflicting_claude_skill_is_preserved_before_install(self):
        path = self.home / ".claude/skills/agent-browser/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("custom Claude skill\n")
        self.apply(install=True, success=False)
        self.assertEqual(path.read_text(), "custom Claude skill\n")
        self.assertFalse(self.log.exists())

    def test_corrupt_or_conflicting_registry_is_not_rewritten(self):
        path = self.write_json(".agents/.skill-lock.json", {"skills": {
            "agent-browser": {"source": "another/repository"},
        }})
        original = path.read_bytes()
        self.apply(install=True, success=False)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse(self.log.exists())
        path.write_text("{invalid")
        self.apply(install=True, success=False)
        self.assertEqual(path.read_text(), "{invalid")
        self.assertFalse(self.log.exists())

    def test_source_manifest_uses_safe_names_and_no_version_pins(self):
        data = tomllib.loads((self.source / ".chezmoidata/agent-skills.toml").read_text())
        names = []
        for source in data["agent_skills"]["sources"]:
            self.assertEqual(set(source), {"source", "skills"})
            self.assertRegex(source["source"], r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$")
            for name in source["skills"]:
                self.assertRegex(name, r"^[a-zA-Z0-9_-]+$")
                names.append(name)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(names), 52)
        self.assertEqual(data["agent_skills"]["hf"], {"skills": ["hf-cli", "huggingface-papers"]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
