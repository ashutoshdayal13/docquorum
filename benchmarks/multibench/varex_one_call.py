"""
VAREX with the benchmark's own one-call protocol and Qwen3.8-27B: the same model as DocQuorum,
called once per form, as the published systems were run. It is the baseline that shows what the
pipeline adds (as the benchmark's one-shot protocol is for UNIKIE-BENCH, and the leaderboard's
own Qwen3.8 27B run is for ExtractBench).

The protocol is the benchmark's example_inference.py, image modality: its system prompt with the
form's schema text, the form image as a PNG, temperature 0, a JSON-object reply; a reply that is
not JSON is saved as an error and scores as empty. Qwen3.8's reasoning is off, as in every run of
this repository. Scored with the benchmark's own evaluation/score.py and field exclusions.

    python benchmarks/multibench/varex_one_call.py run      (resumes)
    python benchmarks/multibench/varex_one_call.py score
"""
import base64
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import frozen27b as F  # noqa: E402
from docquorum import config as C  # noqa: E402
from docquorum.tools import llm  # noqa: E402

F.VARIANT = "one_call"
OUT = F.out_dir("varex") / "views" / "one_call"
# example_inference.py, SYSTEM_PROMPT (VAREX-Bench, image modality)
SYSTEM_PROMPT = """Extract structured data from this document.
Return a JSON object matching this schema:

{schema}

Return null for fields you cannot find.
Return ONLY valid JSON.
Return an instance of the JSON with extracted values, not the schema itself."""


def read(cl, name, image, schema_text):
    out = OUT / f"{name}.json"
    if out.exists():
        return
    url = "data:image/png;base64," + base64.b64encode(image.read_bytes()).decode()
    content = ""
    try:
        r = cl.chat.completions.create(
            model=C.MODEL, temperature=0, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": SYSTEM_PROMPT.format(schema=schema_text)},
                      {"role": "user", "content": [{"type": "image_url", "image_url": {"url": url, "detail": "high"}}]}],
            extra_body={"chat_template_kwargs": {"enable_thinking": False}})
        content = r.choices[0].message.content
        pred = json.loads(content)
    except json.JSONDecodeError:
        pred = {"_error": "Invalid JSON", "_raw": (content or "")[:500]}
    except Exception as e:
        pred = {"_error": str(e)[:300]}
    F.write(out, pred)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    cl = llm.client(timeout=1800)
    jobs = [(name, image, image.parent / "schema.json") for name, image, _, _ in F.varex_inputs()]
    with ThreadPoolExecutor(max_workers=16) as ex:
        for i, _ in enumerate(ex.map(lambda j: read(cl, j[0], j[1], j[2].read_text()), jobs), 1):
            if i % 100 == 0:
                print(f"{i}/{len(jobs)}", flush=True)
    print("done", sum(1 for _ in OUT.glob("*.json")), "forms")


if __name__ == "__main__":
    {"run": run, "score": lambda: F.varex_score(views=("one_call",))}[sys.argv[1]]()
