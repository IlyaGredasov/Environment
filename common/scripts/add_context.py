import fnmatch
import glob
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path.cwd().resolve()


@dataclass(frozen=True)
class Match:
    path: Path
    display_path: str


@dataclass(frozen=True)
class PatternSpec:
    pattern: str
    regex: bool = False
    root: str = "."
    max_depth: int | None = None


@dataclass(frozen=True)
class ParsedArgs:
    tree: list[PatternSpec]
    cat: list[PatternSpec]
    tree_ignore: list[PatternSpec]
    cat_ignore: list[PatternSpec]


@dataclass(frozen=True)
class IgnoreRule:
    pattern: str
    anchored: bool
    basename_only: bool
    directory_only: bool
    negated: bool


@dataclass(frozen=True)
class RegexIgnoreRule:
    regex: re.Pattern[str]
    negated: bool


IgnoreSpec = IgnoreRule | RegexIgnoreRule


def usage() -> str:
    return (
        "Usage: add_context.py [-t|-tr [-dN] PATTERN [ROOT]]...\n"
        "                      [-c|-cr [-dN] PATTERN [ROOT]]...\n"
        "                      [-ti|-tir PATTERN]... [-ci|-cir PATTERN]...\n\n"
        "Print selected repository paths as a tree and/or with contents.\n\n"
        "Options:\n"
        "  -t, --tree         Add matching paths to the tree section.\n"
        "  -c, --cat          Print matching files with their contents.\n"
        "  -ti, --tree-ignore Ignore files only for tree output.\n"
        "  -ci, --cat-ignore  Ignore files only for cat output.\n"
        "  -tr, -cr           Regex variants of -t and -c.\n"
        "  -tir, -cir         Regex variants of -ti and -ci.\n"
        "  -dN                Limit the preceding selector to depth N.\n"
        "  -h, --help         Show this help message and exit.\n\n"
        "Depth uses find-style levels: the selected root is depth 0.\n"
        "Example: -t -d1 . is equivalent to find . -maxdepth 1.\n\n"
        "Patterns can be literal paths, glob patterns including **, simple brace\n"
        "globs like src/*.{cpp,hpp}, or regular expressions matched against\n"
        "repo paths when no literal/glob match is found.\n\n"
        "Regex examples:\n"
        '  -tr "\\d+\\.txt" .\n'
        '  -cr "\\.py$" windows\n'
        '  -tir "(^|/)\\.venv/"\n\n'
        "Ignore patterns use gitignore-like rules unless --regex is passed. Examples:\n"
        "  -ti .venv/    ignore any .venv directory in tree output\n"
        "  -ci /.venv/   ignore the current directory's .venv in cat output\n"
        "  -ti *.py      ignore Python files at any level in tree output"
    )


def print_usage(stream) -> None:
    print(usage(), file=stream)


def parse_short_option(option: str) -> tuple[str, bool] | None:
    if not option.startswith("-") or option.startswith("--") or len(option) < 2:
        return None

    flags = option[1:]
    if flags == "h":
        return None
    if any(flag not in "tcir" for flag in flags):
        return None
    if len(set(flags)) != len(flags):
        return None
    if ("t" in flags) == ("c" in flags):
        return None

    mode = "tree" if "t" in flags else "cat"
    if "i" in flags:
        mode += "_ignore"
    return mode, "r" in flags


def parse_option(
    option: str, parsed: ParsedArgs
) -> tuple[list[PatternSpec], bool, bool] | None:
    short_option = parse_short_option(option)
    if short_option is not None:
        mode, regex = short_option
        short_options = {
            "tree": (parsed.tree, True, regex),
            "cat": (parsed.cat, True, regex),
            "tree_ignore": (parsed.tree_ignore, False, regex),
            "cat_ignore": (parsed.cat_ignore, False, regex),
        }
        return short_options[mode]

    return {
        "--tree": (parsed.tree, True, False),
        "--cat": (parsed.cat, True, False),
        "--tree-ignore": (parsed.tree_ignore, False, False),
        "--cat-ignore": (parsed.cat_ignore, False, False),
    }.get(option)


def is_option_token(token: str) -> bool:
    return (
        token in {"-r", "--regex", "-h", "--help"}
        or parse_depth_option(token) is not None
        or parse_short_option(token) is not None
        or token
        in {
            "--tree",
            "--cat",
            "--tree-ignore",
            "--cat-ignore",
        }
    )


def parse_depth_option(option: str) -> int | None:
    match = re.fullmatch(r"-d(\d+)", option)
    return int(match.group(1)) if match is not None else None


