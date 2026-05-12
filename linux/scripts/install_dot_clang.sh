#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: install_dot_clang.sh [-u USER] [--environ PATH]

Link:
  ~/Programming/C++/.clang-format -> ENVIRON/common/configs/.clang-format
  ~/Programming/C++/.clang-tidy   -> ENVIRON/common/configs/.clang-tidy

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
            [[ $# -ge 2 ]] || { echo "install_dot_clang.sh: missing value for $1" >&2; exit 2; }
            target_user=$2
            shift 2
            ;;
        --environ)
            [[ $# -ge 2 ]] || { echo "install_dot_clang.sh: missing value for $1" >&2; exit 2; }
            environ=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "install_dot_clang.sh: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

user_home=$(getent passwd "$target_user" | cut -d: -f6)
[[ -n "$user_home" ]] || { echo "install_dot_clang.sh: cannot find home for user '$target_user'" >&2; exit 1; }

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

resolve_source() {
    local name=$1
    if [[ -e "$environ/common/configs/$name" ]]; then
        printf '%s\n' "$environ/common/configs/$name"
    elif [[ -e "$environ/common/$name" ]]; then
        printf '%s\n' "$environ/common/$name"
    else
        echo "install_dot_clang.sh: missing source for $name" >&2
        return 1
    fi
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

link_file() {
    local source=$1
    local target=$2

    if [[ -e "$target" && ! -L "$target" ]]; then
        echo "install_dot_clang.sh: refusing to replace non-symlink: $target" >&2
        return 1
    fi

    rm -f -- "$target"
    ln -s -- "$source" "$target"
    chown_user_link "$target"
}

environ=$(expand_path "$environ")
target_dir="$user_home/Programming/C++"
mkdir -p -- "$target_dir"
chown_user_dir "$user_home/Programming"
chown_user_dir "$target_dir"

clang_format=$(resolve_source ".clang-format")
clang_tidy=$(resolve_source ".clang-tidy")

link_file "$clang_format" "$target_dir/.clang-format"
link_file "$clang_tidy" "$target_dir/.clang-tidy"

echo "Installed clang config links for $target_user"
