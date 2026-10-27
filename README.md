# Dotfiles

[chezmoi](https://www.chezmoi.io/) source for my Mac and the Linux research
servers. The OS is detected automatically; there is nothing to choose.

| | macOS | Linux |
| --- | --- | --- |
| Shell | zsh | Bash (login shell is never changed) |
| Config synced | Everything below | Shell, Git/Delta, Vim, Bat/Eza themes, gh, Lazygit, Starship, uv, Conda, SSH aliases |
| Tools installed | Missing ones only (Homebrew + official installers) | Missing ones only, **and only with admin rights**; otherwise none |
| Agents (Claude, Codex, skills) | Yes | No |
| Desktop apps (Ghostty, cmux, Zed, Rectangle, Yazi) | Config only; install the apps yourself | No |

## Everyday use

```sh
chezmoi edit ~/.zshrc        # edit the source copy of a file
chezmoi diff                 # preview what apply would change
chezmoi apply                # apply files (and install missing tools)
chezmoi apply -x scripts     # apply files only, no installers
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
   CLIs. If Zed needs Context7, create its key file (see below).

## Tools

Edit **`.chezmoidata/packages.toml`**. It is the only tool list.

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

How installation behaves:

- **Never upgrades.** Use each tool's own updater (`brew upgrade`, `claude update`, ...).
- **Never blocks syncing.** A failed install is reported, files are still
  applied, and the next apply retries.
- **Never edits your rc files.** Installers run with `SHELL=/bin/sh` and their
  opt-out flags.
- **Linux needs admin rights:** root, passwordless sudo, or the `sudo` group with
  a terminal to type the password into. Without them nothing is installed, so
  servers that aren't yours stay untouched. Packages a release doesn't carry
  (e.g. `starship` on Ubuntu 24.04) are skipped.

Server status (checked 2026-10-27): `miaa-hpc1`, `miaa-hpc2` and `miaa-lab` have
no sudo, so only config is applied. `miaa-sxy` asks for the sudo password when
you run `chezmoi apply` in a terminal.

Not provisioned on purpose: other agent CLIs (Copilot, Cursor, Droid, Kiro,
Qoder), `uv tool` and npm global packages, CUDA/Conda/Python environments.

## Local files (never synced)

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
| `~/.secrets` | Sourced by zsh if present |
| `~/.config/zed/chezmoi-local.json` | Zed's Context7 key (below) |

Zed's Context7 key lives outside the repo:

```sh
printf '{ "context7_api_key": "YOUR_KEY" }\n' > ~/.config/zed/chezmoi-local.json
chmod 600 ~/.config/zed/chezmoi-local.json
chezmoi apply ~/.config/zed/settings.json
```

Don't `chezmoi add` the rendered Zed settings: they contain the key.

## Settings changed from an app's GUI

chezmoi syncs one way, from the repo to the machine. An app that edits its own
settings file doesn't update the repo, and the next apply may undo the change.

| Config | What happens to GUI edits |
| --- | --- |
| Zed, Ghostty, cmux, ccstatusline, other whole files | Overwritten on apply. Copy the change into the source (`chezmoi edit FILE`) to keep it. |
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
| `dot_bashrc`, `modify_dot_bash_profile` | Bash (Linux); the profile keeps existing content and only adds a hook that loads `.bashrc` |
| `env.sh` | Environment shared by both shells |
| `dot_condarc` | Conda (no auto-activated base) |
| `dot_vimrc`, `dot_vim/` | Vim |
| `dot_gitconfig.tmpl`, `dot_gitignore`, `dot_config/git`, `dot_config/delta` | Git and Delta |
| `dot_config/*` | bat, cmux, eza, fsh, ghostty, gh (`private_gh`), lazygit, rectangle, starship, uv, yazi, zed, ccstatusline |
| `private_dot_ssh/private_config` | SSH aliases |
| `dot_agents/`, `private_dot_claude/`, `private_dot_codex/`, `dot_grok/` | Agent instructions, Claude settings merge, Grok completions |
| `.chezmoiexternal.toml`, `dot_vim/.chezmoiexternal.toml` | Plugin clones |
| `.chezmoidata/`, `.chezmoitemplates/` | Package and skill manifests; shared script snippets |
| `.chezmoiignore` | What each OS skips |
| `run_before_install-packages-*.sh.tmpl` | Tool installers |
| `run_after_install-agent-skills.sh.tmpl` | Skill installer and Claude links |
| `run_onchange_after_*` | Rebuild bat's theme cache; apply Rectangle preferences |

## Tests

Tests run in temporary homes with fake package managers; nothing gets installed.

```sh
uv run --no-project --python 3.12 python -m unittest discover -s tests
```
