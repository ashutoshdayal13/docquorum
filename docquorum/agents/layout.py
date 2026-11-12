import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from docquorum import ablate, config as C
from docquorum import extractbench as EB
from docquorum.agents import column_reader, ruled_reader
from docquorum.tools import llm, parser, pdf as PDF
from docquorum.tools.layout import convert_tables, is_column_flow, table_rows
from docquorum.tools.schema import find_array_field


RULED_MIN_ROWS = 5


def rules_missing(ev, pages_seen):
    pages = ev.get("table_pages") or []
    return bool(pages) and sum(pages_seen.get(p, 0) == 0 for p in pages) > len(pages) / 2


def decide(schema, pdf, name):
    n = PDF.npages(pdf)
    ev = {"pages": n, "text_layer": PDF.pdf_has_text(pdf, n)}
    if find_array_field(schema) is None:
        ev["reader"] = "route"
    elif n >= 2 and not ablate.off("colflow") and is_column_flow(pdf, n):
        ev["reader"] = "colflow"
    elif not ev["text_layer"] and (parser.CACHE / name).is_dir():
        texts = dict(enumerate(parser.cached_pages(name, errors="ignore"), 1))
        res = convert_tables(texts, schema)
        if res and res[1]:
            _, good, bad = res
            body = sum(
                max(0, len(r) - 1)
                for pg, t in texts.items()
                if pg not in bad
                for r in table_rows(t)
            )
            comp = sum(len(v) for v in good.values()) / max(1, body)
            ev["table_completeness"] = round(comp, 3)
            ev["table_pages"] = sorted(
                pg
                for pg, t in texts.items()
                if pg not in bad
                and sum(max(0, len(r) - 1) for r in table_rows(t)) >= RULED_MIN_ROWS
            )
            if comp >= 0.9 and not ablate.off("ruled"):
                ev["reader"] = "ruled"
    ev.setdefault("reader", "route")
    return ev


def main():
    split = sys.argv[1]
    recs = sorted(EB.load_records(split), key=EB.name_of)
    out = {EB.name_of(r): decide(r["data_schema"], EB.pdf_of(r), EB.name_of(r)) for r in recs}
    C.RUNS.mkdir(parents=True, exist_ok=True)
    (C.RUNS / f"{split}_layout.json").write_text(json.dumps(out, indent=1))
    print(split, dict(Counter(e["reader"] for e in out.values())), flush=True)
    if "--decide-only" in sys.argv:
        return
    cl = llm.client()
    readers = {"colflow": column_reader, "ruled": ruled_reader}

    def run(rec):
        name, kind = EB.name_of(rec), out[EB.name_of(rec)]["reader"]
        if kind in readers:
            got = readers[kind].read(
                cl,
                rec["data_schema"],
                EB.pdf_of(rec),
                workers=4,
                log=lambda s: print(f"{name[:30]} {s}", flush=True),
            )
            d = C.RUNS / f"{split}_{kind}"
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{name}.json").write_text(json.dumps(got))

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(run, recs))


if __name__ == "__main__":
    main()
