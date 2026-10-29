# NVIDIA hardware is discovered independently of the driver. Audio functions
# on the same card are excluded. Recheck on every apply, including after swaps.
nvidia_gpu_addresses() {
    for gpu_device in /sys/bus/pci/devices/*; do
        [ -r "$gpu_device/vendor" ] && [ -r "$gpu_device/class" ] || continue
        [ "$(cat "$gpu_device/vendor")" = 0x10de ] || continue
        case $(cat "$gpu_device/class") in
            0x03*) printf '%s\n' "${gpu_device##*/}" ;;
        esac
    done
}

nvidia_healthy() {
    command -v nvidia-smi >/dev/null 2>&1 || return 1
    if command -v timeout >/dev/null 2>&1; then
        gpu_report=$(timeout 15s nvidia-smi --query-gpu=pci.bus_id --format=csv,noheader 2>/dev/null) || return 1
    else
        gpu_report=$(nvidia-smi --query-gpu=pci.bus_id --format=csv,noheader 2>/dev/null) || return 1
    fi
    # NVML uses an eight-digit PCI domain; sysfs uses four digits.
    gpu_report=$(printf '%s\n' "$gpu_report" | awk -F: '
        NF == 3 {
            gsub(/[ \t\r]/, "")
            domain = $1
            if (length(domain) == 8) domain = substr(domain, 5)
            print tolower(domain ":" $2 ":" $3)
        }')
    for gpu_address in $nvidia_pci; do
        case "
$gpu_report
" in
            *"
$gpu_address
"*) ;;
            *) return 1 ;;
        esac
    done
}

ubuntu_system() (
    [ -r /etc/os-release ] || exit 1
    . /etc/os-release
    [ "${ID:-}" = ubuntu ]
)

nvidia_driver_packages() {
    dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' \
        'nvidia-driver-*' 'nvidia-headless-*' 'nvidia-dkms-*' \
        'linux-modules-nvidia-*' 'libnvidia-compute*' 'nvidia-kernel-*' \
        'nvidia-open*' 2>/dev/null \
        | awk '$1 ~ /^.[iUFWtH]/ && $2 !~ /^nvidia-driver-pinning-/ { print $2 }'
}

# Libraries and firmware alone do not supply a kernel driver. Keep this check
# separate so an interrupted/headless installation can be completed in place.
nvidia_kernel_packages() {
    dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' \
        'nvidia-dkms-*' 'linux-modules-nvidia-*' 2>/dev/null \
        | awk '$1 ~ /^.[iUFWtH]/ { print $2 }'
}

nvidia_module_version() {
    modinfo -k "$(uname -r)" -F version nvidia 2>/dev/null
}

nvidia_components_ready() {
    command -v nvidia-smi >/dev/null 2>&1 && nvidia_module_version >/dev/null
}

# Only fully configured compute libraries identify a branch safe to complete.
# Mixed branches and unconfigured packages require diagnosis instead.
nvidia_compute_branches() {
    dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' \
        'libnvidia-compute*' 2>/dev/null | awk '
        $1 == "ii" {
            name = $2
            sub(/:.*/, "", name)
            if (name ~ /^libnvidia-compute-[0-9]+(-server)?$/) {
                sub(/^libnvidia-compute-/, "", name)
                if (!seen[name]++) print name
            }
        }'
}

complete_nvidia_branch() {
    gpu_branch=$1
    as_root apt-get update || return 1
    if ! nvidia_module_version >/dev/null; then
        gpu_kernel=$(uname -r)
        gpu_flavour=${gpu_kernel#*-}
        gpu_flavour=${gpu_flavour#*-}
        gpu_module="linux-modules-nvidia-$gpu_branch-open-$gpu_kernel"
        gpu_module_meta="linux-modules-nvidia-$gpu_branch-open-$gpu_flavour"
        if apt-cache show --no-all-versions "$gpu_module" >/dev/null 2>&1 \
            && apt-cache show --no-all-versions "$gpu_module_meta" >/dev/null 2>&1; then
            # Prefer Ubuntu's signed modules for the running kernel, and track
            # future kernels through the matching flavour metapackage.
            set -- "$gpu_module" "$gpu_module_meta" "nvidia-headless-no-dkms-$gpu_branch-open"
        else
            set -- "linux-headers-$gpu_kernel" "nvidia-headless-$gpu_branch-open"
        fi
    else
        set --
    fi
    as_root env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y \
        --no-remove --no-install-recommends "$@" "nvidia-utils-$gpu_branch" || return 1
    if ! nvidia_components_ready; then
        printf '%s\n' 'NVIDIA installation is incomplete: nvidia-smi or the running-kernel module is missing. A reboot cannot repair missing components.' >&2
        return 1
    fi
    printf '%s\n' 'NVIDIA compute components installed. Final activation and reboot checks follow dotfiles and apt upgrade.'
}

nvidia_repository() (
    . /etc/os-release
    case ${VERSION_ID:-} in
        22.04) gpu_distribution=ubuntu2204 ;;
        24.04) gpu_distribution=ubuntu2404 ;;
        26.04) gpu_distribution=ubuntu2604 ;;
        *) printf 'NVIDIA setup: Ubuntu %s is not supported by this installer.\n' "${VERSION_ID:-unknown}" >&2
           exit 1 ;;
    esac
    gpu_arch=$(dpkg --print-architecture) || exit 1
    case $gpu_arch in
        amd64) gpu_arch=x86_64 ;;
        arm64) gpu_arch=sbsa ;;
        *) printf 'NVIDIA setup: unsupported architecture %s.\n' "$gpu_arch" >&2
           exit 1 ;;
    esac
    printf 'https://developer.download.nvidia.com/compute/cuda/repos/%s/%s\n' "$gpu_distribution" "$gpu_arch"
)

