"""
    python -m docquorum.checks <primary|parse|oneshot|layout> <split> <in_dir> <out_dir>

Runs one chain over every reading in in_dir (<name>.json per document of the split).
"""
import json
import sys
from pathlib import Path

from docquorum.checks import Doc, run
from docquorum.extractbench import load_records, name_of, pdf_of

kind, split, src, dst = sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
dst.mkdir(parents=True, exist_ok=True)
n = 0
for rec in load_records(split):
    f = src / f"{name_of(rec)}.json"
    if f.exists():
        doc = Doc(rec["data_schema"], pdf_of(rec), name_of(rec))
        (dst / f.name).write_text(json.dumps(run(kind, json.loads(f.read_text()), doc)))
        n += 1
print(f"checks ({kind}): {src} -> {dst} ({n} documents)")
