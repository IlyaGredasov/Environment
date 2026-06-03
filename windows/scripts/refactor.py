import argparse
import math
import pathlib
import re


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

        for line in lines:
            if line.strip().startswith("```"):
                in_code = not in_code
                new_lines.append(line)
                continue

            if in_code:
                new_lines.append(normalize_indent(line))
            else:
                new_lines.append(line)

        result = "\n".join(new_lines)

        if keep_newline:
            result += "\n"

        path.write_text(result, encoding="utf-8")


if __name__ == "__main__":
    main()
