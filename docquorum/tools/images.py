"""
Small images are enlarged before reading. A vision model reads a page through a fixed patch
grid, so an image a few hundred pixels across (a phone crop of a receipt, a label) reaches it
as a few dozen patches and its text is unreadable: the model then guesses. Enlarging such an
image (LANCZOS, by the smallest whole factor that brings its shorter side to MIN_SIDE) gives
the text enough patches; it adds no content. Images at least MIN_SIDE on their shorter side,
and enlargements that would pass the caller's pixel cap, are left as they are.
"""
from PIL import Image

MIN_SIDE = 1000


def enlarge_small(im, max_pixels=None, min_side=MIN_SIDE):
    """The image enlarged by a whole factor when its shorter side is below min_side; else im."""
    w, h = im.size
    if min(w, h) >= min_side:
        return im
    k = -(-min_side // max(1, min(w, h)))                # ceil
    while k > 1 and max_pixels and (k * w) * (k * h) > max_pixels:
        k -= 1
    return im.resize((k * w, k * h), Image.LANCZOS) if k > 1 else im


def flatten(im):
    """RGB, with any transparent area made white: a plain convert("RGB") turns it black, and
    black text on a transparent background becomes black on black."""
    if im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info:
        rgba = im.convert("RGBA")
        out = Image.new("RGB", rgba.size, (255, 255, 255))
        out.paste(rgba, mask=rgba.getchannel("A"))
        return out
    return im.convert("RGB")
