# Preserve inherited PATH priority and recognize common website/version-manager
# installations even when chezmoi was launched outside an interactive shell.
PATH="$PATH:$HOME/bin:$HOME/.local/bin:$HOME/.cargo/bin:${BUN_INSTALL:-$HOME/.bun}/bin:$HOME/.fzf/bin"
for tool_bin in /opt/homebrew/bin /usr/local/bin /home/linuxbrew/.linuxbrew/bin \
    "$HOME/.linuxbrew/bin" "${NVM_DIR:-$HOME/.nvm}"/versions/node/*/bin; do
    if [ -d "$tool_bin" ]; then
        PATH="$PATH:$tool_bin"
    fi
done
export PATH

commands_available() {
    for tool_command do
        # Debian/Ubuntu package Bat as batcat; either installation is sufficient.
        if [ "$tool_command" = bat ] && command -v batcat >/dev/null 2>&1; then
            continue
        fi
        if [ "$tool_command" = fd ] && command -v fdfind >/dev/null 2>&1; then
            continue
        fi
        command -v "$tool_command" >/dev/null 2>&1 || return 1
    done
}
