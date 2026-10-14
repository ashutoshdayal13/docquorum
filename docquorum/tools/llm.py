"""
Model calls: the OpenAI-compatible client, one chat call, and reading JSON out of a reply.

Every call decodes under the JSON schema it is given (vLLM structured outputs) and with the
model's reasoning switched off.
"""
import json
import re

from docquorum import config as C


def client(timeout=7200):
    """A long call (a whole document, up to 32k output tokens) can take an hour on a shared GPU;
    re-sending it after a timeout repeats all of that work, so retries are few."""
    from openai import OpenAI
    return OpenAI(base_url=C.LLM_URL, api_key="EMPTY", timeout=timeout, max_retries=2)


def extra_body(schema=None):
    """Request fields: the decoding schema, and reasoning off (Qwen3.8 reasons by default)."""
    eb = {}
    if schema:
        eb["structured_outputs"] = {"json": schema}
    eb["chat_template_kwargs"] = {"enable_thinking": False}
    return eb


def image_parts(images, mime="jpeg"):
    return [{"type": "image_url", "image_url": {"url": f"data:image/{mime};base64,{b}"}} for b in images]


def ask(cl, prompt, max_tokens=8000, schema=None, images=()):
    """One call; returns (reply text, tokens used, finish_reason)."""
    content = (image_parts(images) + [{"type": "text", "text": prompt}]) if images else prompt
    r = cl.chat.completions.create(model=C.MODEL, temperature=0.0, max_tokens=max_tokens,
                                   messages=[{"role": "user", "content": content}],
                                   extra_body=extra_body(schema))
    ch = r.choices[0]
    return ch.message.content, (r.usage.total_tokens if r.usage else 0), ch.finish_reason


def parse_json(text):
    """A JSON value from a reply, list first; a cut-off list keeps the objects that closed."""
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    for o, c in (("[", "]"), ("{", "}")):
        i, j = text.find(o), text.rfind(c)
        if i != -1 and j > i:
            try:
                return json.loads(text[i:j + 1])
            except json.JSONDecodeError:
                pass
    i = text.find("[")
    if i == -1:
        return None
    depth, last = 0, None
    for k in range(i, len(text)):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                last = k
    if last is None:
        return None
    try:
        return json.loads(text[i:last + 1] + "]")
    except json.JSONDecodeError:
        return None


def parse_object(text):
    """A JSON object from a reply, object first (parse_json would return the inner list of
    {"a": 1, "items": [...]}); a cut-off object is repaired."""
    t = re.sub(r"^.*?</think>", "", text, count=1, flags=re.S).strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        v = json.loads(t)
        return v if isinstance(v, dict) else None
    except Exception:
        pass
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j > i:
        try:
            v = json.loads(t[i:j + 1])
            if isinstance(v, dict):
                return v
        except Exception:
            pass
    try:
        import json_repair
        v = json_repair.loads(t[i:] if i != -1 else t)
        return v if isinstance(v, dict) else None
    except Exception:
        return None


def server_failure(e):
    """True when the SERVER failed (5xx, connection, timeout) rather than rejecting the
    request: such a document is not written, so a resumed run redoes it."""
    import openai
    if isinstance(e, (openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError)):
        return True
    return getattr(e, "status_code", 0) >= 500
