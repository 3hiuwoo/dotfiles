# Dotfiles

[chezmoi](https://www.chezmoi.io/) source for my Mac and the Linux research
servers. The OS is detected automatically; there is nothing to choose.

| | macOS | Linux |
| --- | --- | --- |
| Shell | zsh | Bash (login shell is never changed) |
| Config synced | Everything below | Shell, Git/Delta, Vim, Bat/Eza themes, gh, Lazygit, uv, Conda, SSH aliases |
| Tools installed | Missing ones only (Homebrew + official installers) | Install missing tools, then upgrade apt packages after applying files; **admin rights required** |
| Agents (Claude, Codex, skills) | Yes | No |
| Desktop apps (Ghostty, cmux, Zed, Rectangle, Yazi) | Config only; install the apps yourself | No |

## Everyday use

```sh
chezmoi edit ~/.zshrc        # edit the source copy of a file
chezmoi diff                 # preview what apply would change
chezmoi apply                # install missing tools, apply files; Linux admins also upgrade apt packages
chezmoi apply -x scripts     # apply files only; skip installation and upgrades
chezmoi apply -R             # also refresh downloaded plugins now
cd ~/.local/share/chezmoi    # the source repo; commit here
```

Edited a live file directly? Capture it with `chezmoi add FILE`, but never on
files holding secrets (see [Local files](#local-files-never-synced)).

## Setting up a new machine

1. Install chezmoi and get this repo onto the machine (`chezmoi init REPO_URL`).
2. Run `chezmoi diff`, then `chezmoi apply`.
3. Linux: if the old `.bashrc` had host-specific lines, move them to
   `~/.bashrc.local` first. The managed `.bashrc` replaces the whole file.
4. Mac: install desktop apps yourself, then log in to the agent
   CLIs. If Zed needs Context7, export its key in `~/.secrets` (see below).

For now, transfer the existing SSH private key securely and manually when
setting up a new Mac. Some servers restrict adding public keys, so reuse the
authorized key where needed. Keep private keys outside the dotfiles repo;
set `~/.ssh` to mode `700` and private-key files to `600`.

- [ ] Revisit encrypted SSH-key backup and restoration through chezmoi if
  managing more Macs makes manual setup inconvenient. Deferred for now:
  manual transfer is sufficient for the small number of Macs in use.

## Tools

Edit **`.chezmoidata/packages.toml`** for ordinary tools. NVIDIA driver
provisioning is described separately below.

| Section | Meaning |
| --- | --- |
| `packages.darwin.brews` | Mac tools from Homebrew |
| `packages.darwin.scripts` | Mac tools from their official installer (uv, Bun, Claude Code, Codex, Grok, Antigravity) |
| `packages.darwin.nvm` | Node.js, through nvm |
| `packages.linux.apt` | Linux tools from apt |
| `packages.linux.scripts` | Linux tools from their official installer (uv) |

Each entry lists the `commands` it provides. If they all exist already, the tool
is skipped, however it was installed. Adding a tool is one line:

```toml
{ name = "btop", commands = ["btop"] },        # inside brews = [ ... ] or apt = [ ... ]
```

Commented-out entries are excluded from installation. Their tool-specific
settings should also be excluded in `.chezmoiignore`. Among the currently
disabled tools, only Starship has a dedicated managed config: its config and
shell initialization automatically follow the active package list. Starship
is enabled on macOS and disabled on Linux, where Bash uses its built-in prompt.
The other commented-out tools have no dedicated managed config in this repo.

Ignoring a config preserves an existing local copy; it does not delete it or
uninstall the tool. The final Linux apt upgrade still updates all installed
apt packages, including tools whose entries are commented out. Use apt holds
or repository pinning when an installed package needs to stay on its current version.

How installation behaves:

- **Missing dependencies are installed before files are applied.** Installation
  failures are reported without stopping file application.
- **Linux apt upgrades are required after file application.** Every full apply
  with admin rights refreshes the apt index and upgrades all installed apt
  packages, including NVIDIA drivers from configured repositories. Mac tools
  and tools installed outside apt keep their own update commands.
- **Failures remain visible.** The final Linux step returns an error for a
  failed apt upgrade or an available dependency still missing, after dotfiles
  have been applied. The next apply retries.
- **Never edits your rc files.** Installers run with `SHELL=/bin/sh` and their
  opt-out flags.
- **Linux needs admin rights:** root, passwordless sudo, or the `sudo` group with
  a terminal to type the password into. Without them nothing is installed, so
  servers that aren't yours stay untouched. Packages a release doesn't carry
  are skipped.

The Linux order is: install dependencies (including an initial NVIDIA driver),
apply files and other after actions, upgrade apt packages, then report reboot
requirements. The scripted upgrade uses `apt-get upgrade --with-new-pkgs`,
equivalent to `apt upgrade` in allowing new dependencies without removing
packages. Package holds and branch pins are respected. It does not run
`autoremove`, unload GPU modules, or reboot. Upgrade configuration prompts keep
existing files; `needrestart` is asked to list restart needs for human handling.

At the end, the OS reboot flag and installed-versus-loaded NVIDIA driver version
are checked. Reboot manually when ready, then run `chezmoi apply` again to
verify. If package errors remain, resolve those before rebooting. An earlier
file or after-action failure stops chezmoi before the final upgrade step.

Server status (checked 2026-10-27): `miaa-hpc1`, `miaa-hpc2` and `miaa-lab` have
no sudo, so only config is applied. `miaa-sxy` asks for the sudo password when
you run `chezmoi apply` in a terminal.

Not provisioned on purpose: other agent CLIs (Copilot, Cursor, Droid, Kiro,
Qoder), `uv tool` and npm global packages, CUDA/Conda/Python environments.

## NVIDIA GPUs on Linux

`nvitop` is in the normal apt list: it is installed only when missing and with
admin rights, just like the other Linux tools. If the release does not carry
it, it is skipped.

On every apply, the Linux installer discovers NVIDIA display/compute devices
from PCI sysfs and compares their addresses with `nvidia-smi`. There is no
hostname list, fixed GPU count, or pinned driver branch. A new server or GPU
swap is checked the same way. Healthy GPUs need no reinstall; the final apt
upgrade can still update their driver normally.

On an Ubuntu machine with root/sudo access and no existing NVIDIA driver,
unconfigured GPUs trigger NVIDIA's compute-only installation: enable its apt
repository with `cuda-keyring`, then install matching running-kernel headers,
`libnvidia-compute`, and `nvidia-dkms-open`. The open kernel modules are recommended
for RTX 40/Ada and required for RTX 50/Blackwell. Ubuntu 22.04, 24.04, and 26.04
are supported on amd64 and arm64; other releases/architectures are reported
without adding a repository. The driver branch is not pinned. Driver
dependencies may be upgraded by this operation; the CUDA development toolkit
is not installed. See [NVIDIA's Ubuntu guide](https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/latest/ubuntu.html)
and [kernel-module guidance](https://developer.nvidia.com/blog/nvidia-transitions-fully-towards-open-source-gpu-kernel-modules/).

An existing driver is left for the final apt upgrade, which installs newer
available versions from its configured repository. Package upgrades replace the
installed version; a loaded older module remains active until reboot. If any
GPU remains unavailable afterward, the final check requests a reboot when the
module version differs, or reports a problem for diagnosis. Devices assigned to
another driver such as `vfio-pci` are excluded from NVIDIA setup and verification.
Automatic initial NVIDIA installation is Ubuntu-only; other apt distributions
still receive their normal package upgrades. After rebooting, run `chezmoi apply`
again to verify.

## Local files (never synced)

`.chezmoiignore` controls deployment to the home directory; `.gitignore`
controls which local files Git leaves untracked. Repository documentation,
tests, and local Python/uv caches are excluded from deployment. The virtual
environment (`.venv/`), uv cache (`.uv-cache/`), pytest cache (`.pytest_cache/`),
and Python bytecode stay local and are not committed.

Create these when a machine needs its own settings. They are not in the source
state, so chezmoi never touches them; `.gitignore` keeps them out of commits.
Add single files, not whole directories such as `~/.ssh` or `~/.claude`: nothing
stops `chezmoi add` from copying keys or credentials into the source.

| File | Use |
| --- | --- |
| `~/env.local.sh` | Early environment for both shells (`CONDA_HOME`, `NVM_DIR`, PATHs) |
| `~/.zshenv.local`, `~/.zprofile.local`, `~/.zshrc.local` | zsh overrides |
| `~/.bashrc.local` | Bash overrides |
| `~/.vimrc.local` | Vim overrides |
| `~/.gitconfig.local` | Git identity, `safe.directory`, credential helper |
| `~/.ssh/config.local` | Extra SSH settings, read before the shared aliases |
| `~/.secrets` | Sourced by zsh if present; includes the Context7 environment variable |

Zed's settings are symlinked to `.tracked/settings.json`, so GUI edits update
the source directly. The Context7 extension manages installing and launching
the MCP server. Leave `settings.context7_api_key` unset so the server reads
`CONTEXT7_API_KEY` from its environment instead. In your local `~/.secrets`, add:

```sh
export CONTEXT7_API_KEY='YOUR_KEY'
```

Keep `~/.secrets` at mode `600`. Open a new shell and fully quit/relaunch Zed
after changing the key. Zed inherits the shell environment when opened from
the CLI, or loads a login-shell environment when opened from the Dock.
Without the variable, Context7 runs anonymously with lower limits. A literal
`"$CONTEXT7_API_KEY"` in settings is not expanded; omit that setting entirely.
Do not enter credentials into the symlinked settings file. The previous
`~/.config/zed/chezmoi-local.json` file is no longer used.

## Settings changed from an app's GUI

For regular managed files, chezmoi syncs from the repo to the machine; an app's
edits do not update the source, and the next apply may undo them. Symlinked
files such as Zed's settings point directly into the repo instead.

| Config | What happens to GUI edits |
| --- | --- |
| Zed | Symlinked to `.tracked/settings.json`; GUI edits update the source directly. Keep credentials in `~/.secrets`. |
| Ghostty, cmux, ccstatusline, other whole files | Overwritten on apply. Copy the change into the source (`chezmoi edit FILE`) to keep it. |
| Claude `settings.json` | Merged: keys in the shared template win, other local keys survive. |
| Rectangle | Only the selected keys are written, and only when the shared JSON changes. |
| `~/.claude.json`, Codex `config.toml` | Not managed; apps own them. |

## Agents (Mac only)

- **Instructions:** `~/.agents/AGENTS.md` is the single source. `~/.claude/CLAUDE.md`
  and `~/.codex/AGENTS.md` link to it.
- **Skills:** listed in `.chezmoidata/agent-skills.toml`. Each apply installs only
  missing ones and links every skill into `~/.claude/skills`. The installed files
  belong to their CLIs, so update them there:

  ```sh
  npx skills update -g    # GitHub sources, including 3hiuwoo/miaa-bibtex
  hf skills update -g     # hf-cli, huggingface-papers
  ```

  A skill that is already a symlink (e.g. into a `~/miaa-bibtex` checkout) is left
  alone. Removing a manifest entry doesn't uninstall the skill.
- **Claude:** `.chezmoitemplates/claude/settings.json` holds the shared keys, merged
  into `~/.claude/settings.json`. `~/.claude.json` stays local; it has no
  user-level MCP servers worth sharing (they come from plugins).
- **Codex:** only the instruction link and skills are shared. `config.toml`
  stays local.

## Plugins and externals

Plugins are installed the way their READMEs recommend, separately from the CLI
tools in `.chezmoidata/packages.toml`:

- `.chezmoiexternal.toml` (four zsh plugins) and `dot_vim/.chezmoiexternal.toml`
  (ten Vim plugins) are Git clones of each upstream's default branch. chezmoi
  clones missing ones and fast-forwards them at most daily, never overwriting
  local work: if a clone has diverged, the pull fails and apply reports an
  error until you fix that clone. Cloning needs `git` (on a fresh Mac it comes
  with the Command Line Tools that Homebrew's installer sets up).
- Files that must match an installed tool come from that tool: Eza's zsh
  completion from its Homebrew package, and FZF's Vim wrapper from the installed
  fzf (beside the binary, or `/usr/share/doc/fzf/examples` on Debian/Ubuntu).

If help tags go missing, run `:helptags ALL` in Vim.

## Where things live

| Source | Target |
| --- | --- |
| `dot_zshrc.tmpl`, `dot_zshenv.tmpl`, `dot_zprofile.tmpl`, `dot_zsh/` | zsh (Mac) |
| `dot_bashrc.tmpl`, `modify_dot_bash_profile` | Bash (Linux); the profile keeps existing content and only adds a hook that loads `.bashrc` |
| `env.sh` | Environment shared by both shells |
| `dot_condarc` | Conda (no auto-activated base) |
| `dot_vimrc`, `dot_vim/` | Vim |
| `dot_gitconfig.tmpl`, `dot_gitignore`, `dot_config/git`, `dot_config/delta` | Git and Delta |
| `dot_config/*` | bat, cmux, eza, fsh, ghostty, gh (`private_gh`), lazygit, rectangle, uv, yazi, zed, ccstatusline; Starship only where enabled in the package list (currently macOS) |
| `private_dot_ssh/private_config` | SSH aliases |
| `dot_agents/`, `private_dot_claude/`, `private_dot_codex/`, `dot_grok/` | Agent instructions, Claude settings merge, Grok completions |
| `.chezmoiexternal.toml`, `dot_vim/.chezmoiexternal.toml` | Plugin clones |
| `.chezmoidata/`, `.chezmoitemplates/` | Package and skill manifests; shared script snippets |
| `.chezmoiignore` | What each OS skips |
| `.gitignore` | Local overrides, credentials, and development artifacts excluded from Git |
| `run_before_install-packages-*.sh.tmpl` | Tool installers |
| `run_after_zz_upgrade-packages-linux.sh.tmpl` | Required final apt upgrade and manual reboot handoff (Linux admins) |
| `run_after_install-agent-skills.sh.tmpl` | Skill installer and Claude links |
| `run_onchange_after_*` | Rebuild bat's theme cache; apply Rectangle preferences |

## Tests

Tests run in temporary homes with fake package managers; nothing gets installed.

```sh
uv run --no-project --python 3.12 python -m unittest discover -s tests
```
