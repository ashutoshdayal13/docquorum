"""Explicit spare-GPU profile for the existing DocQuorum reader.

Uses exact server tokenization to reserve output space. Inputs are never clipped.
Multiple images are composed in source order because this server profiles one image.
All changes are confined to this experimental runner process.
"""
import base64
import copy
import io
import math
from types import SimpleNamespace

import httpx
from PIL import Image


def compose_images(messages):
    messages = copy.deepcopy(messages)
    locations = [(m, i, part) for m in messages if isinstance(m.get("content"), list)
                 for i, part in enumerate(m["content"]) if part.get("type") == "image_url"]
    if len(locations) <= 1:
        return messages
    images = []
    for _, _, part in locations:
        url = part["image_url"]["url"]
        if not url.startswith("data:image/"):
            raise ValueError("Composing images requires local image data")
        images.append(Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGB"))
    columns = min(2, len(images))
    width, height = max(im.width for im in images), max(im.height for im in images)
    canvas = Image.new("RGB", (width * columns, height * math.ceil(len(images) / columns)), "white")
    for i, im in enumerate(images):
        canvas.paste(im, ((i % columns) * width, (i // columns) * height))
    # A bounded view; every page is included, and downsampling is disclosed in the policy.
    scale = min(1, (5_000_000 / (canvas.width * canvas.height)) ** 0.5)
    if scale < 1:
        canvas = canvas.resize((max(1, int(canvas.width * scale)), max(1, int(canvas.height * scale))))
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=90)
    composite = {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}}
    first = locations[0][0]
    for message in messages:
        if isinstance(message.get("content"), list):
            message["content"] = [p for p in message["content"] if p.get("type") != "image_url"]
    first["content"] = [composite, {"type": "text", "text":
        f"The attached composite contains {len(images)} source page images in row-major order (left to right, then top to bottom)."}] + first["content"]
    return messages


def install():
    from docquorum import config as C
    from docquorum.agents import whole, reader
    from docquorum.tools import llm
    whole.MAX_IMAGE_PAGES = 1
    whole.WINDOW_PAGES = 1
    whole.MAX_IN_TOKENS = 20000
    whole.TEXT_WINDOW_TOKENS = 14000
    whole.MAX_OUT_TOKENS = 8192
    reader.MAX_IMAGES_PER_CALL = 1
    original = llm.client

    def client(timeout=1800):
        base = original(timeout)
        calls = []

        def create(**kwargs):
            kwargs["messages"] = compose_images(kwargs["messages"])
            response = httpx.post(C.LLM_URL.removesuffix("/v1") + "/tokenize",
                json={"model": C.MODEL, "messages": kwargs["messages"], "add_generation_prompt": True,
                      "chat_template_kwargs": {"enable_thinking": False}}, timeout=120)
            response.raise_for_status()
            tokens = response.json()
            room = tokens["max_model_len"] - tokens["count"] - 128
            if room < 1024:
                raise ValueError(f"Input needs partitioning: {tokens['count']} tokens; {room} output tokens available")
            requested = kwargs.get("max_tokens", 8192)
            kwargs["max_tokens"] = min(requested, room, 8192)
            got = base.chat.completions.create(**kwargs)
            calls.append({"prompt_tokens": tokens["count"], "requested_output": requested,
                          "output_budget": kwargs["max_tokens"], "finish_reason": got.choices[0].finish_reason,
                          "usage": got.usage.model_dump() if got.usage else None})
            return got
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)), calls=calls)
    llm.client = client
    return {"profile": "DocQuorum8B-bounded-v1", "max_model_len": 32768,
            "model_revision": "9cdc6310a8cb770ce18efaf4e9935334512aee45", "max_output_tokens": 8192,
            "whole_input_estimate_limit": 20000, "text_window_tokens": 14000,
            "whole_image_pages": 1, "multiple_image_adapter": "Row-major composite, at most 5 million pixels",
            "parser": "unavailable; original parser fallback", "frozen_27b_configuration": False,
            "input_clipping": False}
