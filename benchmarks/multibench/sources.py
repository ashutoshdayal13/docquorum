"""
The three benchmarks run by run.py: where their data is, how their inputs are prepared, and
their own scorers. Inference sees only the prepared inputs (document and schema); the answer keys
are read by the scorers alone.

    VAREX              ibm-research/VAREX (Hugging Face) in data/multibench_sources/varex_data,
                       its evaluation code (github.com/udibarzi/varex-bench) in data/multibench_sources/varex
    LongArray-Extract  Extend AI's dataset in data/multibench_sources/longarray
    DocuBench          github.com/DocuPipe/DocuBench in data/multibench_sources/docubench

    python benchmarks/multibench/sources.py prepare varex | longarray
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "multibench_sources"
INPUTS = ROOT / "data" / "multibench"                  # prepared inputs (not in the repository)
MANIFESTS = Path(__file__).resolve().parent / "manifests"

VAREX_DATA, VAREX_SOURCE = SRC / "varex_data", SRC / "varex"
VAREX_REVISION = "2dfc3386a4567c7d56bf1abf4d12ff42afed27b6"
LONGARRAY = SRC / "longarray"
LONGARRAY_REVISION = "f2ae30264ecd942fa0a9b9e787bb42e1e2577184"
DOCUBENCH = SRC / "docubench"
DOCUBENCH_COMMIT = "43a3f3bc00e591e711075678ca6d154acfedcf42"


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else Path(data).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n")
    tmp.replace(path)


def load_module(name, path):
    if not Path(path).exists():
        raise FileNotFoundError(f"{path}: the benchmark's own code is not downloaded (see the docstring of sources.py)")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---- VAREX --------------------------------------------------------------------------------------

def varex_rows(columns):
    import pyarrow.parquet as pq
    for path in sorted((VAREX_DATA / "data").glob("*.parquet")):
        yield from pq.read_table(path, columns=columns).to_pylist()


def varex_prepare():
    """Each form's image and schema text, as the dataset ships them; no answer key."""
    records = []
    for row in varex_rows(["doc_id", "split", "image", "schema"]):
        dst = INPUTS / "varex" / row["doc_id"]
        dst.mkdir(parents=True, exist_ok=True)
        (dst / "image.png").write_bytes(row["image"]["bytes"])
        (dst / "schema.json").write_text(row["schema"])
        records.append({"id": row["doc_id"], "split": row["split"], "image_sha256": sha(row["image"]["bytes"]),
                        "schema_sha256": sha(row["schema"].encode())})
    expected = json.loads((VAREX_SOURCE / "evaluation/manifest.json").read_text())
    if set(expected.get("active_doc_ids") or expected.get("doc_ids") or []) != {r["id"] for r in records}:
        raise ValueError("the dataset and the benchmark's own manifest list different forms")
    write(MANIFESTS / "varex.json", {"dataset": "ibm-research/VAREX", "revision": VAREX_REVISION, "track": "image_only",
                                     "docs": sorted(records, key=lambda r: r["id"]),
                                     "excluded_inputs": ["ground_truth", "text_flow", "text_layout", "image_50dpi"]})
    print(f"VAREX: {len(records)} forms prepared")


def varex_inputs():
    for r in json.loads((MANIFESTS / "varex.json").read_text())["docs"]:
        d = INPUTS / "varex" / r["id"]
        img, sch = d / "image.png", d / "schema.json"
        if sha(img) != r["image_sha256"] or sha(sch) != r["schema_sha256"]:
            raise ValueError(f"input changed: {r['id']}")
        yield r["id"], img, json.loads(sch.read_text()), None


def varex_scorer():
    return load_module("varex_official_score", VAREX_SOURCE / "evaluation/score.py")


# ---- LongArray-Extract ----------------------------------------------------------------------------

def longarray_rows(vertical, columns):
    import pyarrow.parquet as pq
    for path in sorted((LONGARRAY / vertical).glob("*.parquet")):
        yield from pq.read_table(path, columns=columns).to_pylist()


def longarray_prepare():
    """Each document's PDF and its vertical's schema; no answer key, target count or page map."""
    records = []
    for vertical in ("clinical", "financial", "legal"):
        schema = LONGARRAY / "schemas" / f"{vertical}.json"
        for row in longarray_rows(vertical, ["document_id", "pdf"]):
            doc = INPUTS / "longarray" / vertical / f"{row['document_id']}.pdf"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_bytes(row["pdf"]["bytes"])
            records.append({"id": row["document_id"], "vertical": vertical, "pdf": str(doc.relative_to(ROOT)),
                            "schema": str(schema.relative_to(ROOT)), "source_sha256": sha(doc), "schema_sha256": sha(schema)})
    write(MANIFESTS / "longarray.json", {"dataset_revision": LONGARRAY_REVISION, "docs": sorted(records, key=lambda r: r["id"]),
                                         "excluded_inputs": ["ground_truth", "target_count", "target_field", "metadata"]})
    print(f"LongArray-Extract: {len(records)} documents prepared")


def longarray_inputs():
    for r in json.loads((MANIFESTS / "longarray.json").read_text())["docs"]:
        pdf, sch = ROOT / r["pdf"], ROOT / r["schema"]
        if sha(pdf) != r["source_sha256"] or sha(sch) != r["schema_sha256"]:
            raise ValueError(f"input changed: {r['id']}")
        yield r["id"], pdf, json.loads(sch.read_text()), None


def longarray_scorer():
    """The publisher's reference implementation, run verbatim from its dataset card:
    (score_document, FUZZY, sha256 of the code)."""
    readme = (LONGARRAY / "README.md").read_text()
    code = readme.split("### Reference implementation", 1)[1].split("```python\n", 1)[1].split("```", 1)[0]
    module = {"__name__": "longarray_official_reference"}
    exec(compile(code, str(LONGARRAY / "README.md") + ":reference", "exec"), module)
    return module["score_document"], module["FUZZY"], hashlib.sha256(code.encode()).hexdigest()


# ---- DocuBench --------------------------------------------------------------------------------------

def docubench_inputs():
    """Every document with its schema; the task text is the document's guideline, which DocuBench
    appends to every system's prompt."""
    for doc in sorted((DOCUBENCH / "documents").iterdir()):
        guideline = DOCUBENCH / "guidelines" / f"{doc.stem}.txt"
        task = guideline.read_text().strip() if guideline.exists() else None
        yield doc.stem, doc, json.loads((DOCUBENCH / "schemas" / f"{doc.stem}.json").read_text()), task or None


def docubench_scorer():
    return load_module("docubench_scorer", DOCUBENCH / "scorer.py")


INPUT_LISTS = {"varex": varex_inputs, "longarray": longarray_inputs, "docubench": docubench_inputs}

if __name__ == "__main__":
    if sys.argv[1:2] != ["prepare"] or sys.argv[2:3] not in (["varex"], ["longarray"]):
        raise SystemExit(__doc__)
    {"varex": varex_prepare, "longarray": longarray_prepare}[sys.argv[2]]()
