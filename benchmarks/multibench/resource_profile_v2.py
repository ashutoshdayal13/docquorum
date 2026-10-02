"""Source-derived fixes for the spare-GPU profile, measured as a separate variant.

V1 revealed overlong scalar requests returning {} and the external one-shot provider
bypassing our model-budget guard. V2 covers all scalar page windows and routes the
one-shot client through the same guard, without the provider's page/schema dropping.
"""
from resource_profile import install as install_v1


def install():
    from docquorum.agents import whole, reader, oneshot
    from docquorum.tools import llm, pdf as PDF
    from docquorum.tools.schema import scalar_fields
    profile = install_v1()
    whole.TEXT_WINDOW_TOKENS = 10000

    def read_scalars(cl, schema, pdf, pages, image_mode, stat):
        scalars = scalar_fields(schema)
        if not scalars:
            return {}
        sub = {"type": "object", "properties": scalars}
        for key in ("$defs", "definitions", "description"):
            if key in schema: sub[key] = schema[key]
        if image_mode:
            # Every physical page is visited; the old scalar path only saw the first two.
            n_pages = PDF.npages(pdf)
            merged, statuses = {}, []
            for page in range(1, n_pages + 1):
                got, finish, _ = whole.read(cl, sub, pdf, [], False, n_pages,
                    est_out=8000, max_tokens=8192, window=(page, page), scan=True)
                statuses.append((len(scalars), finish, got is not None))
                if isinstance(got, dict): merged = whole.merge_filled(merged, got)
        else:
            # Page windows plus schema groups cover the whole source without clipping.
            merged, statuses = whole.read_parts(cl, sub, pdf, pages, True, PDF.npages(pdf), text_windows=True)
        stat['calls'] += len(statuses)
        if merged is None or not statuses or any(finish != 'stop' or not ok for _, finish, ok in statuses):
            raise RuntimeError('Scalar page/schema partition did not complete')
        return {k:v for k,v in merged.items() if k in scalars}

    def read_oneshot(pdf, schema, prov=None):
        prov = prov or oneshot.provider()
        prov._client = llm.client()
        # Direct call: budget is set before generation; no page drops or schema pruning.
        raw = prov._call_api(prov._prepare_schema(schema), prov._render_page_images(pdf), max_tokens=8192)
        if raw.get('truncated') or raw.get('finish_reason') != 'stop':
            raise RuntimeError('One-shot reading incomplete; use the reader agent partitions')
        return raw.get('data')

    reader._read_scalars = read_scalars
    oneshot.read = read_oneshot
    return profile | {"profile": "DocQuorum8B-bounded-v2", "text_window_tokens": 10000,
                      "scalar_source_coverage": "Every page, with schema partitions if needed",
                      "oneshot": "Guarded client; reject truncated output; no page/schema dropping"}