def parse_args(argv: list[str] | None = None) -> ParsedArgs:
    args = list(sys.argv[1:] if argv is None else argv)
    parsed = ParsedArgs(tree=[], cat=[], tree_ignore=[], cat_ignore=[])

    index = 0
    while index < len(args):
        option = args[index]
        if option in {"-h", "--help"}:
            print_usage(sys.stdout)
            raise SystemExit(0)

        parsed_option = parse_option(option, parsed)
        if parsed_option is None:
            print(f"add_context.py: unknown argument: {option}", file=sys.stderr)
            print_usage(sys.stderr)
            raise SystemExit(2)

        target, is_selector, regex = parsed_option
        index += 1

        max_depth = None
        if is_selector and index < len(args):
            max_depth = parse_depth_option(args[index])
            if max_depth is not None:
                index += 1

        if index >= len(args) or is_option_token(args[index]):
            print(f"add_context.py: missing value for {option}", file=sys.stderr)
            print_usage(sys.stderr)
            raise SystemExit(2)

        pattern = args[index]
        index += 1

        root = "."
        if (
            is_selector
            and regex
            and index < len(args)
            and not is_option_token(args[index])
        ):
            root = args[index]
            index += 1

        if not regex:
            pattern = normalize_input_path(
                pattern,
                preserve_trailing_slash=not is_selector,
            )
        root = normalize_input_path(root)

        if not is_selector and regex:
            target.append(PatternSpec(pattern, regex=True))
        else:
            target.append(
                PatternSpec(
                    pattern,
                    regex=regex,
                    root=root,
                    max_depth=max_depth,
                )
            )

    return parsed


