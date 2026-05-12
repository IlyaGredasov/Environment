#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: install_zsh.sh [-u USER] [--environ PATH]

Install zsh helpers, set USER\'s shell to zsh, remove bash leftovers, and link:
  ~/.zshrc     -> ENVIRON/linux/configs/.zshrc
  ~/.dircolors -> ENVIRON/linux/configs/.dircolors

Defaults:
  USER    current invoking user
  ENVIRON ~/Programming/Environment
EOF
}

target_user="${SUDO_USER:-$(id -un)}"
environ="~/Programming/Environment"

while (($# > 0)); do
    case "$1" in
        -u|--user)
            [[ $# -ge 2 ]] || { echo "install_zsh.sh: missing value for $1" >&2; exit 2; }
            target_user=$2
            shift 2
            ;;
        --environ)
            [[ $# -ge 2 ]] || { echo "install_zsh.sh: missing value for $1" >&2; exit 2; }
            environ=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "install_zsh.sh: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

user_home=$(getent passwd "$target_user" | cut -d: -f6)
[[ -n "$user_home" ]] || { echo "install_zsh.sh: cannot find home for user '$target_user'" >&2; exit 1; }

expand_path() {
    local path=$1
    if [[ "$path" == "~" ]]; then
        path=$user_home
    elif [[ "$path" == "~/"* ]]; then
        path="$user_home/${path:2}"
    fi
    if [[ "$path" != /* ]]; then
        path="$(pwd)/$path"
    fi
    path=${path%/}
    printf '%s\n' "$path"
}

run_root() {
    if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

chown_link() {
    local target=$1
    if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
        chown -h "$target_user:" "$target" 2>/dev/null || true
    fi
}

link_file() {
    local source=$1
    local target=$2

    [[ -e "$source" ]] || { echo "install_zsh.sh: missing source: $source" >&2; return 0; }
    if [[ -e "$target" && ! -L "$target" ]]; then
        echo "install_zsh.sh: refusing to replace non-symlink: $target" >&2
        return 1
    fi

    rm -f -- "$target"
    ln -s -- "$source" "$target"
    chown_link "$target"
}

install_packages() {
    if command -v apt >/dev/null 2>&1; then
        run_root apt update
        run_root apt install -y zsh zsh-autosuggestions zsh-syntax-highlighting
    elif command -v pacman >/dev/null 2>&1; then
        run_root pacman -S --needed --noconfirm zsh zsh-autosuggestions zsh-syntax-highlighting
    else
        echo "install_zsh.sh: unsupported package manager; expected apt-get or pacman" >&2
        exit 1
    fi
}

environ=$(expand_path "$environ")
config_dir="$environ/linux/configs"

install_packages

zsh_path=$(command -v zsh)
run_root chsh -s "$zsh_path" "$target_user"

rm -f -- "$user_home/.bashrc" "$user_home/.bash_history"
link_file "$config_dir/.zshrc" "$user_home/.zshrc"
link_file "$config_dir/.dircolors" "$user_home/.dircolors"
chsh -s /bin/zsh $target_user
echo "Installed zsh config for $target_user"
sudo reboot
