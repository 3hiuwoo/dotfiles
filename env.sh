# Shared environment settings for interactive Bash and Zsh shells.
# Source with: . "$HOME/env.sh"
# Keep shell-specific initialization, aliases, and secrets in shell startup files.

# Personal commands. Keep this simple and portable across Bash and Zsh.
for _dotfiles_bin in "$HOME/.local/bin" "$HOME/bin"; do
    case :$PATH: in
        *":$_dotfiles_bin:"*) ;;
        *) PATH="$_dotfiles_bin:$PATH" ;;
    esac
done
unset _dotfiles_bin
export PATH

# General defaults.
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
export EDITOR="${EDITOR:-vim}"
export COLORTERM="${COLORTERM:-truecolor}"
# Respect the host locale; choose an installed UTF-8 locale only when unset.
if [ -z "${LANG:-}" ]; then
    case "$(locale -a 2>/dev/null)" in
        *en_US.UTF-8*) LANG=en_US.UTF-8 ;;
        *C.UTF-8*) LANG=C.UTF-8 ;;
        *C.utf8*) LANG=C.utf8 ;;
        *) LANG=C ;;
    esac
    export LANG
fi

# Tool locations and appearance.
export BUN_INSTALL="${BUN_INSTALL:-$HOME/.bun}"
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
export BAT_THEME="${BAT_THEME:-Catppuccin Mocha}"
export EZA_CONFIG_DIR="${EZA_CONFIG_DIR:-$XDG_CONFIG_HOME/eza}"

# FZF colors.
export FZF_DEFAULT_OPTS=" \
--color=bg+:#313244,bg:#1E1E2E,spinner:#F5E0DC,hl:#F38BA8 \
--color=fg:#CDD6F4,header:#F38BA8,info:#CBA6F7,pointer:#F5E0DC \
--color=marker:#B4BEFE,fg+:#CDD6F4,prompt:#CBA6F7,hl+:#F38BA8 \
--color=selected-bg:#45475A \
--color=border:#6C7086,label:#CDD6F4"

# Optional machine-specific paths/settings, loaded before tool initialization.
[ ! -r "$HOME/env.local.sh" ] || . "$HOME/env.local.sh"
