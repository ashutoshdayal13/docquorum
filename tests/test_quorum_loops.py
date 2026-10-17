"""The quorum does not keep a reading that went round in a loop when another reading did not."""
from docquorum import quorum


def test_a_list_of_mostly_repeats_is_a_loop_but_a_few_repeated_rows_are_not():
    row = {"word": "a", "tag": None}
    assert quorum.looped({"entries": [row] * 30})
    assert not quorum.looped({"entries": [dict(row, word=str(i)) for i in range(28)] + [row, row]})
    assert not quorum.looped({"entries": [row] * 10})                 # too short to tell


def test_the_quorum_passes_over_looped_readings(monkeypatch):
    rows = [{"word": str(i)} for i in range(25)]
    views = {"primary": {"e": rows[:1] * 40}, "oneshot": {"e": rows[:1] * 38}, "parse": {"e": rows}}
    # the two looped readings agree with each other most
    agreement = {("primary", "oneshot"): (1, 1), ("oneshot", "primary"): (1, 1)}
    monkeypatch.setattr(quorum, "ProcessPoolExecutor", _Serial)
    monkeypatch.setattr(quorum, "agree", lambda job: agreement.get(_names(views, job), (0.1, 0.1)))
    best, score, _ = quorum.pick({}, views)
    assert max(score, key=score.get) == "primary" and best == "parse"


class _Serial:
    def __init__(self, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def map(self, f, jobs): return [f(j) for j in jobs]


def _names(views, job):
    _rec, a, b = job
    find = lambda v: next(k for k, x in views.items() if x is v)
    return find(a), find(b)


def test_a_chunk_that_went_round_in_a_loop_is_read_again_then_cleaned(monkeypatch):
    import json
    import threading
    from docquorum.agents import reader
    from docquorum.tools import llm
    calls = []
    good = [{"w": str(i)} for i in range(25)]

    def ask(cl, prompt, **k):
        calls.append(k.get("repetition_penalty"))
        rows = [{"w": "0"}] * 40 if len(calls) == 1 else good
        return json.dumps(rows), 0, "stop"
    monkeypatch.setattr(llm, "ask", ask)
    stat = {"calls": 0, "tok": 0, "truncated": 0, "lock": threading.Lock()}
    rows, cut = reader._ask_chunk(None, "text", (), ("rows", "", "{}", None, ""), "page 1", stat)
    assert rows == good and calls == [None, reader.LOOP_PENALTY] and stat["loops"] == 1
    # a reply that still loops after the penalty keeps each record once
    monkeypatch.setattr(llm, "ask", lambda cl, p, **k: (json.dumps([{"w": "0"}] * 30 + [{"w": "1"}]), 0, "stop"))
    rows, _ = reader._ask_chunk(None, "text", (), ("rows", "", "{}", None, ""), "page 2", stat)
    assert rows == [{"w": "0"}, {"w": "1"}]
