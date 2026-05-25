#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: install_dircolors.sh [-u USER] [--environ PATH]

Link:
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
            [[ $# -ge 2 ]] || { echo "install_dircolors.sh: missing value for $1" >&2; exit 2; }
            target_user=$2
            shift 2
            ;;
        --environ)
            [[ $# -ge 2 ]] || { echo "install_dircolors.sh: missing value for $1" >&2; exit 2; }
            environ=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "install_dircolors.sh: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

user_home=$(getent passwd "$target_user" | cut -d: -f6)
[[ -n "$user_home" ]] || { echo "install_dircolors.sh: cannot find home for user '$target_user'" >&2; exit 1; }

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

chown_link() {
    local target=$1
    if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
        chown -h "$target_user:" "$target" 2>/dev/null || true
    fi
}

environ=$(expand_path "$environ")
source="$environ/linux/configs/.dircolors"
target="$user_home/.dircolors"

[[ -e "$source" ]] || { echo "install_dircolors.sh: missing source: $source" >&2; exit 1; }
if [[ -e "$target" && ! -L "$target" ]]; then
    echo "install_dircolors.sh: refusing to replace non-symlink: $target" >&2
    exit 1
fi

rm -f -- "$target"
ln -s -- "$source" "$target"
chown_link "$target"

echo "Installed dircolors config for $target_user"
