# Download an official installer to a private temp file, then run it with the
# given interpreter. SHELL=/bin/sh keeps installers that append PATH blocks to
# bash/zsh/fish rc files from editing the managed dotfiles. Prefix the call
# with a privilege wrapper (as_root) for a global install.
# Usage: [WRAPPER] run_official_installer NAME URL INTERPRETER [VAR=value...]
run_official_installer() {
    _installer_runner=
    if [ "$1" = as_root ]; then
        _installer_runner=as_root
        shift
    fi
    _installer_name=$1
    _installer_url=$2
    _installer_shell=$3
    shift 3
    _installer_file=$(mktemp "${TMPDIR:-/tmp}/dotfiles-$_installer_name.XXXXXX")
    if ! curl --fail --silent --show-error --location --retry 3 \
        "$_installer_url" --output "$_installer_file"; then
        rm -f "$_installer_file"
        printf 'Could not download the %s installer from %s.\n' "$_installer_name" "$_installer_url" >&2
        return 1
    fi
    printf 'Installing %s with its official installer.\n' "$_installer_name"
    _installer_status=0
    $_installer_runner env SHELL=/bin/sh "$@" "$_installer_shell" "$_installer_file" \
        </dev/null || _installer_status=$?
    rm -f "$_installer_file"
    return "$_installer_status"
}
