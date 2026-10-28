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
    gpu_installed_version=$(dpkg-query -W -f='${Status} ${Version}\n' nvidia-dkms-open 2>/dev/null \
        | awk '$1 == "install" && $2 == "ok" && $3 == "installed" { print $4 }')
    [ -n "$gpu_installed_version" ] || return 1
    gpu_installed_version=${gpu_installed_version#*:}
    gpu_installed_version=${gpu_installed_version%%-*}
    [ -r /sys/module/nvidia/version ] || return 0
    gpu_loaded_version=$(cat /sys/module/nvidia/version)
    [ "$gpu_installed_version" != "$gpu_loaded_version" ]
}

# Called only after the installer's root/sudo check. This bootstraps a driver
# on a fresh Ubuntu host; it never replaces an existing driver or reloads a
# module. A failed health check is evidence to diagnose, not a reinstall order.
configure_nvidia() {
    printf 'NVIDIA GPUs needing a driver health check:\n%s\n' "$nvidia_pci"
    if ! ubuntu_system; then
        printf '%s\n' 'Automatic NVIDIA driver installation supports Ubuntu only; configure this distribution manually.' >&2
        return 0
    fi
    nvidia_driver_available || return 0
    gpu_packages=$(nvidia_driver_packages)
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
    elif [ -n "$(nvidia_driver_packages)" ]; then
        printf '%s\n' 'NVIDIA driver packages installed. Final activation and reboot checks follow dotfiles and apt upgrade.'
    else
        printf '%s\n' 'NVIDIA driver packages were not installed. Check repository and hardware support; no reboot was performed.' >&2
        return 1
    fi
}
