"""V2 plus complete text partitions and record-preserving dense-table reads.

This policy is derived from the pipeline source before its benchmark errors are
inspected. Disjoint page windows are different evidence, rather than alternative
readings: their arrays must accumulate. Dense tables retain identifier/value
association; truncation triggers smaller row blocks, never column separation.
"""
from resource_profile_v2 import install as install_v2


def merge_windows(a, b):
    from docquorum.agents.whole import _empty
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for key, value in b.items():
            out[key] = merge_windows(out[key], value) if key in out else value
        return out
    if _empty(a): return b
    if _empty(b): return a
    if isinstance(a, list) and isinstance(b, list): return a + b
    return a


def install():
    from docquorum.agents import whole, reader
    from docquorum.agents import prompts
    from docquorum.tools import llm
    profile = install_v2()
    original_parts = whole.read_parts
    whole.merge_filled = merge_windows

    def complete_parts(*args, **kwargs):
        merged, statuses = original_parts(*args, **kwargs)
        statuses = [(count, finish, ok and finish == 'stop') for count, finish, ok in statuses]
        # The original caller tolerates one failed part; None forces its fallback.
        if not statuses or any(not ok for _, _, ok in statuses):
            return None, statuses
        return merged, statuses

    def ask_chunk(cl, text, imgs, meta, label, stat, penalty=None, scan=False):
        array_name, lead, item_text, decoding_schema = meta[:4]
        context = meta[4] if len(meta) > 4 else ""      # the reader's reference block, if any
        intro = (prompts.CHUNK_OCR if scan else prompts.CHUNK_TEXT).format(p0=label, p1=label)
        prompt = prompts.CHUNK.format(context=context, intro=intro, text=text, item_schema=item_text,
                                      array_name=array_name, array_desc=lead)
        # A failed call is not evidence for an empty table. Propagate it rather than
        # letting the original helper return ([], False) and count it as completed.
        raw, tokens, finish = llm.ask(cl, prompt, max_tokens=8192, schema=decoding_schema, images=imgs)
        with stat['lock']:
            stat['calls'] += 1
            stat['tok'] += tokens
            stat['truncated'] += finish == 'length'
        if finish not in ('stop', 'length'):
            raise RuntimeError(f'Record partition did not finish: {label}/{finish}')
        if imgs and finish == 'length':
            raise RuntimeError(f'Image record partition incomplete: {label}')
        rows = llm.parse_json(raw)
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            if finish == 'length': return [], True
            raise ValueError(f'Record partition is not an array of objects: {label}')
        return rows, finish == 'length'

    def harvest(cl, text, imgs, meta, label, depth, stat):
        try:
            rows, cut = reader._ask_chunk(cl, text, imgs, meta, label, stat)
        except ValueError as error:
            if 'Input needs partitioning:' not in str(error): raise
            # The exact tokenizer rejects oversized inputs before generation.
            rows, cut = [], True
        if not cut:
            return rows
        # The image reader's path is separate. Never advertise a repaired truncated
        # text partition as complete when its recursive refinement fails.
        if imgs or depth >= 8:
            raise RuntimeError(f'Incomplete record partition: {label}')
        halves = reader.split_text(text, 2)
        if len(halves) < 2 or any(h == text for h in halves):
            raise RuntimeError(f'Cannot partition incomplete record block: {label}')
        with stat['lock']:
            stat['refined'] += 1
        complete = []
        for i, part in enumerate(halves):
            complete.extend(harvest(cl, part, (), meta, f'{label}.{i+1}', depth+1, stat))
        return complete

    whole.read_parts = complete_parts
    reader.OUT_BUDGET = 8192
    # Reader's old density-based split_columns divides cells belonging to one row.
    # Genuine independent panels are already handled by load_pages' layout parser.
    reader.split_columns = lambda text: [text]
    reader._ask_chunk = ask_chunk
    reader._harvest = harvest
    return profile | {'profile':'DocQuorum8B-bounded-v3', 'row_output_budget':8192,
        'window_merge':'Accumulate disjoint-page arrays in page order; preserve repeats',
        'partitions':'Require every partition to finish; otherwise use reader fallback',
        'dense_tables':'Keep complete rows; split oversized/truncated text blocks up to depth 8',
        'failed_record_calls':'Propagate failures; never treat failed calls as empty completed arrays'}
