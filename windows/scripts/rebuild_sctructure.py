import argparse
import os
import re
import shutil
import uuid

link_re = re.compile(r"\[\[([^]]+)]]")
invalid_chars = set('\\/:*?"<>|\n\r\t')


def is_valid_filename(name: str) -> bool:
    return bool(name) and not any(c in invalid_chars for c in name)


def collect_md_files(root: str) -> list[str]:
    md_files = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [directory for directory in dirs if directory != ".obsidian"]
        for name in files:
            if name.endswith(".md"):
                md_files.append(os.path.join(dirpath, name))
    return md_files


def extract_final_link(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None

    last_line = lines[-1]
    matches = link_re.findall(last_line)

    if len(matches) != 1:
        return None

    name = matches[0].split("|", 1)[0]
    return name if is_valid_filename(name) else None


def build_title_map(md_files: list[str]) -> dict[str, str]:
    return {
        os.path.abspath(path): os.path.splitext(os.path.basename(path))[0]
        for path in md_files
    }


def build_parents(
    md_files: list[str],
) -> tuple[dict[str, str | None], dict[str, str | None], dict[str, set[str]]]:
    file_parent = {}
    title_parent = {}
    children_titles = {}

    for path in md_files:
        abs_path = os.path.abspath(path)

        with open(abs_path, "r", encoding="utf-8", errors="ignore") as file:
            text = file.read()

        title = os.path.splitext(os.path.basename(abs_path))[0]

        if "#unfinished" in text:
            parent = None
        else:
            parent = extract_final_link(text)
            if not parent or parent == title:
                parent = None

        file_parent[abs_path] = parent

        if title not in title_parent:
            title_parent[title] = parent

        if parent:
            children_titles.setdefault(parent, set()).add(title)

    return file_parent, title_parent, children_titles


def build_chain_for_file(
    abs_path: str,
    file_parent: dict[str, str | None],
    title_parent: dict[str, str | None],
) -> list[str]:
    chain = []
    current = file_parent.get(abs_path)

    while current:
        chain.append(current)
        current = title_parent.get(current)

    chain.reverse()
    return chain


def move_all_safely(moves: list[tuple[str, str]]) -> None:
    tag = f".__swap__{uuid.uuid4().hex}__"
    tmp_moves = []
    src_name_map = {}

    for src, dst in moves:
        if src == dst:
            continue

        src_tmp = src + tag
        os.replace(src, src_tmp)
        tmp_moves.append((src_tmp, dst))
        src_name_map[src_tmp] = src

    for src_tmp, dst in tmp_moves:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        print(f"{src_name_map[src_tmp]} -> {dst}")
        shutil.move(src_tmp, dst)


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

    root = os.path.abspath(args.root)
    md_files = collect_md_files(root)

    path_to_title = build_title_map(md_files)
    file_parent, title_parent, children_titles = build_parents(md_files)

    moves = []

    for src_abs, title in path_to_title.items():
        chain = build_chain_for_file(src_abs, file_parent, title_parent)

        if title in children_titles:
            rel = (
                os.path.join(*chain, title, title + ".md")
                if chain
                else os.path.join(title, title + ".md")
            )
        else:
            rel = os.path.join(*chain, title + ".md") if chain else title + ".md"

        dst_abs = os.path.abspath(os.path.join(root, rel))

        if src_abs != dst_abs and "Template.md" not in src_abs:
            moves.append((src_abs, dst_abs))

    move_all_safely(moves)


if __name__ == "__main__":
    main()