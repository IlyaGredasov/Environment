import argparse
import math
import pathlib
import re

YAML_LANGUAGE = "yaml"

try:
    from yamlfix import fix_code
    from yamlfix.model import YamlfixConfig
except ImportError:
    fix_code = None
    YamlfixConfig = None


def normalize_indent(line: str, tab_size: int = 4) -> str:
    match = re.match(r"^([ \t]+)", line)
    if not match:
        return line

    prefix = match.group(1)
    spaces = prefix.count(" ")
    tabs = prefix.count("\t")

    width = spaces + tabs * tab_size
    new_tabs = math.ceil(width / tab_size)

    return "\t" * new_tabs + line[len(prefix) :]


def leading_width(line: str, tab_size: int = 4) -> int:
    match = re.match(r"^([ \t]+)", line)
    if not match:
        return 0

    prefix = match.group(1)
    return prefix.count(" ") + prefix.count("\t") * tab_size


def normalize_yaml_indents(lines: list[str], tab_size: int = 4, indent_size: int = 2) -> list[str]:
    widths = [leading_width(line, tab_size) for line in lines if line.strip()]
    positive_widths = [width for width in widths if width > 0]

    if not positive_widths:
        return lines

    indent_unit = positive_widths[0]
    for width in positive_widths[1:]:
        indent_unit = math.gcd(indent_unit, width)

    if indent_unit == 0:
        return lines

    normalized_lines = []
    for line in lines:
        if not line.strip():
            normalized_lines.append(line)
            continue

        match = re.match(r"^([ \t]+)", line)
        if not match:
            normalized_lines.append(line)
            continue

        width = leading_width(line, tab_size)
        levels = max(1, round(width / indent_unit))
        normalized_lines.append(" " * (levels * indent_size) + line[len(match.group(1)) :])

    return normalized_lines


def parse_code_language(line: str) -> str:
    info = line.strip()[3:].strip()
    if not info:
        return ""

    return info.split(maxsplit=1)[0].lower()


def has_explicit_yaml_start(source: str) -> bool:
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        return stripped == "---" or stripped.startswith("--- ")

    return False


def format_yaml_block(lines: list[str]) -> list[str]:
    if not any(line.strip() for line in lines):
        return lines

    if fix_code is None or YamlfixConfig is None:
        raise RuntimeError("yamlfix is required to format ```yaml code blocks")

    source = "\n".join(normalize_yaml_indents(lines))
    config = YamlfixConfig(
        explicit_start=has_explicit_yaml_start(source),
        preserve_quotes=True,
        line_length=999,
    )

    try:
        fixed = fix_code(source, config=config)
    except Exception:
        return lines

    return fixed.splitlines()


def format_code_block(lines: list[str], language: str) -> list[str]:
    if language == YAML_LANGUAGE:
        return format_yaml_block(lines)

    return [normalize_indent(line) for line in lines]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=r"D:\KnowledgeBase",
        help="Path to Obsidian knowledge base root",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = pathlib.Path(args.root)

    for path in root.rglob("*.md"):
        if any(part == ".obsidian" for part in path.parts):
            continue

        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        keep_newline = raw.endswith("\n")

        new_lines = []
        in_code = False
        code_language = ""
        code_lines = []

        for line in lines:
            if line.strip().startswith("```"):
                if in_code:
                    new_lines.extend(format_code_block(code_lines, code_language))
                    code_lines = []
                    code_language = ""
                else:
                    code_language = parse_code_language(line)

                in_code = not in_code
                new_lines.append(line)
                continue

            if in_code:
                code_lines.append(line)
            else:
                new_lines.append(line)

        if in_code:
            new_lines.extend(format_code_block(code_lines, code_language))

        result = "\n".join(new_lines)

        if keep_newline:
            result += "\n"

        path.write_text(result, encoding="utf-8")


if __name__ == "__main__":
    main()
