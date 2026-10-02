"""V3 plus complete image coverage for mixed PDFs and scan chunks.

The baseline's document-level text heuristic misses image-only pages when other
pages have native text. Its two-page scan chunks are also sliced to one image by
the spare-GPU profile. Preserve physical pages before optimizing model readings.
"""
from resource_profile_v3 import install as install_v3


def install():
    from docquorum.agents import reader, whole
    profile = install_v3()
    original_load = reader.load_pages
    original_plan = reader.plan_chunks
    whole.MAX_IMAGE_PAGES = 4

    def load_pages(*args, **kwargs):
        pages, parsed = original_load(*args, **kwargs)
        rich = [len(text.strip()) >= 50 for text in pages]
        if not parsed and any(rich) and not all(rich):
            # A blank text layer can be a scanned page, not a blank document page.
            # Read every physical page as an image; do not fill from legend text.
            print(f'    [mixed PDF] {sum(not r for r in rich)}/{len(pages)} pages without usable text; read all pages as images', flush=True)
            return [''] * len(pages), False
        return pages, parsed

    def plan_chunks(pages, n_fields, one_page=False):
        image_mode = sum(len(text.strip()) for text in pages) < 50 * max(1,len(pages))
        # Only scan chunks change; native-text records can still span two pages.
        return original_plan(pages, n_fields, one_page=one_page or image_mode)

    reader.load_pages = load_pages
    reader.plan_chunks = plan_chunks
    return profile | {'profile':'DocQuorum8B-bounded-v4', 'whole_image_pages':4,
        'mixed_pdf':'If native and non-text pages coexist, visit all physical pages as images',
        'scan_chunks':'One physical page per chunk; never slice away a second page image',
        'development_scope':'Mixed-PDF routing change motivated by completed DocuBench baseline diagnostics'}
