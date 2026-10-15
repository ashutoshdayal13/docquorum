"""Replay the three documented checks from bundled inputs, without inference."""
from pathlib import Path
from types import SimpleNamespace
import copy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
import pymupdf
from docquorum.checks import blank_boxes, copied_rows, printed_numbers


def read(path):
    return json.loads(path.read_text())


def main():
    for folder, check in [("check_blank_box", blank_boxes),
                          ("check_printed_precision", printed_numbers),
                          ("checks_pueblo", copied_rows)]:
        path = ROOT / "examples" / folder
        plain = ""
        if folder == "check_printed_precision":
            with pymupdf.open(path / "source.pdf") as pdf:
                plain = "\n".join(p.get_text(sort=True) for p in pdf)
        doc = SimpleNamespace(schema=read(path / "schema.json"), plain=plain)
        actual = check.apply(copy.deepcopy(read(path / "before.json")), doc)
        assert actual == read(path / "after.json"), f"Replay differs: {folder}"
        print(f"Verified {folder}: complete before/after replay")
    for file, expected in read(ROOT / "example-hashes.json").items():
        assert hashlib.sha256((ROOT / file).read_bytes()).hexdigest() == expected, file
    print("Verified bundled example hashes")


if __name__ == "__main__":
    main()
