import argparse
import os
import uuid

parser = argparse.ArgumentParser()
parser.add_argument("path")
parser.add_argument("--prefix", default="")
args = parser.parse_args()

dir_path = os.path.abspath(args.path)
base_prefix = f"{args.prefix}_" if args.prefix else ""

files = [
    name
    for name in sorted(os.listdir(dir_path))
    if os.path.isfile(os.path.join(dir_path, name))
]

temp_files = []

for name in files:
    src = os.path.join(dir_path, name)
    tmp_name = f"{uuid.uuid4().hex}{os.path.splitext(name)[1]}"
    tmp = os.path.join(dir_path, tmp_name)
    os.rename(src, tmp)
    temp_files.append(tmp)

for i, tmp in enumerate(temp_files, start=1):
    dst = os.path.join(dir_path, f"{base_prefix}{i:03d}.png")
    os.rename(tmp, dst)
