# macOS workstation and Linux server dotfiles

Chezmoi source state for a full macOS workstation and headless Linux research
servers. Shared terminal configuration, completions, themes, and plugin sources
are included. OS-specific scripts install the dependencies before applying
files. Existing tools are accepted regardless of how they were installed.
Only terminal dependencies are installed; desktop applications and fonts are
installed manually. Desktop configuration and agent integrations are macOS-only.
A macOS-only preference script applies the selected Rectangle settings.
This repository currently has no remote configured.

## OS profiles and dependency installation

The profile is selected automatically from `.chezmoi.os`; no prompt or hostname
list is needed. `.chezmoiignore` controls which files are deployed, and
`.chezmoidata/packages.toml` is the single package list to maintain.

| Profile | Configuration | Dependencies |
| --- | --- | --- |
| macOS workstation | All managed configuration, including Ghostty, Zed, Rectangle, GitHub CLI, Lazygit, Yazi, Starship, and existing agent shell integrations | Existing terminal tools; Homebrew supplies missing commands only |
| Linux server | Bash, Git/Delta, Bat themes, Vim and its existing plugins, uv, SSH aliases, and portable terminal themes | Existing terminal tools; Debian/Ubuntu packages supply missing commands, Bash completions, and certificate data; user-local uv if absent |

The Linux scope was checked against the configured `miaa-hpc1`, `miaa-hpc2`, and
`miaa-lab` hosts on 2026-10-26. They use Ubuntu, Bash login shells, Vim, tmux,
rsync, uv, and Python research workloads, with no graphical sessions or agent
CLIs found. The VPS and unconfigured `miaa-sxy` are outside this profile audit.
The package installer also supports Debian through the same apt package list;
other Linux distributions fail with an explicit message until a native list is
added.

Linux excludes Ghostty, Zed, Rectangle, macOS helpers, GitHub CLI preferences,
Lazygit, Yazi, Starship, CCS, Grok, and zsh configuration/plugins. Bash is the
Linux interactive shell; `.bashrc` loads the shared environment automatically.
The login hook preserves existing `.bash_profile` content and the previous
`.bash_login`/`.profile` fallback when creating a new profile. Login shells are
not changed with `chsh`. Existing zsh installations and ignored files are left
untouched, but are no longer provisioned on Linux.

