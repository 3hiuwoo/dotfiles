"""Exercise rendered installers with fake package managers; never install tools.

Run with: uv run --no-project --python 3.12 python tests/test_provisioning.py
Requires chezmoi, Python 3.11+, and a POSIX shell.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest


SOURCE = Path(__file__).resolve().parents[1]
CHEZMOI = shutil.which("chezmoi")


class ProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dotfiles-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls"
        self.env = {
            "HOME": str(self.home),
            "PATH": str(self.bin),
            "AUDIT_LOG": str(self.log),
            "AUDIT_UID": "0",
            "AUDIT_CERT_INSTALLED": "1",
            "AUDIT_BREW_EXIT": "0",
            "AUDIT_GROUPS": "users",
            "AUDIT_SUDO_NOPASS": "1",
            "AUDIT_APT_MISSING": "",
        }
        self.stub("brew", '''case "$1" in
shellenv) exit 0 ;;
bundle) printf 'brew %s\\n' "$*" >> "$AUDIT_LOG"
        /bin/cat >> "$AUDIT_LOG"
        exit "$AUDIT_BREW_EXIT" ;;
*) exit 99 ;;
esac''')
        self.stub("id", '''case "$1" in
-u) printf "%s\n" "$AUDIT_UID" ;;
-Gn) printf "%s\n" "$AUDIT_GROUPS" ;;
*) exit 1 ;;
esac''')
        self.stub("dpkg-query", '''if [ "$AUDIT_CERT_INSTALLED" = 1 ]; then
printf 'install ok installed'
else
exit 1
fi''')
        self.stub("apt-get", 'printf "apt-get %s\\n" "$*" >> "$AUDIT_LOG"')
        self.stub("apt-cache", '''for p in $AUDIT_APT_MISSING; do [ "$3" = "$p" ] && exit 100; done
exit 0''')
        self.stub("sudo", '''if [ "$1" = -n ]; then [ "$AUDIT_SUDO_NOPASS" = 1 ] || exit 1; shift; fi
[ "$1" = -v ] && exit 1
printf "sudo %s\n" "$*" >> "$AUDIT_LOG"; "$@"''')
        # Official installers are downloaded by curl and run through env.
        self.stub("curl", '''while [ $# -gt 0 ]; do
case "$1" in
--output) out=$2; shift ;;
http*) url=$1 ;;
esac
shift
done
printf "curl %s\n" "$url" >> "$AUDIT_LOG"
[ "${AUDIT_CURL_FAIL:-}" = "$url" ] && exit 22
printf 'echo "installer ran: SHELL=$SHELL $*" >> "$AUDIT_LOG"\n' > "$out"''')
        for name in ["mktemp", "rm", "cat", "sh", "bash"]:
            (self.bin / name).symlink_to(shutil.which(name))
        (self.bin / "env").symlink_to("/usr/bin/env")
        self.setUp_node()

    scripts = []
    # node/npm/npx present by default so the nvm path is only exercised on purpose.
    def setUp_node(self):
        for name in ["node", "npm", "npx"]:
            self.stub(name)

    def stub(self, name, body="exit 0", directory=None):
        path = (directory or self.bin) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)
        return path

    def base(self, platform, packages):
        kind = "brews" if platform == "darwin" else "apt"
        section = {kind: packages, "scripts": self.scripts}
        if platform == "darwin":
            section["nvm"] = {"url": "https://nvm.example/install.sh"}
        data = {
            "chezmoi": {"os": platform, "homeDir": str(self.home)},
            "packages": {platform: section},
        }
        return [
            CHEZMOI, "--source", str(SOURCE), "--destination", str(self.home),
            "--persistent-state", str(self.root / "state"),
            "--override-data", json.dumps(data), "--no-tty",
        ]

    def run_installer(self, platform, packages, apply=False):
        base = self.base(platform, packages)
        if apply:
            command = base + ["apply", str(self.home / f"install-packages-{platform}.sh")]
        else:
            template = SOURCE / f"run_before_install-packages-{platform}.sh.tmpl"
            rendered = subprocess.run(
                base + ["execute-template", "--file", str(template)],
                capture_output=True, text=True, check=True,
            ).stdout
            script = self.root / "installer.sh"
            script.write_text(rendered)
            subprocess.run(["/bin/sh", "-n", str(script)], check=True)
            command = ["/bin/sh", str(script)]
        return subprocess.run(command, env=self.env, capture_output=True, text=True,
                              timeout=30, start_new_session=True)

    def calls(self):
        return self.log.read_text() if self.log.exists() else ""

    def test_existing_website_and_nvm_tools_need_no_homebrew(self):
        self.stub("audit-local-tool", directory=self.home / ".local/bin")
        self.stub("audit-nvm-tool", directory=self.home / ".nvm/versions/node/v1/bin")
        packages = [
            {"name": "audit-local", "commands": ["audit-local-tool"]},
            {"name": "audit-node", "commands": ["audit-nvm-tool"]},
        ]
        result = self.run_installer("darwin", packages)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), "")

    def test_only_missing_cli_formula_is_requested(self):
        self.stub("audit-present")
        packages = [
            {"name": "audit-present-package", "commands": ["audit-present"]},
            {"name": "audit-missing-package", "commands": ["audit-missing"]},
        ]
        result = self.run_installer("darwin", packages)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), 'brew bundle --no-upgrade --file=-\nbrew "audit-missing-package"\n')

    def test_every_required_command_must_be_available(self):
        self.stub("audit-runtime")
        result = self.run_installer("darwin", [
            {"name": "audit-runtime", "commands": ["audit-runtime", "audit-package-runner"]},
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('brew "audit-runtime"', self.calls())

    def test_linux_preserves_existing_tools_and_certificates(self):
        self.stub("audit-manual", directory=self.home / ".cargo/bin")
        result = self.run_installer("linux", [
            {"name": "audit-manual", "commands": ["audit-manual"]},
            {"name": "ca-certificates", "commands": []},
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), "")

    def test_linux_installs_missing_commands_and_certificate_data(self):
        self.env["AUDIT_CERT_INSTALLED"] = "0"
        for uid in ["0", "1000"]:
            with self.subTest(uid=uid):
                self.log.unlink(missing_ok=True)
                self.env["AUDIT_UID"] = uid
                result = self.run_installer("linux", [
                    {"name": "audit-missing", "commands": ["audit-missing"]},
                    {"name": "ca-certificates", "commands": []},
                ])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("apt-get install -y --no-install-recommends --no-upgrade audit-missing ca-certificates", self.calls())
                self.assertEqual("sudo apt-get update" in self.calls(), uid != "0")

    def test_linux_without_admin_rights_skips_everything(self):
        self.env.update(AUDIT_UID="1000", AUDIT_SUDO_NOPASS="0", AUDIT_GROUPS="users")
        self.scripts = [{"name": "uv", "commands": ["audit-uv"], "url": "https://uv.example/i.sh",
                         "shell": "sh", "env": []}]
        result = self.run_installer("linux", [{"name": "audit-missing", "commands": ["audit-missing"]}])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no administrator rights", result.stdout)
        self.assertEqual(self.calls(), "")

    def test_linux_admin_group_without_terminal_skips(self):
        # sudo needs a password and no terminal can answer: skip, never hang.
        self.env.update(AUDIT_UID="1000", AUDIT_SUDO_NOPASS="0", AUDIT_GROUPS="users sudo")
        result = self.run_installer("linux", [{"name": "audit-missing", "commands": ["audit-missing"]}])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("apt-get install", self.calls())

    def test_linux_skips_packages_missing_from_release(self):
        self.env["AUDIT_APT_MISSING"] = "audit-new"
        result = self.run_installer("linux", [
            {"name": "audit-old", "commands": ["audit-old"]},
            {"name": "audit-new", "commands": ["audit-new"]},
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--no-upgrade audit-old\n", self.calls())
        self.assertIn("audit-new", result.stdout)

    def test_linux_admin_runs_official_installer_globally(self):
        self.env["AUDIT_UID"] = "1000"
        self.scripts = [{"name": "uv", "commands": ["audit-uv"], "url": "https://uv.example/i.sh",
                         "shell": "sh", "env": ["UV_INSTALL_DIR=/usr/local/bin"]}]
        result = self.run_installer("linux", [])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("sudo env SHELL=/bin/sh UV_INSTALL_DIR=/usr/local/bin sh", self.calls())
        self.assertIn("installer ran: SHELL=/bin/sh", self.calls())

    def test_mac_official_installers_only_for_missing_commands(self):
        self.stub("audit-present")
        self.scripts = [
            {"name": "present", "commands": ["audit-present"], "url": "https://p.example/i.sh",
             "shell": "sh", "env": []},
            {"name": "missing", "commands": ["audit-absent"], "url": "https://m.example/i.sh",
             "shell": "sh", "env": ["AUDIT_FLAG=1"]},
        ]
        result = self.run_installer("darwin", [])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("p.example", self.calls())
        self.assertIn("curl https://m.example/i.sh", self.calls())
        self.assertIn("installer ran: SHELL=/bin/sh", self.calls())

    def test_mac_node_comes_from_nvm_without_rc_edits(self):
        # The host's own node is on the probed PATH, so check the rendered call.
        base = self.base("darwin", [])
        template = SOURCE / "run_before_install-packages-darwin.sh.tmpl"
        rendered = subprocess.run(base + ["execute-template", "--file", str(template)],
                                  capture_output=True, text=True, check=True).stdout
        self.assertIn('run_official_installer nvm "https://nvm.example/install.sh" bash PROFILE=/dev/null', rendered)
        self.assertIn("nvm install --lts", rendered)

    def test_failures_never_interrupt_apply_and_are_retried(self):
        packages = [{"name": "audit-missing", "commands": ["audit-missing"]}]
        self.scripts = [{"name": "tool", "commands": ["audit-tool"], "url": "https://t.example/i.sh",
                         "shell": "sh", "env": []}]
        self.env["AUDIT_BREW_EXIT"] = "1"
        self.env["AUDIT_CURL_FAIL"] = "https://t.example/i.sh"
        result = self.run_installer("darwin", packages, apply=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Package setup incomplete", result.stderr)
        self.env["AUDIT_BREW_EXIT"] = "0"
        del self.env["AUDIT_CURL_FAIL"]
        result = self.run_installer("darwin", packages, apply=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls().count("brew bundle"), 2)
        self.assertEqual(self.calls().count("installer ran"), 1)

    def test_manifest_has_no_desktop_downloads(self):
        packages = tomllib.loads((SOURCE / ".chezmoidata/packages.toml").read_text())["packages"]
        self.assertNotIn("casks", packages["darwin"])
        names = {item["name"] for item in packages["darwin"]["brews"]}
        self.assertFalse(names & {"ghostty", "zed", "rectangle", "font-fira-code-nerd-font"})



if __name__ == "__main__":
    unittest.main(verbosity=2)