def to_posix(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def normalize_input_path(path: str, preserve_trailing_slash: bool = False) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    is_root = normalized == "/" or re.fullmatch(r"[A-Za-z]:/", normalized) is not None
    if not preserve_trailing_slash and not is_root:
        normalized = normalized.rstrip("/")
    return normalized or "."


def expand_braces(pattern: str) -> list[str]:
    start = pattern.find("{")
    if start < 0:
        return [pattern]

    end = pattern.find("}", start + 1)
    if end < 0:
        return [pattern]

    prefix = pattern[:start]
    inner = pattern[start + 1 : end]
    suffix = pattern[end + 1 :]
    expanded: list[str] = []

    for part in inner.split(","):
        expanded.extend(expand_braces(f"{prefix}{part}{suffix}"))

    return expanded


def has_glob_magic(pattern: str) -> bool:
    return any(char in pattern for char in "*?[")


def parse_ignore_rule(spec: PatternSpec) -> IgnoreSpec | None:
    pattern = spec.pattern.strip()
    if not pattern or pattern.startswith("#"):
        return None

    negated = False
    if pattern.startswith(("\\#", "\\!")):
        pattern = pattern[1:]
    elif pattern.startswith("!"):
        negated = True
        pattern = pattern[1:]

    if spec.regex:
        try:
            return RegexIgnoreRule(re.compile(pattern), negated)
        except re.error:
            return None

    pattern = normalize_input_path(pattern, preserve_trailing_slash=True)
    anchored = pattern.startswith("/")
    pattern = pattern.lstrip("/")
    directory_only = pattern.endswith("/")
    pattern = pattern.rstrip("/")

    if not pattern:
        return None

    basename_only = "/" not in pattern
    return IgnoreRule(
        pattern=pattern,
        anchored=anchored,
        basename_only=basename_only,
        directory_only=directory_only,
        negated=negated,
    )


def compile_ignore_rules(patterns: list[PatternSpec]) -> list[IgnoreSpec]:
    rules: list[IgnoreSpec] = []
    for pattern in patterns:
        rule = parse_ignore_rule(pattern)
        if rule is not None:
            rules.append(rule)
    return rules


def candidate_paths(relative_path: str) -> list[str]:
    parts = [part for part in relative_path.split("/") if part]
    return ["/".join(parts[:index]) for index in range(1, len(parts) + 1)]


def gitignore_match(rule: IgnoreRule, candidate: str) -> bool:
    if rule.basename_only:
        if rule.anchored:
            return fnmatch.fnmatchcase(candidate, rule.pattern)
        return fnmatch.fnmatchcase(candidate.rsplit("/", 1)[-1], rule.pattern)

    return re.fullmatch(gitignore_regex(rule.pattern), candidate) is not None


def gitignore_regex(pattern: str) -> str:
    result: list[str] = []
    index = 0

    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                index += 2
                if index < len(pattern) and pattern[index] == "/":
                    result.append("(?:.*/)?")
                    index += 1
                else:
                    result.append(".*")
                continue
            result.append("[^/]*")
        elif char == "?":
            result.append("[^/]")
        elif char == "[":
            end = index + 1
            if end < len(pattern) and pattern[end] == "!":
                end += 1
            if end < len(pattern) and pattern[end] == "]":
                end += 1
            while end < len(pattern) and pattern[end] != "]":
                end += 1
            if end >= len(pattern):
                result.append("\\[")
            else:
                content = pattern[index + 1 : end]
                if content.startswith("!"):
                    content = "^" + content[1:]
                result.append(f"[{content}]")
                index = end
        else:
            result.append(re.escape(char))
        index += 1

    return "".join(result)


def is_ignored(path: Path, is_dir: bool, rules: list[IgnoreSpec]) -> bool:
    relative_path = to_posix(path)
    if (
        relative_path == ".git"
        or relative_path.startswith(".git/")
        or "/.git/" in relative_path
    ):
        return True

    ignored = False
    candidates = candidate_paths(relative_path)
    if not candidates:
        return False

    for rule in rules:
        if isinstance(rule, RegexIgnoreRule):
            trailing_candidates = [
                f"{candidate}/"
                for candidate in candidates
                if is_dir or candidate != relative_path
            ]
            paths_to_test = candidates + trailing_candidates
            if any(rule.regex.search(candidate) for candidate in paths_to_test):
                ignored = not rule.negated
            continue

        paths_to_test = (
            candidates if not rule.directory_only or is_dir else candidates[:-1]
        )
        if any(gitignore_match(rule, candidate) for candidate in paths_to_test):
            ignored = not rule.negated

    return ignored


def resolve_path(pattern: str) -> Path:
    path = Path(pattern)
    if path.is_absolute():
        return path
    return ROOT / path


def glob_matches(pattern: str) -> list[Path]:
    path = Path(pattern)
    if path.is_absolute():
        return [Path(match) for match in glob.glob(pattern, recursive=True)]

    return list(ROOT.glob(pattern.replace("\\", "/")))


def iter_repo_items(
    root: Path, rules: list[IgnoreSpec], max_depth: int | None = None
) -> list[Path]:
    items: list[Path] = []
    if root.is_file():
        return [root] if not is_ignored(root, False, rules) else []

    for current_root, dirnames, filenames in os.walk(root):
        current = Path(current_root)
        current_depth = len(current.resolve().relative_to(root.resolve()).parts)
        if max_depth is not None and current_depth >= max_depth:
            dirnames.clear()
            continue

        dirnames[:] = sorted(
            dirname
            for dirname in dirnames
            if dirname != ".git" and not is_ignored(current / dirname, True, rules)
        )
        for dirname in dirnames:
            items.append(current / dirname)
        for filename in sorted(filenames):
            file_path = current / filename
            if not is_ignored(file_path, False, rules):
                items.append(file_path)
    return items


def get_pattern_matches(
    pattern: str,
    rules: list[IgnoreSpec],
    max_depth: int | None = None,
) -> list[Match]:
    matches: list[Match] = []
    found = False

    for expanded in expand_braces(pattern):
        literal = resolve_path(expanded)
        if literal.exists():
            matches.append(Match(literal, normalize_input_path(expanded)))
            found = True

        if has_glob_magic(expanded):
            for item in glob_matches(expanded):
                matches.append(Match(item, to_posix(item)))
                found = True

    if found:
        return matches

    try:
        regex = re.compile(pattern)
    except re.error:
        return []

    for item in iter_repo_items(ROOT, rules, max_depth):
        relative_path = to_posix(item)
        if regex.search(relative_path):
            matches.append(Match(item, relative_path))

    return matches


def get_regex_matches(
    pattern: str,
    root: str,
    rules: list[IgnoreSpec],
    max_depth: int | None = None,
) -> list[Match]:
    try:
        regex = re.compile(pattern)
    except re.error:
        return []

    search_root = resolve_path(root)
    if not search_root.exists() or is_ignored(search_root, search_root.is_dir(), rules):
        return []

    matches: list[Match] = []
    for item in iter_repo_items(search_root, rules, max_depth):
        relative_path = to_posix(item)
        if regex.search(relative_path):
            matches.append(Match(item, relative_path))

    return matches


def child_display_path(display_root: str, root_path: Path, child_path: Path) -> str:
    child_relative = child_path.resolve().relative_to(root_path.resolve()).as_posix()
    display_root = display_root.replace("\\", "/").rstrip("/")
    if not display_root or display_root == ".":
        return child_relative
    return f"{display_root}/{child_relative}"


def iter_items_under(
    directory: Path,
    display_root: str,
    rules: list[IgnoreSpec],
    max_depth: int | None = None,
    include_directories: bool = False,
) -> list[Match]:
    items: list[Match] = []
    for current_root, dirnames, filenames in os.walk(directory):
        current = Path(current_root)
        current_depth = len(current.resolve().relative_to(directory.resolve()).parts)
        if max_depth is not None and current_depth >= max_depth:
            dirnames.clear()
            continue

        dirnames[:] = sorted(
            dirname
            for dirname in dirnames
            if dirname != ".git" and not is_ignored(current / dirname, True, rules)
        )
        if include_directories:
            for dirname in dirnames:
                directory_path = current / dirname
                items.append(
                    Match(
                        directory_path,
                        child_display_path(display_root, directory, directory_path),
                    )
                )
        for filename in sorted(filenames):
            file_path = current / filename
            if not is_ignored(file_path, False, rules):
                items.append(
                    Match(
                        file_path,
                        child_display_path(display_root, directory, file_path),
                    )
                )
    return items


def get_matching_items(
    spec: PatternSpec,
    rules: list[IgnoreSpec],
    include_directories: bool = False,
) -> list[Match]:
    include_directories = include_directories and spec.max_depth is not None
    items: list[Match] = []
    matches = (
        get_regex_matches(spec.pattern, spec.root, rules, spec.max_depth)
        if spec.regex
        else get_pattern_matches(spec.pattern, rules, spec.max_depth)
    )
    for match in matches:
        path = match.path
        if not path.exists() or is_ignored(path, path.is_dir(), rules):
            continue
        if path.is_dir():
            if include_directories and match.display_path != ".":
                items.append(match)

            remaining_depth = spec.max_depth
            if spec.regex and remaining_depth is not None:
                search_root = resolve_path(spec.root).resolve()
                match_depth = len(path.resolve().relative_to(search_root).parts)
                remaining_depth -= match_depth

            items.extend(
                iter_items_under(
                    path,
                    match.display_path,
                    rules,
                    remaining_depth,
                    include_directories,
                )
            )
        elif path.is_file():
            items.append(Match(path, match.display_path))
    return items


def dedupe_key(path: Path) -> str:
    resolved = path.resolve().as_posix()
    return resolved.casefold() if os.name == "nt" else resolved


def collect(
    patterns: list[PatternSpec],
    rules: list[IgnoreSpec],
    include_directories: bool = False,
) -> list[Match]:
    seen: set[str] = set()
    results: list[Match] = []
    for pattern in patterns:
        for match in get_matching_items(pattern, rules, include_directories):
            key = dedupe_key(match.path)
            if key not in seen:
                seen.add(key)
                results.append(match)
    return results


def render_tree(paths: list[str]) -> None:
    parent_paths = {
        "/".join(parts[:index])
        for path in paths
        for parts in [path.split("/")]
        for index in range(1, len(parts))
    }
    seen_dirs: set[str] = set()
    for path in paths:
        if path in parent_paths:
            continue
        parts = path.split("/")
        for index in range(len(parts) - 1):
            directory = "/".join(parts[: index + 1])
            if directory in seen_dirs:
                continue
            seen_dirs.add(directory)
            if index == 0:
                print(parts[index])
            else:
                print(f"{'|   ' * (index - 1)}|-- {parts[index]}")

        if len(parts) == 1:
            print(parts[0])
        else:
            print(f"{'|   ' * (len(parts) - 2)}|-- {parts[-1]}")


def main() -> int:
    args = parse_args()
    tree_rules = compile_ignore_rules(args.tree_ignore)
    cat_rules = compile_ignore_rules(args.cat_ignore)

    tree_files = collect(args.tree, tree_rules, include_directories=True)
    cat_files = collect(args.cat, cat_rules)

    if tree_files:
        render_tree(sorted({match.display_path for match in tree_files}))

    if tree_files and cat_files:
        print()

    for match in cat_files:
        if not match.path.is_file():
            continue
        print(f"### {match.display_path}")
        try:
            print(match.path.read_text(encoding="utf-8"), end="")
        except UnicodeDecodeError:
            print(match.path.read_text(errors="replace"), end="")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
