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


def test_a_long_scan_keeps_its_parse_reading_unless_the_parse_lost_the_list():
    rows = [{"w": str(i)} for i in range(100)]
    assert quorum.long_scan_choice({"primary": {"e": rows}, "parse": {"e": rows[:90]}}) == "parse"
    assert quorum.long_scan_choice({"primary": {"e": rows}, "parse": {"e": rows[:40]}}) == "primary"
    assert quorum.long_scan_choice({"parse": {"e": rows[:5]}}) == "parse"            # nothing to compare
    loop = {"e": rows[:1] * 120}
    assert quorum.long_scan_choice({"primary": {"e": rows}, "parse": loop}) == "primary"
    assert quorum.long_scan_choice({"primary": loop, "parse": {"e": rows[:1] * 90}}) == "parse"
