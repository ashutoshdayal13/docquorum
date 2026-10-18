"""
Count the model calls and tokens this process uses, from each reply's own usage block.

Every extraction-model call goes through the OpenAI client's chat.completions.create and every
parser call through MinerU's HttpVlmClient.get_response_data; both are wrapped to add the reply's
usage to process-wide totals. Unlike the servers' /metrics counters, this counts only this
process, so several measurements can share the servers. Failed requests are not counted (as in
the servers' request_success_total).

    import usage_meter
    usage_meter.install()
    before = usage_meter.snapshot(); ...; used = usage_meter.since(before)
"""
import threading

KEYS = ("model_calls", "model_input_tokens", "model_output_tokens",
        "parser_calls", "parser_input_tokens", "parser_output_tokens")
_lock = threading.Lock()
_total = dict.fromkeys(KEYS, 0)
_installed = False


def _add(prefix, prompt, completion):
    with _lock:
        _total[f"{prefix}_calls"] += 1
        _total[f"{prefix}_input_tokens"] += prompt or 0
        _total[f"{prefix}_output_tokens"] += completion or 0


def install():
    global _installed
    if _installed:
        return
    from openai.resources.chat.completions import Completions
    from mineru_vl_utils.vlm_client.http_client import HttpVlmClient

    create = Completions.create

    def counted_create(self, *a, **k):
        r = create(self, *a, **k)
        u = getattr(r, "usage", None)
        _add("model", getattr(u, "prompt_tokens", 0), getattr(u, "completion_tokens", 0))
        return r

    get_data = HttpVlmClient.get_response_data

    def counted_get_data(self, response):
        d = get_data(self, response)
        u = d.get("usage") or {}
        _add("parser", u.get("prompt_tokens"), u.get("completion_tokens"))
        return d

    Completions.create = counted_create
    HttpVlmClient.get_response_data = counted_get_data
    _installed = True


def snapshot():
    with _lock:
        return dict(_total)


def since(before):
    now = snapshot()
    return {k: now[k] - before[k] for k in KEYS}
