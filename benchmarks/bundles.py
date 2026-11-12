import json
from pathlib import Path


def write(path, items):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as fh:
        for key in sorted(items):
            fh.write(json.dumps({"id": key, "data": items[key]}, ensure_ascii=False) + "\n")
    tmp.replace(path)


def read(path):
    path = Path(path)
    if path.is_dir():
        return {f.stem: json.loads(f.read_text()) for f in sorted(path.glob("*.json"))}
    out = {}
    with path.open() as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                out[row["id"]] = row["data"]
    return out
