import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument("path")
parser.add_argument("--prefix", required=True)
args = parser.parse_args()

dir_path = os.path.abspath(args.path)

for i, name in enumerate(sorted(os.listdir(dir_path)), start=1):
    src = os.path.join(dir_path, name)
    if os.path.isfile(src):
        dst = os.path.join(dir_path, f"{args.prefix}_{i:03d}.png")
        os.rename(src, dst)