The two `run_onchange_before_install-packages-*.sh.tmpl` scripts run on the
matching OS before files are applied. They run again when their rendered
package list or installer changes, following chezmoi's
[package installation pattern](https://www.chezmoi.io/user-guide/advanced/install-packages-declaratively/).

- Both installers check commands first, preserving website-script, version-manager,
  native OS, and package-manager installations. The inherited PATH keeps priority;
  common user bin directories, Cargo, Bun, FZF, NVM Node installations, and standard
  Homebrew locations are also checked. No interactive startup files are sourced.
- Each package entry maps a fallback package name to its required commands:
  `git-delta` provides `delta`, `ripgrep` provides `rg`, and `bat-extras` supplies
  `batman`. On Linux, either `bat` or `batcat` satisfies Bat. These are availability
  checks, not enforced version upgrades; optional-tool version limits below apply.
- macOS: install only missing CLI packages with `brew bundle --no-upgrade`.
  Homebrew is bootstrapped only when a missing tool actually needs it; this may
  require Apple's command line tools and administrator access. No casks, desktop
  applications, or fonts are downloaded. Existing Node and standalone uv are kept.
- Linux: run apt only for missing commands or supporting data (CA certificates
  and Bash completions), as root or through sudo. No general upgrade is run.
  Install uv from its
  [official installer](https://docs.astral.sh/uv/getting-started/installation/)
  into `~/.local/bin` only if it is absent, without modifying shell profiles.
- Agent executables, provider setup, accounts, and credentials stay local to
  Macs. The installers do not install agent CLIs. CUDA/drivers, Conda, Python
  environments, and project libraries remain outside dotfile provisioning;
  use the project's uv workflow for project dependencies.

Ignored Linux files are left untouched if already present. These filters do
not uninstall packages or delete existing desktop/agent configuration. Externals
follow upstream default branches with a daily cache refresh; system packages use
each OS's repositories.

## Managed files

| Files | Purpose |
| --- | --- |
| `.zshenv`, `.zprofile`, `.zshrc` | macOS environment, optional Homebrew login setup, interactive shell |
| `.bashrc`, `.bash_profile` | Linux interactive shell and a login hook that preserves existing profile content |
| `env.sh` | Shared Bash/zsh environment and tool appearance |
| `.condarc` | Conda-forge defaults; disable base auto-activation |
| `.config/starship.toml` | macOS-only Starship prompt |
| `.config/eza/theme.yml` | Eza colors |
| `.config/fsh/catppuccin-mocha.ini` | macOS Fast Syntax Highlighting colors |
| `.zsh/ccs-init.zsh`, `.zsh/completions/_ccs` | macOS-only CCS wrapper and generated completion snapshot |
| `.grok/completions/zsh/_grok` | macOS-only generated Grok completion snapshot |
| `.zsh/plugins/macos/` | Existing macOS helpers, deployed only on macOS |
| `.vimrc` | Shared Vim settings and mappings; optional local overrides |
| `.vim/pack/vendor/` | Existing Vim plugin sources, fetched by externals |
| `.gitconfig`, `.gitignore`, `.config/git/ignore` | Shared Git preferences; one ignore list in `.gitignore`, also exposed through an XDG symlink; local Git overrides are included last |
| `.config/delta/themes/catppuccin.gitconfig` | Existing Catppuccin Delta theme snapshot |
| `.config/bat/themes/` | Catppuccin Mocha syntax theme and license, shared with Yazi from one source |
| `.config/ghostty/config`, `.config/ghostty/config.ghostty` | macOS-only terminal appearance and keybindings |
| `.config/zed/settings.json`, `.config/zed/keymap.json` | macOS-only editor preferences and keybindings; Context7 credentials come from a local input |
| `.config/lazygit/config.yml` | macOS-only Lazygit Catppuccin colors |
| `.config/yazi/theme.toml`, `.config/yazi/package.toml`, `.config/yazi/flavors/catppuccin-mocha.yazi/` | macOS-only Yazi theme selection, pinned package declaration, and required flavor assets |
| `.config/uv/uv.toml` | Prefer uv-managed Python installations |
| `.ssh/config` | Five existing SSH aliases; optional local overrides are included first |
| `.config/gh/config.yml` | macOS-only GitHub CLI preferences and aliases; authentication is excluded |
| `.config/rectangle/preferences.json` | Selected Rectangle shortcuts and behavior; applied by a macOS-only script |

The generated CCS/Grok completions contain command definitions, not login or
provider configuration. Refresh these snapshots after changing the corresponding
CLI version. CCS's executable and provider configuration remain machine-local.

## Upstream externals

Both `.chezmoiexternal.toml` and `dot_vim/.chezmoiexternal.toml` follow upstream
repositories' default branches, with `refreshPeriod = "24h"`. There are no
fixed commit hashes or archive checksums. Chezmoi refreshes an expired cache
when invoked; nothing updates in the background. Force an immediate refresh:

```sh
chezmoi apply -R
```

The root manifest supplies FSH, zsh-autosuggestions, zsh-history-substring-search,
zsh-completions, and Eza completion on Macs. Vim's scoped manifest supplies the
ten existing native packages (Ack, Catppuccin, CtrlP, Lightline, NERDCommenter,
NERDTree, Repeat, Surround, EasyMotion, and WakaTime) on both systems, plus FZF's
Vim wrapper under `pack/vendor/opt/fzf/`. It does not add `junegunn/fzf.vim`.

Archive externals use `exact = false` to preserve existing Git metadata and
extra files. Chezmoi owns the deployed upstream files; manage updates through
chezmoi instead of also pulling these plugin directories manually. Skills use
their own CLI and repository workflows, described below. Themes and other
ordinary captured configuration assets are separate from these externals.

Default-branch updates favor current upstream behavior over reproducing one
historical installation. Verify shell/Vim startup after refreshing. The shared
zsh-completions copy uses upstream's portable paths; Homebrew's prefix-specific
substitutions are not carried across machines.

## Platform and machine boundaries

| Area | Behavior |
| --- | --- |
| macOS utilities | Finder, AppleScript, Music, Spotify, Obsidian, and the LibreOffice app path are enabled only on macOS. The macOS plugin is not deployed on Linux. |
| Opening files/URLs | `open_command` uses `BROWSER` for web URLs when set, otherwise macOS `open` or Linux `xdg-open`. A headless machine needs an explicit browser or has no desktop opener. |
| Compiler | `cppcompile` uses `-stdlib=libc++` only on macOS; Linux uses its compiler's default standard library. |
| Homebrew | Discover an installed `brew`, including Apple Silicon, Intel Mac, and standard Linuxbrew paths. LLVM and extra completion paths use `HOMEBREW_PREFIX`. |
| Conda/Mamba | Source an existing installation from `CONDA_HOME`, the inherited `CONDA_EXE`, or common Miniforge/Miniconda/Anaconda locations. No environment is installed or copied. |
| Bun/NVM | Load only when their existing installation files are present. `BUN_INSTALL` and `NVM_DIR` can be overridden locally. |
| Missing CLI tools | Skip their aliases and initialization. On Debian/Ubuntu, `batcat` is also recognized as Bat. |
| Locale | Preserve the host's `LANG`; if unset, choose an available UTF-8 locale, otherwise `C`. |
| Fonts and themes | Install and select a Nerd Font manually for prompt/icons. The Catppuccin Mocha syntax theme is supplied for Bat and Delta. Older FZF versions may lack `--zsh` bindings or the configured colors. |
| Shell history | Use local `.zsh_history`, `HISTSIZE=2000`, and `SAVEHIST=1000` on both systems; never sync its contents. |
| Qoder and other local CLIs | Agent paths, aliases, and wrappers are rendered only on macOS. Binaries, accounts, dispatchers, sessions, and login data are not copied or installed. |
| Git | The global ignore path uses `~` instead of an absolute home path. The macOS credential helper is enabled only on macOS; other hosts configure their credential helper locally. Existing `safe.directory` entries stay in `.gitconfig.local`. |
| Ghostty | Both existing configuration filenames are preserved on Macs. The entire configuration directory is excluded on Linux. |
| Zed | Settings and keybindings are macOS-only. Context7 is enabled only when its local API key is present. The settings file is deployed with mode `0600`. |
| SSH | Alias key paths already use `~/.ssh/`. The directory uses mode `0700` and config uses `0600`; key files and host state are provisioned separately. |
| GitHub CLI | Only `config.yml` is shared between Macs; Linux is excluded. Its directory uses `0700` and config uses `0600`. Accounts, tokens, and `hosts.yml` stay local. |
| Rectangle | The JSON and apply script are macOS-only. The script writes selected keys using `defaults`, preserving update history, window state, and login-startup settings. |

Rectangle preferences were captured from the installed 0.98 release. The shared
JSON contains four shortcut dictionaries and six behavior settings, retaining
their original value types. `run_onchange_after_rectangle-preferences.sh.tmpl`
includes the JSON checksum so changes trigger an apply after files are deployed.
It uses native `plutil` and `defaults`, without installing or launching software.
If Rectangle is running when preferences change, relaunch it to load the changes.
Changes made in Rectangle's UI must be captured in the shared JSON separately.
The live application plist is not managed as a file. See Rectangle's
[preferences documentation](https://github.com/rxhanson/Rectangle#preferences-storage).

The Delta theme and Yazi flavor files are snapshots of the existing installation
on 2026-10-26, from [Catppuccin for Delta](https://github.com/catppuccin/delta)
and [Yazi flavors](https://github.com/yazi-rs/flavors). The Yazi package declaration
retains revision `0670801`; its flavor source, syntax theme, and both licenses
are included. Preview images and generated state are not needed for deployment.

Delta hyperlinks are enabled with `hyperlinks = true`. Delta versions before
0.19 need the Bat syntax theme installed separately, as documented by
[Catppuccin for Delta](https://github.com/catppuccin/delta#usage). The Mocha XML
and its license live once in `.chezmoitemplates/` and render into both Bat's themes
and Yazi's flavor. `run_onchange_after_build-bat-cache.sh.tmpl` builds the local
cache after deployment, on both platforms. The cache is generated state and is
never synced. If it is cleared manually, rebuild it with `bat cache --build`
(`batcat cache --build` on Debian/Ubuntu).

The global `--help` formatter remains available in zsh. The short `-h` flag is
left untouched so commands such as `du -h DIRECTORY` retain their arguments.

The macOS helper files are preserved from the existing local Oh My Zsh macOS
plugin snapshot, including its README/license notice. Spotify's help examples
use descriptive placeholders. Its real `~/.shpotify.cfg` stays local.

## Linux Bash

The Linux-only `.bashrc` provides:

- An immediate return for non-interactive shells, keeping SSH commands and
  file-transfer sessions quiet and free of interactive setup.
- Shared `env.sh` settings, duplicate-free additions of personal bin directories,
  and local append-only history (`HISTSIZE=2000`, `HISTFILESIZE=1000`).
- Existing Conda/Mamba and NVM initialization, optional Bun paths, system Bash
  completions, and optional FZF, Starship, and zoxide integration. Startup does
  not install or download tools.
- Git/uv aliases, Bat or Debian's `batcat`, optional Eza, a quoted-path-safe
  `mkcd`, vi editing with familiar insert bindings, and a plain SSH-friendly
  prompt when Starship is absent. No agent aliases or desktop helpers are loaded.
- `~/env.local.sh` for early environment settings and `~/.bashrc.local` for final
  interactive overrides. History, credentials, and these local files are ignored.

`modify_dot_bash_profile` maintains only its marked login hook. Other existing
profile content is retained; when no profile exists, the generated file keeps
Bash's `.bash_login` then `.profile` precedence. The hook avoids sourcing
`.bashrc` twice if an existing profile already loaded it. This follows
[Bash's startup-file rules](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html).

Before the first apply on an existing Linux account, move any host-specific
customizations from its old `.bashrc` into `.bashrc.local` or `env.local.sh`.
The shared `.bashrc` itself is fully managed. macOS Bash files are excluded and
remain local. After deployment, open a new shell to load the new configuration.

## Vim portability

Use a normal Vim 8.2+ build with native package support. True color and persistent
undo are enabled only when supported. The Space leader, existing mappings,
NERDTree behavior, commenting, motions, and Catppuccin theme are preserved.

- Clipboard: macOS uses `unnamed`. Linux uses `unnamedplus` only when supported
  and `DISPLAY` or `WAYLAND_DISPLAY` is present. Clipboard access across SSH
  still depends on the remote Vim build and display connection. Normal Vim
  registers remain available without a desktop clipboard.
- FZF: sync the existing Vim wrapper, not an OS-specific executable. Load it only
  with an installed FZF >= 0.53; otherwise Space+p uses CtrlP. A compatible popup
  build uses the existing centered window; other builds use a lower split.
  Ripgrep (or Ack for the Ack plugin) also needs separate installation.
- WakaTime: retain the plugin but require an existing CLI and either its local
  config file or `WAKATIME_API_KEY`. Discover the CLI from PATH or the per-user
  WakaTime directory, or set `g:wakatime_CLIPath` in `.vimrc.local`. Respect
  `WAKATIME_HOME`. When prerequisites are missing, suppress plugin startup so it
  cannot download a binary or ask for a key. Restart Vim after configuring it.
- State: undo files, `.viminfo`, netrw history, swaps, backups, generated help
  tags, FZF history, and all WakaTime credentials/activity/binaries stay local.
  Plugin help sources are synced; run `:helptags ALL` locally if help tags need
  rebuilding on a new machine.

Documentation: [Vim clipboard](https://vimhelp.org/options.txt.html#%27clipboard%27),
[native packages](https://vimhelp.org/repeat.txt.html#packages),
[FZF wrapper](https://github.com/junegunn/fzf/tree/master/plugin), and
[WakaTime](https://github.com/wakatime/vim-wakatime).

## Local settings and credentials

These optional files are intentionally ignored by chezmoi and Git:

- `~/env.local.sh`: portable shell settings loaded by `env.sh`, before tool
  initialization; use this to set `CONDA_HOME`, `NVM_DIR`, or custom paths.
- `~/.zshenv.local`: settings needed by every zsh, including non-interactive
  shells. Keep this minimal and avoid printing output.
- `~/.zprofile.local`: login-shell additions.
- `~/.zshrc.local`: final interactive overrides.
- `~/.bashrc.local`: final Linux Bash overrides.
- `~/.vimrc.local`: machine-specific Vim overrides, loaded after shared settings
  and before the WakaTime readiness check.
- `~/.gitconfig.local`: machine-specific Git trust entries and optional identity,
  credential-helper, or other overrides. Git reads this file after shared settings.
- `~/.ssh/config.local`: optional machine-specific SSH settings, included before
  shared aliases so scalar options can be overridden. This file is not required.
- `~/.config/zed/chezmoi-local.json`: a private JSON input read by the chezmoi
  settings template, not directly by Zed. It holds `context7_api_key`; an absent
  file or empty key disables Context7 on that machine.

The current Git trust settings and Zed API key were preserved in these local
files with mode `0600`. On another machine, create the Zed input separately if
Context7 is needed, then run `chezmoi apply ~/.config/zed/settings.json`:

```json
{
  "context7_api_key": "YOUR_CONTEXT7_API_KEY"
}
```

Use `chmod 600 ~/.config/zed/chezmoi-local.json` after creating it. Do not run
`chezmoi add` on this file or recapture the rendered Zed settings with an embedded
key. Edit the managed template with `chezmoi edit ~/.config/zed/settings.json`.
Rendered diffs of that file can contain the local key.

`~/.secrets` is sourced if present and is never managed here. Application
credential files are outside the managed paths. History, completion dumps,
compiled `.zwc` files, and generated caches are excluded. FSH initializes its
theme cache from the synced INI and upstream plugin's bundled secondary theme,
without downloading anything during shell startup.

Zed's current prompts directory contains database files rather than portable
prompt sources, and its custom themes directory is empty; neither is managed.
Bibcc and cmux remain outside this expansion. Agent configuration is managed
only on macOS, with the narrow scope below.

## Shared agents and minimal Claude configuration (macOS)

`~/.agents/AGENTS.md` is the canonical global instruction file. Both
`~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` are relative symlinks to it.
Codex discovers `~/.agents/skills` directly.

`.chezmoidata/agent-skills.toml` lists the GitHub sources and names of 52 skills
(including the 13 MIAA BibTeX skills from `3hiuwoo/miaa-bibtex`) plus 2 Hugging
Face skills. `run_after_install-agent-skills.sh.tmpl` runs on each Mac apply, invoking
`npx --yes skills@latest add SOURCE --global --agent claude-code --skill ... --yes`
only for skills that are missing or not yet registered with that CLI. Existing
registered installations are not updated or replaced. A conflicting source
registration or Claude skill directory stops setup without deleting it.

Installed skill files and `~/.agents/.skill-lock.json` are **not managed by
chezmoi**. The CLI owns their contents and update metadata. No skill snapshots
or old hashes are restored after an update. To update user-wide skills:

```sh
npx skills update -g    # GitHub sources, including miaa-bibtex
hf skills update -g     # hf-cli, huggingface-papers
```

The Hugging Face skills are installed with `hf skills add NAME --global` and
tracked by their `.hf-skill-manifest.json`, not by the skills CLI lock.

The setup also ensures relative Claude links for every available shared skill,
including skills installed later. It preserves unrelated Claude skills and its
cloud-synced directory. Add new desired sources/names to the manifest so a fresh
Mac installs them too; removing a manifest entry does not uninstall a skill.
Do not use `chezmoi add` to capture installed skills or their registry.

The MIAA BibTeX skills install from the GitHub repository like other sources,
so a new Mac needs no local checkout. If `~/.agents/skills/NAME` is already a
symlink (for example into a `~/miaa-bibtex` development checkout), setup leaves
it alone and only ensures the Claude link.

| Managed source | Destination and behavior |
| --- | --- |
| `dot_agents/AGENTS.md` | Shared global instructions |
| `.chezmoidata/agent-skills.toml` | Missing-install manifest for the skills CLI; installed files/lock stay local |
| `.chezmoitemplates/claude/settings.json` | Merge portable preferences into `.claude/settings.json`, preserving additional local fields and environment variables |
| `dot_config/ccstatusline/settings.json` | Configuration for the existing `npx -y ccstatusline@latest` status line |

`~/.claude.json` stays entirely local. It contains account information, project
trust, usage history, and also some genuine global preferences such as plugin
favorites and display choices. Those preferences could be synchronized through
an explicit allowlist in the future, but the whole file should never be copied.
There are currently no user-wide MCP definitions to share, so the empty
source-side MCP fragment and its modifier were removed. If user-wide MCP
servers are added later, merge only the chosen server definitions into
`.claude.json`. `.mcp.json` is project-scoped, not a second global config file.

The Claude settings merge owns the values present in its shared template.
Unlisted keys remain local; removing a shared key does not remove the existing
destination value. It retains the existing inline notification hook and plugin
selections. Unused hook scripts, plugin downloads, sessions, account files,
histories, and caches are not captured. No `ccusage` configuration was present
or needed by this status line. Install/login to the agent CLIs separately.

Edit the shared JSON template directly. **Do not recapture `.claude.json` or
`.claude/settings.json` with `chezmoi add`**: they can contain local credentials
and runtime data. File mode `0600` restricts local access; it does not encrypt
source files.

Codex currently shares only the instruction link and `.agents` skills. Its
`config.toml`, keybindings, approval rules, auth, sessions, memories, and
app-managed computer-use integrations remain local. A future Codex extension
should merge a selected preference allowlist into `config.toml`, preserve
project trust and app-managed MCP/notification settings, and manage reviewed
keybindings separately. Do not capture the entire `.codex` directory.

All agent targets, the skill bootstrap, and `ccstatusline` are excluded on Linux.
Tests use a fake skills CLI to check missing installs, updates surviving apply,
registry preservation, retries, conflicting destinations, and Linux exclusion.

## Settings changed by application interfaces

Chezmoi is not automatic two-way synchronization. An app may change its live
settings without changing the chezmoi source. Review those edits before the next
apply; an apply can restore the source's values.

| Configuration | Current ownership and GUI behavior |
| --- | --- |
| Zed settings/keybindings | Whole-file managed. GUI edits, including new keys, are not imported and can be reverted by apply. The private Context7 input protects credentials, not GUI preference changes. |
| Claude settings | Shared template keys win on apply; unlisted local keys survive. `/config` edits to shared keys must be copied into the shared template to persist across applies/machines. |
| `.claude.json` and Codex config | Local; application changes are left alone. |
| Rectangle | The script applies selected keys when the source preferences change. Unrelated keys survive; GUI edits to selected keys are not captured and can be reset on a later script run. |
| ccstatusline and other ordinary config files | Whole-file managed; capture reviewed preference changes explicitly. |

For a preference intended for every Mac, transfer the changed, non-secret keys
from the live file into its source template (for Zed, use
`chezmoi edit ~/.config/zed/settings.json`). Review `chezmoi diff` locally before
applying. Zed diffs may include the local API key; never paste those raw diffs
or blindly re-add the rendered settings file. Ordinary non-secret files such as
Zed's keymap can be recaptured individually after review.

A local GUI edit is not yet a synchronized preference. Preserving all live
values automatically would also prevent shared settings updates from reaching
existing machines. A future GUI-friendly workflow should explicitly distinguish
local overrides from preferences promoted to the shared source; current behavior
above is documented rather than silently changed.

## Apply and maintain

The destination machine needs chezmoi and this source tree. The first apply
installs missing terminal dependencies; network access is needed for missing
packages, missing skills, and refreshed externals. Linux package installation needs root or sudo
when native packages are missing. Vim plugin sources are fetched by chezmoi.
Install desktop applications (including Ghostty, Zed, and Rectangle), your terminal
font, and Zed's selected Catppuccin theme/icon extensions separately on Macs;
extension installations and login state are not copied. Bun, NVM, Conda/Mamba,
and agent executables remain optional machine-local installations.

Review and apply from this source directory:

```sh
chezmoi diff
chezmoi apply
```

To update configuration without running package or preference scripts:

```sh
chezmoi apply --exclude scripts
```

The installers do not deploy anything to remote hosts. Copy or initialize this
source tree there and run chezmoi locally on the host when ready.

Edit the managed source through chezmoi, then review and apply:

```sh
chezmoi edit ~/.zshrc
chezmoi diff
chezmoi apply
```

If editing a live managed file directly, capture that specific file again with
`chezmoi add FILE`. Commit source changes locally when ready; pushing and remote
setup are separate steps. Do not broadly add credential or cache directories.

Chezmoi references: [externals](https://www.chezmoi.io/reference/special-files/chezmoiexternal-format/),
[conditional ignores](https://www.chezmoi.io/reference/special-files/chezmoiignore/),
and [daily operations](https://www.chezmoi.io/user-guide/daily-operations/).

## Bash profile verification on 2026-10-27

Run all shell and installer checks without installing anything:

```sh
uv run --no-project --python 3.12 python -m unittest discover -s tests -v
```

All 14 Bash and installer tests pass. The Bash checks cover Linux/macOS target selection, quiet non-interactive
startup, interactive settings and local overrides, repeated sourcing without
PATH growth, profile-content preservation and idempotency, login-file precedence,
single `.bashrc` loading, and optional tools/custom Conda initialization. They
run in temporary homes using Bash on macOS; no Linux host is deployed by them.

## Earlier terminal provisioning verification on 2026-10-27

Run the installer regression checks without installing anything:

```sh
uv run --no-project --python 3.12 python tests/test_provisioning.py
```

- Seven tests pass: website/NVM installation discovery, missing-command package
  selection, multi-command dependencies, Linux certificate data, root/sudo
  branches, failed-install retry, unchanged-run skipping, and no desktop downloads.
- Fresh temporary deployments pass file verification, shell/config parsing,
  interactive shell startup, Vim startup, Git ignore symlink and permission checks,
  and Delta theme/hyperlink checks: 461 files/symlinks on macOS and 439 on Linux.
- The current Mac needed only `htop`; the real apply installed it with Homebrew.
  Existing website/NVM/system commands were preserved. No desktop apps or fonts
  were installed. `chezmoi verify` passes, status is empty, and a second apply
  performs no work.
- Local Git ignore rules now match, the GitHub CLI directory uses `0700`, and
  Delta loads Catppuccin Mocha without a missing-theme warning. Yazi's theme bytes
  are unchanged, and the private Zed key remains absent from source files.
- Linux rendering and startup were simulated on macOS. Native Linux installation
  and a first-time Homebrew bootstrap were not performed in this round.
- No Git commit or remote setup was performed.

## Historical OS profile verification on 2026-10-26

These checks predate the command-based installation policy and terminal-only
package scope introduced on 2026-10-27; the old cask behavior is no longer used.

- Both profiles rendered and passed zsh/POSIX shell syntax checks. Fresh
  temporary deployments passed apply, verify, and repeated status checks with
  scripts excluded: 461 non-directory entries on macOS and 438 on Linux.
- Linux deployment omitted every desktop/workstation configuration listed
  above, and all agent references were absent from its rendered shell files.
- Stub package-manager runs exercised missing-package selection, root/sudo
  branches, failed-install retry, already-installed packages, and chezmoi's
  skip behavior after a successful unchanged install.
- The macOS installer generated the expected Homebrew package list, passed
  `--no-upgrade`, preserved existing app bundles, and skipped repeated execution.
- Native `sh -n` and read-only apt package-candidate checks passed on all three
  configured research servers. No remote configuration or packages were changed.
- Real package downloads/bootstrap were not executed during these checks.

## Earlier capture verification on 2026-10-26

The checks below describe the initial capture, before the workstation/server
split. Their Linux target counts and desktop coverage are historical.

- Vim's ten plugin archives matched the installed tracked files, and the pinned
  FZF wrapper matched the Homebrew copy. Fresh macOS/Linux target deployments
  passed startup, mappings, theme, local overrides, reload safety, persistent
  undo, older/missing FZF fallback, and the FZF quickfix action checks.
- WakaTime prerequisites were tested with a local stub CLI and fixture config;
  absent prerequisites did not start an installer or ask for credentials.
- Applied only Vim targets in the Vim round. Native macOS Vim startup passed
  with the installed tools and synced FZF wrapper; tracking was suppressed in
  the smoke test to avoid recording test activity. Vim-only `chezmoi verify`
  passed and Vim-only status was empty. Existing editor history and WakaTime
  credentials were preserved.
- Shell syntax checks passed for all edited startup files and `env.sh`.
- Fresh temporary deployments passed for macOS and Linux target selections:
  plugins, theme generation, completions, history defaults, local overrides,
  optional tools present/absent, custom Conda/Mamba paths, openers, and Yazi.
- Fresh shell startup did not fetch anything from the network. Startup also
  succeeded with the downloaded plugins absent.
- Applied to the current Mac and verified startup in a native terminal with
  the installed tools. `chezmoi verify` passed and `chezmoi status` was empty.
- Initial shell-only managed file targets, including externals: 231 on macOS and 226 on Linux.
  The five macOS helper files are excluded from Linux deployments.

Linux branches were simulated using macOS zsh and Linux chezmoi target data;
validation on a native Linux host remains for the next machine deployment.

### Git, terminal, editor, and CLI expansion

- Added and applied 16 files for Git/Delta, Ghostty, Zed, Lazygit, Yazi, and uv.
  Scoped `chezmoi verify` passed and scoped `chezmoi status` was empty.
- Current Zed settings/keybindings and Ghostty options retained their effective
  values; the native Ghostty validator reported no diagnostics. Effective Git
  values, including theme settings and all existing trust entries, were preserved.
- Fresh temporary macOS and Linux target deployments passed scoped apply,
  idempotency, JSONC/TOML/XML parsing, platform conditionals, and file-mode checks.
  Missing local credentials disabled Context7; a synthetic credential containing
  quotes and backslashes rendered correctly.
- The current Zed key was absent from all source files. Rendered Zed settings
  and both private local inputs have mode `0600`. Bibcc and agent configuration
  were not added. Linux rendering was checked on macOS, not a native Linux host.

### SSH, Rectangle, and GitHub CLI expansion

- Added five existing SSH aliases, GitHub CLI preferences, and ten selected
  Rectangle preferences. The three managed files passed `chezmoi verify` and
  scoped status was empty after applying the Rectangle script.
- `ssh -G` resolved each alias identically before and after capture, without
  connecting to any server. SSH config and GitHub CLI config use mode `0600`;
  the SSH directory uses `0700`.
- Fresh macOS and Linux file deployments passed permission and GitHub CLI
  parsing checks. Rectangle files and script execution were excluded on Linux.
- A fresh macOS end-to-end apply deployed the JSON before executing its script.
  Native defaults checks preserved dictionary, Boolean, integer, and real value
  types plus an unrelated test preference. Repeated unchanged apply skipped the
  script. All current Rectangle preferences, including local app state, retained
  their effective values.
- SSH identities, `known_hosts`, and GitHub authentication files were untouched.
