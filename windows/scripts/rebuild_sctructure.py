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


def build_parents(
    md_files: list[str],
) -> dict[str, str | None]:
    file_parent = {}

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

    return file_parent


def build_chains(
    file_parent: dict[str, str | None],
) -> tuple[dict[str, list[str]], set[str]]:
    title_paths = {}
    for path in file_parent:
        title = os.path.splitext(os.path.basename(path))[0]
        title_paths.setdefault(title, []).append(path)

    chains = {}
    resolved_parents = {}

    def resolve(path: str, visiting: set[str]) -> list[str] | None:
        if path in chains:
            return chains[path]
        if path in visiting:
            return None

        parent_title = file_parent[path]
        if not parent_title:
            chains[path] = []
            return chains[path]

        candidates = []
        for candidate_path in title_paths.get(parent_title, []):
            candidate_chain = resolve(candidate_path, visiting | {path})
            if candidate_chain is not None:
                candidates.append((candidate_chain + [parent_title], candidate_path))

        if not candidates:
            chains[path] = [parent_title]
            return chains[path]

        chain, parent_path = min(
            candidates,
            key=lambda item: (len(item[0]), os.path.normcase(item[1])),
        )
        chains[path] = chain
        resolved_parents[path] = parent_path
        return chain

    for path in file_parent:
        resolve(path, set())

    return chains, set(resolved_parents.values())


def build_relative_path(title: str, chain: list[str], has_children: bool) -> str:
    parts = chain + ([title] if has_children else []) + [title + ".md"]
    return os.path.join(*parts)


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

    file_parent = build_parents(md_files)
    chains, referenced_paths = build_chains(file_parent)

    moves = []

    for src_abs, chain in chains.items():
        title = os.path.splitext(os.path.basename(src_abs))[0]
        rel = build_relative_path(title, chain, src_abs in referenced_paths)

        dst_abs = os.path.abspath(os.path.join(root, rel))

        if src_abs != dst_abs and "Template.md" not in src_abs:
            moves.append((src_abs, dst_abs))

    move_all_safely(moves)


if __name__ == "__main__":
    main()
