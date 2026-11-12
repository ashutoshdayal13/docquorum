from PIL import Image

MIN_SIDE = 1000


def enlarge_small(im, max_pixels=None, min_side=MIN_SIDE):
    w, h = im.size
    if min(w, h) >= min_side:
        return im
    k = -(-min_side // max(1, min(w, h)))
    while k > 1 and max_pixels and (k * w) * (k * h) > max_pixels:
        k -= 1
    return im.resize((k * w, k * h), Image.LANCZOS) if k > 1 else im


def flatten(im):
    if im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info:
        rgba = im.convert("RGBA")
        out = Image.new("RGB", rgba.size, (255, 255, 255))
        out.paste(rgba, mask=rgba.getchannel("A"))
        return out
    return im.convert("RGB")
