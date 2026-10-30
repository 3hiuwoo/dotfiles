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
        self.pci = self.root / "pci"
        self.pci.mkdir()
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
            "AUDIT_NVIDIA_INSTALLED": "0",
            "AUDIT_ARCH": "amd64",
            "AUDIT_BIN": str(self.bin),
            "TMPDIR": str(self.root),
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
        self.stub("dpkg-query", '''case "$*" in
*cuda-keyring*)
    [ -f "$AUDIT_LOG.keyring-installed" ] && printf 'install ok installed'
    exit 0 ;;
*nvidia-driver-*)
    if [ "$AUDIT_NVIDIA_INSTALLED" = 1 ] || [ -f "$AUDIT_LOG.driver-installed" ]; then
        printf '%s nvidia-dkms-open\n' "${AUDIT_NVIDIA_STATUS:-ii}"
    elif [ -n "${AUDIT_COMPUTE_BRANCH:-}" ]; then
        printf 'ii libnvidia-compute-%s:amd64\n' "$AUDIT_COMPUTE_BRANCH"
    fi
    exit 0 ;;
*'libnvidia-compute*'*)
    if [ -n "${AUDIT_COMPUTE_BRANCH:-}" ]; then
        for branch in $AUDIT_COMPUTE_BRANCH; do
            printf 'ii libnvidia-compute-%s:amd64\n' "$branch"
        done
    fi
    exit 0 ;;
*'nvidia-dkms-*'*)
    if [ "$AUDIT_NVIDIA_INSTALLED" = 1 ] || [ -f "$AUDIT_LOG.driver-installed" ]; then
        printf '%s nvidia-dkms-open\n' "${AUDIT_NVIDIA_STATUS:-ii}"
    fi
    exit 0 ;;
*nvidia-dkms-open*)
    if [ "$AUDIT_NVIDIA_INSTALLED" = 1 ] || [ -f "$AUDIT_LOG.driver-installed" ]; then
        printf 'install ok installed %s\n' "${AUDIT_DRIVER_VERSION:-615.71.10-1ubuntu1}"
    fi
    exit 0 ;;
esac
if [ "$AUDIT_CERT_INSTALLED" = 1 ]; then
printf 'install ok installed'
else
exit 1
fi''')
        self.stub("dpkg", '''case "$1" in
--print-architecture) printf '%s\n' "$AUDIT_ARCH" ;;
-i) printf 'dpkg %s\n' "$*" >> "$AUDIT_LOG"
    [ "${AUDIT_KEYRING_FAIL:-0}" = 1 ] && exit 1
    : > "$AUDIT_LOG.keyring-installed" ;;
*) exit 1 ;;
esac''')
        self.stub("uname", "printf '7.0.0-test\\n'")
        self.stub("modinfo", '''[ "${AUDIT_MODULE_MISSING:-0}" = 1 ] && exit 1
if [ "$AUDIT_NVIDIA_INSTALLED" = 1 ] || [ -f "$AUDIT_LOG.driver-installed" ]; then
    version=${AUDIT_DRIVER_VERSION:-615.71.10-1ubuntu1}
    version=${version#*:}
    printf '%s\n' "${version%%-*}"
else
    exit 1
fi''')
        self.stub("apt-get", '''printf "apt-get %s\\n" "$*" >> "$AUDIT_LOG"
if [ "$1" = update ] && [ "${AUDIT_UPDATE_FAIL:-0}" = 1 ]; then exit 100; fi
if [ "$1" = upgrade ]; then
    printf 'restart policy: %s\n' "${NEEDRESTART_MODE:-unset}" >> "$AUDIT_LOG"
    if [ "${AUDIT_CHECK_APPLY:-0}" = 1 ]; then
        [ -f "$HOME/.fixture" ] || exit 91
        printf 'files already applied\n' >> "$AUDIT_LOG"
    fi
    [ "${AUDIT_UPGRADE_FAIL:-0}" = 1 ] && exit 100
fi
case "$*" in
*'--no-upgrade audit-missing'*)
    [ "${AUDIT_PACKAGE_FAIL:-0}" = 1 ] && exit 100
    if [ "${AUDIT_CHECK_APPLY:-0}" = 1 ]; then
        printf '#!/bin/sh\nexit 0\n' > "$AUDIT_BIN/audit-missing"
        /bin/chmod +x "$AUDIT_BIN/audit-missing"
    fi ;;
*nvidia-dkms-open*|*nvidia-headless-*)
    [ "${AUDIT_DRIVER_FAIL:-0}" = 1 ] && exit 100
    [ "${AUDIT_NO_DRIVER:-0}" = 1 ] || : > "$AUDIT_LOG.driver-installed" ;;
esac
case "$*" in
*nvidia-dkms-open*|*nvidia-utils-*)
    if [ "${AUDIT_NO_SMI:-0}" != 1 ] && [ "${AUDIT_NO_DRIVER:-0}" != 1 ]; then
        printf '#!/bin/sh\nexit 1\n' > "$AUDIT_BIN/nvidia-smi"
        /bin/chmod +x "$AUDIT_BIN/nvidia-smi"
    fi ;;
esac
exit 0''')
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
        for name in ["mktemp", "rm", "cat", "sh", "bash", "awk", "readlink"]:
            (self.bin / name).symlink_to(shutil.which(name))
        (self.bin / "env").symlink_to("/usr/bin/env")
        self.setUp_node()

    scripts = []
    user_scripts = []
    uv_tools = []
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
        else:
            section["user_scripts"] = self.user_scripts
        data = {
            "chezmoi": {"os": platform, "homeDir": str(self.home)},
            "packages": {platform: section, "uv_tools": self.uv_tools},
        }
        return [
            CHEZMOI, "--source", str(SOURCE), "--destination", str(self.home),
            "--persistent-state", str(self.root / "state"),
            "--override-data", json.dumps(data), "--no-tty",
        ]

    def render_script(self, platform, packages, after=False):
        name = ("run_after_zz_upgrade-packages-linux.sh.tmpl" if after else
                f"run_before_install-packages-{platform}.sh.tmpl")
        rendered = subprocess.run(
            self.base(platform, packages) + ["execute-template", "--file", str(SOURCE / name)],
            capture_output=True, text=True, check=True,
        ).stdout
        if platform == "linux":
            for original, fixture in [
                ("/sys/bus/pci/devices", self.pci),
                ("/var/run/reboot-required", self.root / "reboot-required"),
                ("/sys/module/nvidia/version", self.root / "nvidia-loaded-version"),
                ("/proc/driver/nvidia/version", self.root / "nvidia-proc-version"),
            ]:
                rendered = rendered.replace(original, str(fixture))
            os_release = self.root / "os-release"
            os_release.write_text("ID=" + self.env.get("AUDIT_DISTRO", "ubuntu")
                                  + "\nVERSION_ID=" + self.env.get("AUDIT_VERSION", "26.04") + "\n")
            rendered = rendered.replace("/etc/os-release", str(os_release))
        return rendered

    def run_installer(self, platform, packages, apply=False, after=False):
        base = self.base(platform, packages)
        if apply:
            command = base + ["apply", str(self.home / f"install-packages-{platform}.sh")]
        else:
            script = self.root / "installer.sh"
            script.write_text(self.render_script(platform, packages, after=after))
            subprocess.run(["/bin/sh", "-n", str(script)], check=True)
            command = ["/bin/sh", str(script)]
        return subprocess.run(command, env=self.env, capture_output=True, text=True,
                              timeout=30, start_new_session=True)

    def calls(self):
        return self.log.read_text() if self.log.exists() else ""

    def apply_linux_lifecycle(self, packages=()):
        """Exercise real chezmoi ordering with mocked system commands."""
        source = self.root / "lifecycle-source"
        source.mkdir(exist_ok=True)
        (source / "run_before_install-packages-linux.sh").write_text(
            self.render_script("linux", packages))
        (source / "run_after_zz_upgrade-packages-linux.sh").write_text(
            self.render_script("linux", packages, after=True))
        (source / "dot_fixture").write_text("managed configuration\n")
        (source / "run_after_y_finish-files.sh").write_text(
            '#!/bin/sh\nprintf "other after action\\n" >> "$AUDIT_LOG"\n')
        base = self.base("linux", packages)
        base[base.index("--source") + 1] = str(source)
        self.env["AUDIT_CHECK_APPLY"] = "1"
        return subprocess.run(
            base + ["apply", "--force", "--exclude=externals"], env=self.env,
            capture_output=True, text=True, timeout=30, start_new_session=True,
        )

    def test_dependencies_and_dotfiles_precede_required_upgrade(self):
        self.gpu("0000:01:00.0")
        result = self.apply_linux_lifecycle([
            {"name": "audit-missing", "commands": ["audit-missing"]},
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertLess(calls.index("--no-upgrade audit-missing"), calls.index("nvidia-dkms-open"))
        self.assertLess(calls.index("nvidia-dkms-open"), calls.index("other after action"))
        self.assertLess(calls.index("other after action"), calls.index("apt-get upgrade"))
        self.assertIn("files already applied", calls)
        self.assertIn("restart policy: l", calls)
        self.assertIn("--with-new-pkgs --no-remove", calls)
        self.assertIn("Reboot required", result.stdout)
        self.assertNotIn("sudo reboot\n", calls)

    def test_required_upgrade_runs_on_every_apply_with_no_missing_tools(self):
        for _ in range(2):
            result = self.apply_linux_lifecycle()
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls().count("apt-get upgrade"), 2)
        self.assertIn("No reboot requirement detected", result.stdout)

    def test_upgrade_failure_returns_error_after_dotfiles_are_applied(self):
        self.env["AUDIT_UPGRADE_FAIL"] = "1"
        (self.root / "reboot-required").write_text("System restart required\n")
        result = self.apply_linux_lifecycle()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.home / ".fixture").read_text(), "managed configuration\n")
        self.assertIn("Apt upgrade is incomplete", result.stderr)
        self.assertIn("Reboot required", result.stderr)

    def test_update_failure_skips_upgrade_but_preserves_applied_files(self):
        self.env["AUDIT_UPDATE_FAIL"] = "1"
        result = self.apply_linux_lifecycle()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.home / ".fixture").exists())
        self.assertNotIn("apt-get upgrade", self.calls())

    def test_dependency_failure_still_allows_files_and_upgrade(self):
        self.gpu("0000:01:00.0")
        self.env["AUDIT_DRIVER_FAIL"] = "1"
        result = self.apply_linux_lifecycle()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.home / ".fixture").exists())
        self.assertIn("NVIDIA driver setup", result.stderr)
        self.assertIn("apt-get upgrade", self.calls())

    def test_missing_ordinary_dependency_is_reported_after_upgrade(self):
        self.env["AUDIT_PACKAGE_FAIL"] = "1"
        result = self.apply_linux_lifecycle([
            {"name": "audit-missing", "commands": ["audit-missing"]},
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.home / ".fixture").exists())
        self.assertIn("apt-get upgrade", self.calls())
        self.assertIn("Dependency still missing: audit-missing", result.stderr)

    def test_final_upgrade_requires_admin_rights(self):
        self.env.update(AUDIT_UID="1000", AUDIT_SUDO_NOPASS="0")
        result = self.apply_linux_lifecycle()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / ".fixture").exists())
        self.assertNotIn("apt-get", self.calls())
        self.assertIn("Skipping apt upgrade", result.stdout)

    def test_final_upgrade_uses_sudo_for_admin_user(self):
        self.env["AUDIT_UID"] = "1000"
        result = self.run_installer("linux", [], after=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("sudo apt-get update", self.calls())
        self.assertIn("sudo env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get upgrade", self.calls())

    def test_final_apt_upgrade_is_disabled_on_macos(self):
        self.assertEqual(self.render_script("darwin", [], after=True).strip(), "")

    def test_os_reboot_flag_is_reported_only_at_the_end(self):
        (self.root / "reboot-required").write_text("System restart required\n")
        (self.root / "reboot-required.pkgs").write_text("linux-image-test\n")
        result = self.run_installer("linux", [], after=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(result.stdout.index("Apt upgrade finished"), result.stdout.index("Reboot required"))
        self.assertIn("linux-image-test", result.stdout)

    def test_updated_driver_module_requires_manual_reboot(self):
        self.gpu("0000:01:00.0")
        self.env["AUDIT_NVIDIA_INSTALLED"] = "1"
        self.stub("nvidia-smi", "exit 1")
        (self.root / "nvidia-loaded-version").write_text("595.71.05\n")
        result = self.run_installer("linux", [], after=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Reboot required", result.stdout)
        self.assertNotIn("NVIDIA still does not expose", result.stderr)

    def test_matching_loaded_driver_needs_no_reboot(self):
        self.gpu("0000:01:00.0")
        self.env["AUDIT_NVIDIA_INSTALLED"] = "1"
        (self.root / "nvidia-loaded-version").write_text("615.71.10\n")
        self.stub("nvidia-smi", "printf '00000000:01:00.0\\n'")
        result = self.run_installer("linux", [], after=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No reboot requirement detected", result.stdout)
        self.assertNotIn("nvidia-dkms-open", self.calls())

    def test_pending_system_reboot_defers_gpu_health_diagnosis(self):
        self.gpu("0000:01:00.0")
        self.env["AUDIT_NVIDIA_INSTALLED"] = "1"
        (self.root / "nvidia-loaded-version").write_text("615.71.10\n")
        (self.root / "reboot-required").write_text("System restart required\n")
        self.stub("nvidia-smi", "exit 1")
        result = self.run_installer("linux", [], after=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("after the pending system reboot", result.stdout)
        self.assertIn("Reboot required", result.stdout)

    def test_final_gpu_check_preserves_passthrough_assignment(self):
        self.gpu("0000:01:00.0", driver="vfio-pci")
        result = self.run_installer("linux", [], after=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("assigned to", result.stderr)
        self.assertNotIn("NVIDIA still does not expose", result.stderr)

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

    def test_linux_without_admin_rights_skips_global_installs(self):
        self.env.update(AUDIT_UID="1000", AUDIT_SUDO_NOPASS="0", AUDIT_GROUPS="users")
        self.scripts = [{"name": "global", "commands": ["audit-global"], "url": "https://g.example/i.sh",
                         "shell": "sh", "env": []}]
        result = self.run_installer("linux", [{"name": "audit-missing", "commands": ["audit-missing"]}])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no administrator rights", result.stdout)
        self.assertEqual(self.calls(), "")

    def uv_stub(self):
        self.stub("uv", 'printf "uv %s\\n" "$*" >> "$AUDIT_LOG"\n'
                  '[ "${AUDIT_UV_FAIL:-}" = "$4" ] && exit 2\nexit 0')

    def test_linux_user_tools_install_without_admin_rights(self):
        self.env.update(AUDIT_UID="1000", AUDIT_SUDO_NOPASS="0", AUDIT_GROUPS="users")
        self.uv_stub()
        self.user_scripts = [{"name": "audit-installer", "commands": ["audit-installer"],
                              "url": "https://u.example/i.sh", "shell": "sh",
                              "env": ["UV_NO_MODIFY_PATH=1"]}]
        self.uv_tools = [{"name": "audit-pkg", "commands": ["audit-cli"]}]
        result = self.run_installer("linux", [{"name": "audit-missing", "commands": ["audit-missing"]}])
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertIn("installer ran: SHELL=/bin/sh", calls)
        self.assertIn("uv tool install --managed-python audit-pkg", calls)
        self.assertNotIn("sudo", calls)
        self.assertNotIn("apt-get", calls)
        self.assertIn("no administrator rights", result.stdout)

    def test_existing_global_user_tools_are_not_reinstalled(self):
        self.uv_stub()
        self.stub("audit-installer")
        self.stub("audit-cli")
        self.user_scripts = [{"name": "audit-installer", "commands": ["audit-installer"],
                              "url": "https://u.example/i.sh", "shell": "sh", "env": []}]
        self.uv_tools = [{"name": "audit-pkg", "commands": ["audit-cli"]}]
        result = self.run_installer("linux", [])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), "")

    def test_uv_tools_are_skipped_when_uv_is_unavailable(self):
        self.env["AUDIT_CURL_FAIL"] = "https://u.example/i.sh"
        self.user_scripts = [{"name": "uv", "commands": ["audit-uv"],
                              "url": "https://u.example/i.sh", "shell": "sh", "env": []}]
        self.uv_tools = [{"name": "audit-pkg", "commands": ["audit-cli"]}]
        result = self.run_installer("linux", [{"name": "audit-missing", "commands": ["audit-missing"]}])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("audit-pkg (uv unavailable)", result.stderr)
        self.assertIn("Package setup incomplete: uv audit-pkg (uv unavailable)", result.stderr)
        self.assertIn("--no-upgrade audit-missing", self.calls())

    def test_one_failed_uv_tool_does_not_stop_the_others(self):
        self.uv_stub()
        self.env["AUDIT_UV_FAIL"] = "audit-bad"
        self.uv_tools = [{"name": "audit-bad", "commands": ["audit-bad-cli"]},
                         {"name": "audit-good", "commands": ["audit-good-cli"]}]
        for platform in ["linux", "darwin"]:
            with self.subTest(platform=platform):
                self.log.unlink(missing_ok=True)
                result = self.run_installer(platform, [])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("uv tool install --managed-python audit-good", self.calls())
                self.assertIn("Package setup incomplete: audit-bad", result.stderr)

    def test_final_check_reports_missing_user_tools_without_admin(self):
        self.env.update(AUDIT_UID="1000", AUDIT_SUDO_NOPASS="0")
        self.uv_tools = [{"name": "audit-pkg", "commands": ["audit-cli"]}]
        result = self.run_installer("linux", [], after=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Dependency still missing: audit-pkg", result.stderr)
        self.assertIn("Skipping apt upgrade", result.stdout)
        self.assertNotIn("apt-get", self.calls())

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

    def gpu(self, address, vendor="0x10de", kind="0x030000", driver=None):
        device = self.pci / address
        device.mkdir()
        (device / "vendor").write_text(vendor + "\n")
        (device / "class").write_text(kind + "\n")
        if driver:
            (device / "driver").symlink_to(self.root / "drivers" / driver)

    def test_gpu_detection_excludes_audio_and_other_vendors(self):
        self.gpu("0000:01:00.1", kind="0x040300")
        self.gpu("0000:02:00.0", vendor="0x8086")
        self.assertEqual(self.run_installer("linux", []).returncode, 0)
        self.assertEqual(self.calls(), "")

    def test_healthy_gpus_need_no_admin_or_installs(self):
        self.gpu("0000:01:00.0")
        self.gpu("0001:02:00.0", kind="0x030200")
        self.stub("nvidia-smi", "printf '00000000:01:00.0\\n00000001:02:00.0\\n'")
        self.env.update(AUDIT_UID="1000", AUDIT_SUDO_NOPASS="0")
        result = self.run_installer("linux", [])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), "")
        self.assertNotIn("no administrator rights", result.stdout)

    def test_unconfigured_gpu_without_admin_is_untouched(self):
        self.gpu("0000:01:00.0")
        self.env.update(AUDIT_UID="1000", AUDIT_SUDO_NOPASS="0")
        result = self.run_installer("linux", [])
        self.assertIn("no administrator rights", result.stdout)
        self.assertEqual(self.calls(), "")

    def test_missing_second_gpu_diagnoses_existing_driver(self):
        self.gpu("0000:01:00.0")
        self.gpu("0000:02:00.0")
        self.stub("nvidia-smi", "printf '00000000:01:00.0\\n'")
        result = self.run_installer("linux", [])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("not exposing every GPU", result.stderr)
        self.assertEqual(self.calls(), "")

    def test_driver_waiting_for_reboot_is_not_reinstalled(self):
        self.gpu("0000:01:00.0")
        self.env["AUDIT_NVIDIA_INSTALLED"] = "1"
        result = self.run_installer("linux", [])
        self.assertIn("Check reboot state", result.stderr)
        self.assertEqual(self.calls(), "")

    def test_passthrough_gpu_is_not_reconfigured(self):
        self.gpu("0000:01:00.0", driver="vfio-pci")
        result = self.run_installer("linux", [])
        self.assertIn("assigned to", result.stderr)
        self.assertEqual(self.calls(), "")

    def test_fresh_ubuntu_gpu_host_bootstraps_driver_without_pin(self):
        self.gpu("0000:01:00.0")
        self.gpu("0000:02:00.0")
        result = self.run_installer("linux", [])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cuda/repos/ubuntu2604/x86_64/cuda-keyring_1.1-1_all.deb", self.calls())
        self.assertIn("dpkg -i", self.calls())
        self.assertIn("linux-headers-7.0.0-test libnvidia-compute nvidia-dkms-open", self.calls())
        self.assertEqual(self.calls().count("nvidia-dkms-open"), 1)
        self.assertLess(self.calls().index("dpkg -i"), self.calls().index("apt-get update"))
        self.assertFalse(list(self.root.glob("dotfiles-cuda-keyring.*")))
        self.assertIn("Final activation and reboot checks", result.stdout)
        self.assertNotIn("reboot\n", self.calls())
        # A second apply before reboot must not reinstall the newly added driver.
        again = self.run_installer("linux", [])
        self.assertIn("Check reboot state", again.stderr)
        self.assertEqual(self.calls().count("nvidia-dkms-open"), 1)

    def test_library_only_installation_is_completed_in_its_existing_branch(self):
        self.gpu("0000:01:00.0")
        self.env["AUDIT_COMPUTE_BRANCH"] = "580"
        result = self.apply_linux_lifecycle()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertIn("Completing NVIDIA compute installation in existing branch 580", result.stdout)
        self.assertIn("linux-modules-nvidia-580-open-7.0.0-test", calls)
        self.assertIn("linux-modules-nvidia-580-open-test", calls)
        self.assertIn("nvidia-headless-no-dkms-580-open nvidia-utils-580", calls)
        self.assertIn("--no-remove --no-install-recommends", calls)
        self.assertNotIn("cuda-keyring", calls)
        self.assertNotIn("nvidia-dkms-open", calls)
        self.assertIn("Reboot required", result.stdout)
        self.assertTrue((self.home / ".fixture").exists())
        again = self.run_installer("linux", [])
        self.assertIn("Check reboot state", again.stderr)
        self.assertEqual(self.calls(), calls)

    def test_library_only_repair_falls_back_to_matching_open_dkms(self):
        self.gpu("0000:01:00.0")
        self.env.update(AUDIT_COMPUTE_BRANCH="580-server",
                        AUDIT_APT_MISSING="linux-modules-nvidia-580-server-open-7.0.0-test")
        result = self.run_installer("linux", [])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("linux-headers-7.0.0-test nvidia-headless-580-server-open nvidia-utils-580-server", self.calls())

    def test_existing_module_only_needs_matching_missing_utility(self):
        self.gpu("0000:01:00.0")
        self.env.update(AUDIT_NVIDIA_INSTALLED="1", AUDIT_COMPUTE_BRANCH="580")
        result = self.run_installer("linux", [])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--no-install-recommends nvidia-utils-580", self.calls())
        self.assertNotIn("nvidia-headless", self.calls())
        self.assertNotIn("cuda-keyring", self.calls())

    def test_mixed_library_branches_are_not_automatically_reconfigured(self):
        self.gpu("0000:01:00.0")
        self.env["AUDIT_COMPUTE_BRANCH"] = "580 595"
        result = self.run_installer("linux", [])
        self.assertIn("Check reboot state", result.stderr)
        self.assertEqual(self.calls(), "")

    def test_missing_utility_is_an_error_even_with_pending_reboot(self):
        self.gpu("0000:01:00.0")
        self.env["AUDIT_NVIDIA_INSTALLED"] = "1"
        (self.root / "reboot-required").write_text("System restart required\n")
        result = self.run_installer("linux", [], after=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("NVIDIA installation is incomplete", result.stderr)
        self.assertNotIn("after the pending system reboot", result.stdout)

    def test_missing_running_kernel_module_is_not_a_reboot_only_state(self):
        self.gpu("0000:01:00.0")
        self.env.update(AUDIT_NVIDIA_INSTALLED="1", AUDIT_MODULE_MISSING="1")
        self.stub("nvidia-smi", "exit 1")
        (self.root / "reboot-required").write_text("System restart required\n")
        result = self.run_installer("linux", [], after=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("running-kernel module is missing", result.stderr)

    def test_incomplete_repair_still_applies_files_but_returns_failure(self):
        self.gpu("0000:01:00.0")
        self.env.update(AUDIT_COMPUTE_BRANCH="580", AUDIT_NO_SMI="1")
        (self.root / "reboot-required").write_text("System restart required\n")
        result = self.apply_linux_lifecycle()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.home / ".fixture").exists())
        self.assertIn("apt-get upgrade", self.calls())
        self.assertIn("NVIDIA installation is incomplete", result.stderr)

    def test_fresh_install_without_utility_is_not_reported_as_awaiting_reboot(self):
        self.gpu("0000:01:00.0")
        self.env["AUDIT_NO_SMI"] = "1"
        (self.root / "reboot-required").write_text("System restart required\n")
        result = self.apply_linux_lifecycle()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.home / ".fixture").exists())
        self.assertIn("driver packages were not installed completely", result.stderr)
        self.assertNotIn("Final activation and reboot checks", result.stdout)

    def test_no_supported_driver_does_not_claim_installation_success(self):
        self.gpu("0000:01:00.0")
        self.env["AUDIT_NO_DRIVER"] = "1"
        result = self.run_installer("linux", [])
        self.assertIn("driver packages were not installed", result.stderr)
        self.assertNotIn("Final activation and reboot checks", result.stdout)

    def test_partially_installed_driver_needs_diagnosis(self):
        self.gpu("0000:01:00.0")
        self.env.update(AUDIT_NVIDIA_INSTALLED="1", AUDIT_NVIDIA_STATUS="iF")
        result = self.run_installer("linux", [])
        self.assertIn("Check reboot state", result.stderr)
        self.assertEqual(self.calls(), "")

    def test_driver_install_failure_continues_and_reuses_keyring_on_retry(self):
        self.gpu("0000:01:00.0")
        self.env["AUDIT_DRIVER_FAIL"] = "1"
        result = self.run_installer("linux", [])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("NVIDIA driver setup", result.stderr)
        self.env["AUDIT_DRIVER_FAIL"] = "0"
        again = self.run_installer("linux", [])
        self.assertIn("Final activation and reboot checks", again.stdout)
        self.assertEqual(self.calls().count("dpkg -i"), 1)
        self.assertEqual(self.calls().count("nvidia-dkms-open"), 2)

    def test_keyring_download_failure_does_not_run_privileged_install(self):
        self.gpu("0000:01:00.0")
        self.env["AUDIT_CURL_FAIL"] = ("https://developer.download.nvidia.com/compute/cuda/repos/"
                                       "ubuntu2604/x86_64/cuda-keyring_1.1-1_all.deb")
        result = self.run_installer("linux", [])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("NVIDIA driver setup", result.stderr)
        self.assertNotIn("dpkg -i", self.calls())
        self.assertNotIn("apt-get", self.calls())
        self.assertFalse(list(self.root.glob("dotfiles-cuda-keyring.*")))

    def test_keyring_install_failure_does_not_install_driver(self):
        self.gpu("0000:01:00.0")
        self.env["AUDIT_KEYRING_FAIL"] = "1"
        result = self.run_installer("linux", [])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("NVIDIA driver setup", result.stderr)
        self.assertNotIn("apt-get", self.calls())
        self.assertFalse(list(self.root.glob("dotfiles-cuda-keyring.*")))

    def test_supported_releases_and_arm64_select_the_matching_repository(self):
        self.gpu("0000:01:00.0")
        for version, distribution in [("22.04", "ubuntu2204"), ("24.04", "ubuntu2404")]:
            with self.subTest(version=version):
                self.log.unlink(missing_ok=True)
                self.env.update(AUDIT_VERSION=version, AUDIT_ARCH="arm64", AUDIT_DRIVER_FAIL="1")
                Path(str(self.log) + ".keyring-installed").unlink(missing_ok=True)
                result = self.run_installer("linux", [])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"cuda/repos/{distribution}/sbsa/", self.calls())

    def test_unknown_release_or_architecture_does_not_add_repository(self):
        self.gpu("0000:01:00.0")
        for version, arch in [("28.04", "amd64"), ("26.04", "riscv64")]:
            with self.subTest(version=version, arch=arch):
                self.env.update(AUDIT_VERSION=version, AUDIT_ARCH=arch)
                result = self.run_installer("linux", [])
                self.assertIn("NVIDIA driver setup", result.stderr)
                self.assertEqual(self.calls(), "")

    def test_other_distributions_do_not_use_ubuntu_driver_tool(self):
        self.gpu("0000:01:00.0")
        self.env["AUDIT_DISTRO"] = "debian"
        result = self.run_installer("linux", [])
        self.assertIn("supports Ubuntu only", result.stderr)
        self.assertEqual(self.calls(), "")

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
        # uv and hf are per-user on both systems, never apt or global installs.
        self.assertEqual([t["name"] for t in packages["uv_tools"]], ["huggingface-hub"])
        self.assertNotIn("uv", {s["name"] for s in packages["linux"]["scripts"]})
        self.assertNotIn("hf", {a["name"] for a in packages["linux"]["apt"]})
        names = {s["name"] for s in packages["darwin"]["scripts"]}
        self.assertNotIn("hf", names)
        names = {item["name"] for item in packages["darwin"]["brews"]}
        self.assertFalse(names & {"ghostty", "zed", "rectangle", "font-fira-code-nerd-font"})



if __name__ == "__main__":
    unittest.main(verbosity=2)
