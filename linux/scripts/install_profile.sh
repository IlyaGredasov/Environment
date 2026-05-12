#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: install_profile.sh [-u USER] [--environ PATH]

Link:
  /usr/share/konsole/orange.profile -> ENVIRON/linux/configs/orange.profile

Defaults:
  USER    current invoking user; used only to expand ~/ in ENVIRON
  ENVIRON ~/Programming/Environment
EOF
}

target_user="${SUDO_USER:-$(id -un)}"
environ="~/Programming/Environment"

while (($# > 0)); do
    case "$1" in
        -u|--user)
            [[ $# -ge 2 ]] || { echo "install_profile.sh: missing value for $1" >&2; exit 2; }
            target_user=$2
            shift 2
            ;;
        --environ)
            [[ $# -ge 2 ]] || { echo "install_profile.sh: missing value for $1" >&2; exit 2; }
            environ=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "install_profile.sh: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

user_home=$(getent passwd "$target_user" | cut -d: -f6)
[[ -n "$user_home" ]] || { echo "install_profile.sh: cannot find home for user '$target_user'" >&2; exit 1; }

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

environ=$(expand_path "$environ")
source="$environ/linux/configs/orange.profile"
target_dir="/usr/share/konsole"
target="$target_dir/orange.profile"

[[ -e "$source" ]] || { echo "install_profile.sh: missing source: $source" >&2; exit 1; }
run_root mkdir -p -- "$target_dir"

if [[ -e "$target" && ! -L "$target" ]]; then
    echo "install_profile.sh: refusing to replace non-symlink: $target" >&2
    exit 1
fi

run_root rm -f -- "$target"
run_root ln -s -- "$source" "$target"

echo "Installed Konsole profile: $target"
