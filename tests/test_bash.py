"""Check Linux Bash startup in temporary homes without installing packages."""

import json
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import tempfile
import time
import tomllib
import unittest


SOURCE = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
CHEZMOI = shutil.which("chezmoi")


class BashTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dotfiles-bash-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = {
            "HOME": str(self.home), "PATH": f"{self.bin}:/usr/bin:/bin",
            "TERM": "xterm-256color", "LANG": "en_US.UTF-8",
        }

    def base(self, platform="linux"):
        return [
            CHEZMOI, "--source", str(SOURCE), "--destination", str(self.home),
            "--persistent-state", str(self.root / "state"), "--no-tty",
            "--override-data", json.dumps({"chezmoi": {
                "os": platform, "homeDir": str(self.home),
            }}),
        ]

    # Plugin clones need the network; these tests cover the rc files.
    def apply(self, platform="linux"):
        result = subprocess.run(
            self.base(platform) + ["apply", "--exclude=scripts,externals", "--force"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def interactive(self, script, profile=False):
        master, slave = pty.openpty()
        command = [BASH, "--noprofile"]
        if profile:
            command += ["--norc"]
            script = '. "$HOME/.bash_profile"; ' + script
        command += ["-i", "-c", script]
        process = subprocess.Popen(
            command, env=self.env, stdin=slave, stdout=slave, stderr=slave,
            start_new_session=True,
        )
        os.close(slave)
        output = bytearray()
        deadline = time.monotonic() + 20
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], 0.1)
                if ready:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output.extend(chunk)
                elif process.poll() is not None:
                    break
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
        finally:
            os.close(master)
        text = output.decode(errors="replace").replace("\r\n", "\n")
        self.assertEqual(process.returncode, 0, text)
        return text

    def stub(self, name, body="exit 0"):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def test_linux_uses_bash_and_omits_zsh(self):
        self.apply()
        self.assertTrue((self.home / ".bashrc").is_file())
        self.assertTrue((self.home / ".bash_profile").is_file())
        for name in [".zsh", ".zshrc", ".zshenv", ".zprofile", ".config/fsh"]:
            self.assertFalse((self.home / name).exists(), name)
        packages = tomllib.loads((SOURCE / ".chezmoidata/packages.toml").read_text())
        names = {p["name"] for p in packages["packages"]["linux"]["apt"]}
        self.assertTrue({"bash", "bash-completion"} <= names)
        self.assertNotIn("zsh", names)

    def test_macos_preserves_existing_bash_files(self):
        for name in [".bashrc", ".bash_profile"]:
            (self.home / name).write_text(f"# local Mac {name}\n")
        self.apply("darwin")
        for name in [".bashrc", ".bash_profile"]:
            self.assertEqual((self.home / name).read_text(), f"# local Mac {name}\n")

    def test_noninteractive_startup_is_silent_and_has_no_side_effects(self):
        self.apply()
        (self.home / ".bashrc.local").write_text("echo SHOULD_NOT_RUN\n")
        result = subprocess.run([
            BASH, "--noprofile", "--norc", "-c",
            'before=$PATH; . "$HOME/.bashrc"; '
            '[[ $PATH == "$before" && -z ${_CHEZMOI_BASHRC_LOADED:-} ]]',
        ], env=self.env, capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_interactive_defaults_local_override_and_path_reload(self):
        self.apply()
        (self.home / ".bashrc.local").write_text("alias gs='git status --short'\n")
        output = self.interactive(
            'first=$PATH; . "$HOME/.bashrc"; [[ $PATH == "$first" ]] || exit 1; '
            '[[ $HISTSIZE == 2000 && $HISTFILESIZE == 1000 && -o vi ]] || exit 2; '
            'shopt -q histappend checkwinsize || exit 3; alias gs; '
            'mkcd "$HOME/path with spaces" || exit 4; '
            '[[ $PWD == "$HOME/path with spaces" ]] || exit 5; printf "BASH_OK\\n"'
        )
        self.assertIn("alias gs='git status --short'", output)
        self.assertIn("BASH_OK", output)
        self.assertNotIn("command not found", output)

    def test_login_bridge_preserves_profile_and_loads_rc_once(self):
        original = 'export AUDIT_PROFILE=kept\n. "$HOME/.bashrc"\n'
        (self.home / ".bash_profile").write_text(original)
        (self.home / ".bashrc.local").write_text('AUDIT_RC_COUNT=$((${AUDIT_RC_COUNT:-0} + 1))\n')
        self.apply()
        first = (self.home / ".bash_profile").read_bytes()
        self.apply()
        self.assertEqual((self.home / ".bash_profile").read_bytes(), first)
        self.assertTrue(first.startswith(original.encode()))
        self.assertEqual(first.count(b"# >>> chezmoi Bash >>>"), 1)
        output = self.interactive(
            '[[ $AUDIT_PROFILE == kept && $AUDIT_RC_COUNT == 1 ]] || exit 1; printf "LOGIN_OK\\n"',
            profile=True,
        )
        self.assertIn("LOGIN_OK", output)

    def test_new_profile_keeps_previous_login_file_precedence(self):
        (self.home / ".profile").write_text('export AUDIT_PREVIOUS=profile\n. "$HOME/.bashrc"\n')
        self.apply()
        self.assertIn("FALLBACK_OK", self.interactive(
            '[[ $AUDIT_PREVIOUS == profile ]] || exit 1; printf "FALLBACK_OK\\n"', profile=True,
        ))
        (self.home / ".bash_login").write_text('export AUDIT_PREVIOUS=bash_login\n')
        self.assertIn("PRECEDENCE_OK", self.interactive(
            '[[ $AUDIT_PREVIOUS == bash_login && $_CHEZMOI_BASHRC_LOADED == $$ ]] || exit 1; '
            'printf "PRECEDENCE_OK\\n"', profile=True,
        ))

    def test_optional_tools_and_custom_conda_are_loaded(self):
        for name in ["batcat", "uv"]:
            self.stub(name)
        self.stub("fzf", "printf 'export AUDIT_FZF=loaded\\n'")
        conda = self.home / "custom-conda/etc/profile.d"
        conda.mkdir(parents=True)
        (conda / "conda.sh").write_text("export AUDIT_CONDA=loaded\n")
        (conda / "mamba.sh").write_text("export AUDIT_MAMBA=loaded\n")
        (self.home / "env.local.sh").write_text('export CONDA_HOME="$HOME/custom-conda"\n')
        self.apply()
        output = self.interactive(
            '[[ $AUDIT_FZF == loaded && $AUDIT_CONDA == loaded && $AUDIT_MAMBA == loaded ]] || exit 1; '
            'alias cat pip; printf "TOOLS_OK\\n"'
        )
        self.assertIn("alias cat='batcat --paging=never'", output)
        self.assertIn("alias pip='uv pip'", output)
        self.assertIn("TOOLS_OK", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
