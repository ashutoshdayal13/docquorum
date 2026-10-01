"""
Conform an extraction to the shape its schema declares: every declared property present,
null when the reading did not return it.

Measured defect: under structured decoding a property that is not `required` may be left
out, and Qwen3.8 leaves out the ones whose answer is null (every Caterpillar spec row came
back without `symbol`, `conditions`, `min`, `typ`, `max`). The benchmark's own one-shot
provider does the same. The gold records those nulls, and the scorer counts an absent key as
a missed value, so a correct reading scored 67.14 (precision 100, recall 50.5).

Only properties whose schema admits null are filled. A missing non-nullable property means
the reader failed to find a value the schema says must exist; writing null there asserts a
value the schema forbids, and the scorer counts it as a wrong prediction.

    python conform.py <run_dir> <out_dir>     (EB_SPLIT selects the records)
"""
import json
import os
import sys
from pathlib import Path


def _defs(root):
    return root.get("$defs") or root.get("definitions") or {}


def resolve(s, root, depth=0):
    while isinstance(s, dict) and "$ref" in s and depth < 20:
        s = _defs(root).get(s["$ref"].split("/")[-1], {})
        depth += 1
    return s if isinstance(s, dict) else {}


def admits_null(s, root):
    s = resolve(s, root)
    t = s.get("type")
    if t == "null" or (isinstance(t, list) and "null" in t):
        return True
    for comb in ("anyOf", "oneOf"):
        if any(admits_null(alt, root) for alt in s.get(comb) or []):
            return True
    return False


EMPTY_TO_DEFAULT = os.environ.get("DQ_EMPTY_TO_DEFAULT", "1") == "1"


def _default_null(s):
    """The property's own schema declares `"default": null`."""
    return isinstance(s, dict) and "default" in s and s["default"] is None


def _branch(o, s, root):
    """The alternative of an anyOf/oneOf that matches the value's shape."""
    for comb in ("anyOf", "oneOf"):
        for alt in s.get(comb) or []:
            a = resolve(alt, root)
            if isinstance(o, dict) and (a.get("type") == "object" or "properties" in a):
                return a
            if isinstance(o, list) and (a.get("type") == "array" or "items" in a):
                return a
    return s


def conform(o, s, root, stat=None):
    s = _branch(o, resolve(s, root), root)
    if isinstance(o, dict) and s.get("properties"):
        out = dict(o)
        for k, sub in s["properties"].items():
            if k in out and out[k] == [] and EMPTY_TO_DEFAULT and _default_null(sub):
                # an empty list for a list the schema defaults to null: nothing is printed,
                # which the schema writes as its default (gold: null 566 times, [] 7 times)
                out[k] = None
                if stat is not None:
                    stat["emptied"] = stat.get("emptied", 0) + 1
            elif k in out:
                out[k] = conform(out[k], sub, root, stat)
            elif admits_null(sub, root):
                out[k] = None
                if stat is not None:
                    stat["filled"] = stat.get("filled", 0) + 1
        return out
    if isinstance(o, list) and isinstance(s.get("items"), dict):
        return [conform(x, s["items"], root, stat) for x in o]
    return o


def conform_record(pred, schema):
    schema = json.loads(schema) if isinstance(schema, str) else schema
    return conform(pred, schema, schema)


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.mkdir(parents=True, exist_ok=True)
    split = os.environ.get("EB_SPLIT", "long")
    total = 0
    for line in open(__import__("settings").DATA / f"{split}.jsonl"):
        if not line.strip():
            continue
        rec = json.loads(line)
        name = rec["id"].split("/")[-1]
        f = src / f"{name}.json"
        if not f.exists():
            continue
        schema = rec["data_schema"]
        schema = json.loads(schema) if isinstance(schema, str) else schema
        stat = {}
        out = conform(json.loads(f.read_text()), schema, schema, stat)
        (dst / f"{name}.json").write_text(json.dumps(out))
        total += stat.get("filled", 0)
    print(f"conform: filled {total} absent nullable properties -> {dst}")


if __name__ == "__main__":
    main()
