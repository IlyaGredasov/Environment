#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: add_context.sh [-t PATTERN]... [-c PATTERN]...

  -t, --tree  Add matching files to the tree section.
  -c, --cat   Print matching files with their contents.

Patterns can be literal paths, shell globs, simple brace globs like
src/*.{cpp,hpp}, or extended regular expressions matched against repo paths.
EOF
}

tree_patterns=()
cat_patterns=()

while (($# > 0)); do
    case "$1" in
        -t|--tree)
            if (($# < 2)); then
                echo "add_context.sh: missing value for $1" >&2
                exit 2
            fi
            tree_patterns+=("$2")
            shift 2
            ;;
        -c|--cat)
            if (($# < 2)); then
                echo "add_context.sh: missing value for $1" >&2
                exit 2
            fi
            cat_patterns+=("$2")
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "add_context.sh: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

expand_braces() {
    local pattern=$1
    if [[ "$pattern" == *"{"*"}"* ]]; then
        local prefix=${pattern%%\{*}
        local rest=${pattern#*\{}
        local inner=${rest%%\}*}
        local suffix=${rest#*\}}
        local part
        IFS=',' read -r -a parts <<< "$inner"
        for part in "${parts[@]}"; do
            expand_braces "$prefix$part$suffix"
        done
    else
        printf '%s\n' "$pattern"
    fi
}

normalize_path() {
    local path=$1
    path=${path#./}
    path=${path%/}
    printf '%s\n' "$path"
}

list_matches() {
    local pattern=$1
    local expanded
    local found=0

    while IFS= read -r expanded; do
        if [[ -e "$expanded" ]]; then
            normalize_path "$expanded"
            found=1
        fi

        while IFS= read -r match; do
            [[ -z "$match" ]] && continue
            normalize_path "$match"
            found=1
        done < <(compgen -G "$expanded" || true)
    done < <(expand_braces "$pattern")

    if ((found == 0)); then
        find . -path './.git' -prune -o \( -type f -o -type d \) -print \
            | sed 's#^\./##' \
            | grep -E "$pattern" 2>/dev/null || true
    fi
}

collect_files() {
    local pattern=$1
    local match

    while IFS= read -r match; do
        [[ -z "$match" ]] && continue
        if [[ -d "$match" ]]; then
            find "$match" -path '*/.git' -prune -o -type f -print \
                | sed 's#^\./##'
        elif [[ -f "$match" ]]; then
            normalize_path "$match"
        fi
    done < <(list_matches "$pattern")
}

render_tree() {
    awk -F/ '
        {
            for (i = 1; i < NF; i++) {
                dir = $1
                for (j = 2; j <= i; j++) {
                    dir = dir "/" $j
                }

                if (!(dir in seen_dirs)) {
                    seen_dirs[dir] = 1
                    if (i == 1) {
                        print $i
                    } else {
                        indent = ""
                        for (j = 1; j <= i - 2; j++) {
                            indent = indent "|   "
                        }
                        print indent "|-- " $i
                    }
                }
            }

            if (NF == 1) {
                print $1
            } else {
                indent = ""
                for (i = 1; i <= NF - 2; i++) {
                    indent = indent "|   "
                }
                print indent "|-- " $NF
            }
        }
    '
}

declare -A seen_tree=()
declare -A seen_cat=()
tree_files=()
cat_files=()

for pattern in "${tree_patterns[@]}"; do
    while IFS= read -r file; do
        [[ -z "$file" || "$file" == .git/* || "$file" == */.git/* ]] && continue
        if [[ -z "${seen_tree[$file]+x}" ]]; then
            seen_tree["$file"]=1
            tree_files+=("$file")
        fi
    done < <(collect_files "$pattern")
done

for pattern in "${cat_patterns[@]}"; do
    while IFS= read -r file; do
        [[ -z "$file" || "$file" == .git/* || "$file" == */.git/* ]] && continue
        if [[ -z "${seen_cat[$file]+x}" ]]; then
            seen_cat["$file"]=1
            cat_files+=("$file")
        fi
    done < <(collect_files "$pattern")
done

if ((${#tree_files[@]} > 0)); then
    printf '%s\n' "${tree_files[@]}" | sort -u | render_tree
fi

if ((${#tree_files[@]} > 0 && ${#cat_files[@]} > 0)); then
    printf '\n'
fi

for file in "${cat_files[@]}"; do
    [[ -f "$file" ]] || continue
    printf '# %s\n' "$file"
    cat -- "$file"
    printf '\n'
done
