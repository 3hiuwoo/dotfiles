# Shared by Linux setup and the final upgrade. Reuse cached sudo credentials;
# prompt in a terminal only when the account belongs to an admin group.
in_admin_group() {
    for group in $(id -Gn 2>/dev/null); do
        case $group in sudo|admin|wheel) return 0 ;; esac
    done
    return 1
}

acquire_admin() {
    if [ "$(id -u)" -eq 0 ]; then
        as_root() { "$@"; }
    elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
        as_root() { sudo "$@"; }
    elif command -v sudo >/dev/null 2>&1 && in_admin_group \
        && (: </dev/tty) 2>/dev/null && sudo -v </dev/tty; then
        as_root() { sudo "$@"; }
    else
        return 1
    fi
}