nvidia_driver_available() {
    for gpu_address in $nvidia_pci; do
        gpu_binding=$(readlink "/sys/bus/pci/devices/$gpu_address/driver" 2>/dev/null || true)
        case $gpu_binding in
            ''|*/nvidia|*/nouveau) ;;
            *) printf 'GPU %s is assigned to %s; leaving driver configuration alone.\n' "$gpu_address" "$gpu_binding" >&2
               return 1 ;;
        esac
    done
}

nvidia_reboot_needed() {
    gpu_installed_version=$(nvidia_module_version) || return 1
    [ -n "$gpu_installed_version" ] || return 1
    [ -r /sys/module/nvidia/version ] || return 0
    gpu_loaded_version=$(cat /sys/module/nvidia/version)
    [ "$gpu_installed_version" != "$gpu_loaded_version" ]
}

# Called only after the installer's root/sudo check. This bootstraps a driver
# on a fresh Ubuntu host, or completes known versioned compute libraries in
# their existing branch. It never reloads modules or replaces a kernel driver.
configure_nvidia() {
    printf 'NVIDIA GPUs needing a driver health check:\n%s\n' "$nvidia_pci"
    if ! ubuntu_system; then
        printf '%s\n' 'Automatic NVIDIA driver installation supports Ubuntu only; configure this distribution manually.' >&2
        return 0
    fi
    nvidia_driver_available || return 0
    gpu_packages=$(nvidia_driver_packages)
    if ! nvidia_components_ready; then
        gpu_branches=$(nvidia_compute_branches)
        # Branches are validated package-name suffixes, with no glob characters.
        # shellcheck disable=SC2086
        set -- $gpu_branches
        if [ "$#" -eq 1 ] && { nvidia_module_version >/dev/null \
            || { [ -z "$(nvidia_kernel_packages)" ] && [ ! -r /proc/driver/nvidia/version ]; }; }; then
            printf 'Completing NVIDIA compute installation in existing branch %s.\n' "$1"
            complete_nvidia_branch "$1"
            return $?
        fi
    fi
    if [ -n "$gpu_packages" ] || [ -r /proc/driver/nvidia/version ] \
        || command -v nvidia-smi >/dev/null 2>&1; then
        printf '%s\n' 'Existing NVIDIA driver is not exposing every GPU. Available driver updates will be applied after dotfiles. Check reboot state, kernel logs, module signing, and hardware compatibility if the problem remains.' >&2
        return 0
    fi
    gpu_repository=$(nvidia_repository) || return 1
    if [ "$(dpkg-query -W -f='${Status}' cuda-keyring 2>/dev/null || true)" != 'install ok installed' ]; then
        gpu_keyring=$(mktemp "${TMPDIR:-/tmp}/dotfiles-cuda-keyring.XXXXXX") || return 1
        if ! curl --fail --silent --show-error --location --retry 3 \
            "$gpu_repository/cuda-keyring_1.1-1_all.deb" --output "$gpu_keyring"; then
            rm -f "$gpu_keyring"
            return 1
        fi
        gpu_keyring_status=0
        as_root dpkg -i "$gpu_keyring" || gpu_keyring_status=$?
        rm -f "$gpu_keyring"
        [ "$gpu_keyring_status" -eq 0 ] || return 1
    fi
    # NVIDIA's compute-only Ubuntu installation, using open kernel modules for
    # Ada/RTX 40 and Blackwell/RTX 50. No hostname, GPU count, or branch pin.
    # Refresh after enabling the NVIDIA repository, even if apt ran earlier.
    as_root apt-get update || return 1
    as_root env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y \
        --no-install-recommends "linux-headers-$(uname -r)" \
        libnvidia-compute nvidia-dkms-open || return 1
    if nvidia_healthy; then
        printf '%s\n' 'NVIDIA driver exposes every detected GPU.'
    elif nvidia_components_ready; then
        printf '%s\n' 'NVIDIA driver packages installed. Final activation and reboot checks follow dotfiles and apt upgrade.'
    else
        printf '%s\n' 'NVIDIA driver packages were not installed completely: nvidia-smi or the running-kernel module is missing. Check package errors; no reboot was performed.' >&2
        return 1
    fi
}
