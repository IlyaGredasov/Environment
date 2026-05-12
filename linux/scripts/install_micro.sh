#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: install_micro.sh [-u USER] [--environ PATH]

Link:
  ~/.config/micro/bindings.json -> ENVIRON/linux/configs/micro_bindings.json
  ~/.config/micro/settings.json -> ENVIRON/common/configs/micro_settings.json

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
            [[ $# -ge 2 ]] || { echo "install_micro.sh: missing value for $1" >&2; exit 2; }
            target_user=$2
            shift 2
            ;;
        --environ)
            [[ $# -ge 2 ]] || { echo "install_micro.sh: missing value for $1" >&2; exit 2; }
            environ=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "install_micro.sh: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

user_home=$(getent passwd "$target_user" | cut -d: -f6)
[[ -n "$user_home" ]] || { echo "install_micro.sh: cannot find home for user '$target_user'" >&2; exit 1; }

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

chown_user_dir() {
    local target=$1
    if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
        chown "$target_user:" "$target" 2>/dev/null || true
    fi
}

chown_user_link() {
    local target=$1
    if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
        chown -h "$target_user:" "$target" 2>/dev/null || true
    fi
}

environ=$(expand_path "$environ")
bindings_source="$environ/linux/configs/micro_bindings.json"
settings_source="$environ/common/configs/micro_settings.json"
if [[ ! -e "$settings_source" && -e "$environ/common/micro_settings.json" ]]; then
    settings_source="$environ/common/micro_settings.json"
fi

target_dir="$user_home/.config/micro"
bindings_target="$target_dir/bindings.json"
settings_target="$target_dir/settings.json"

[[ -e "$bindings_source" ]] || { echo "install_micro.sh: missing source: $bindings_source" >&2; exit 1; }
[[ -e "$settings_source" ]] || { echo "install_micro.sh: missing source: $settings_source" >&2; exit 1; }
mkdir -p -- "$target_dir"
chown_user_dir "$user_home/.config"
chown_user_dir "$target_dir"

link_file() {
    local source=$1
    local target=$2

    if [[ -e "$target" && ! -L "$target" ]]; then
        echo "install_micro.sh: refusing to replace non-symlink: $target" >&2
        exit 1
    fi

    rm -f -- "$target"
    ln -s -- "$source" "$target"
    chown_user_link "$target"
}

link_file "$bindings_source" "$bindings_target"
link_file "$settings_source" "$settings_target"

echo "Installed micro config for $target_user"
