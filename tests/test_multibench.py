"""Evaluation integrity and source-adapter regressions, without GPU inference."""
import base64
import io
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks/multibench"))
import resource_profile as R
import docubench as D
import varex as V
import longarray as L


def image_part(color):
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), color).save(buf, format="PNG")
    return {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}}


def test_image_composition_keeps_order_and_source_messages():
    messages = [{"role": "user", "content": [image_part("red"), image_part("blue"), {"type": "text", "text": "schema"}]}]
    snapshot = json.dumps(messages)
    combined = R.compose_images(messages)
    assert json.dumps(messages) == snapshot
    parts = combined[0]['content']
    assert sum(p['type'] == 'image_url' for p in parts) == 1
    im = Image.open(io.BytesIO(base64.b64decode(parts[0]['image_url']['url'].split(',', 1)[1])))
    assert im.size == (80, 40)
    assert im.getpixel((10, 20))[0] > 200
    assert im.getpixel((60, 20))[2] > 200
    assert parts[-1] == {"type": "text", "text": "schema"}


def test_context_reserves_output_and_rejects_oversized_input(monkeypatch):
    from docquorum.agents import whole, reader
    from docquorum.tools import llm
    for attr in ['MAX_IMAGE_PAGES', 'WINDOW_PAGES', 'MAX_IN_TOKENS', 'TEXT_WINDOW_TOKENS', 'MAX_OUT_TOKENS']:
        monkeypatch.setattr(whole, attr, getattr(whole, attr))
    monkeypatch.setattr(reader, 'MAX_IMAGES_PER_CALL', reader.MAX_IMAGES_PER_CALL)
    requests = []
    def create(**kw):
        requests.append(kw)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop')], usage=None)
    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm, 'client', lambda _: fake)
    counts = {'count': 30000, 'max_model_len': 32768}
    monkeypatch.setattr(R.httpx, 'post', lambda *a, **kw: SimpleNamespace(raise_for_status=lambda: None, json=lambda: counts))
    R.install()
    cl = llm.client()
    messages = [{'role': 'user', 'content': 'complete source'}]
    cl.chat.completions.create(messages=messages, max_tokens=32000)
    assert requests[0]['max_tokens'] == 2640
    assert requests[0]['messages'] == messages
    counts['count'] = 32000
    with pytest.raises(ValueError, match='partitioning'):
        cl.chat.completions.create(messages=messages, max_tokens=32000)
    assert len(requests) == 1


def test_native_docx_preserves_hebrew_and_paragraph_order(tmp_path):
    path = tmp_path/'source.docx'
    xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>שלום</w:t></w:r></w:p><w:p><w:r><w:t>123.45</w:t></w:r></w:p></w:body></w:document>'
    with zipfile.ZipFile(path, 'w') as f:
        f.writestr('word/document.xml', xml)
    text = D.native_text(path)
    assert text == 'word/document.xml\nשלום\n123.45'


def test_varex_missing_prediction_remains_in_denominator(monkeypatch, tmp_path):
    monkeypatch.setattr(V, 'OUT', tmp_path)
    V.write(tmp_path/'manifest.json', {'docs':[{'id':'a'}, {'id':'b'}], 'pilot_ids':['a','b']})
    V.write(tmp_path/'predictions/official/image_only/a.pred.json', {'x':'correct'})
    source = [{'doc_id':'a','split':'Flat','ground_truth':'{"x":"correct"}'},
              {'doc_id':'b','split':'Flat','ground_truth':'{"x":"missing"}'}]
    monkeypatch.setattr(V, 'rows', lambda columns: iter(source))
    V.score('pilot')
    result = json.loads((tmp_path/'scores/pilot/summary.json').read_text())['systems']['official']
    assert result['exact_match_normalized'] == 0.5
    assert result['attempted'] == 1
    assert not result['eligible_for_full_ranking']


def test_longarray_uses_official_unordered_matching_and_surplus_diagnostic():
    score, fuzzy, _ = L.official_scorer()
    schema = {'properties': {'rows': {'type':'array', 'items': {'properties': {'id':{}, 'amount':{}}}}}}
    gold = {'rows':[{'id':'a','amount':1}, {'id':'b','amount':2}]}
    pred = {'rows':[{'id':'b','amount':2}, {'id':'a','amount':1}, {'id':'junk','amount':999}]}
    # Official accuracy does not penalize surplus rows: our reports must expose their count.
    assert score(pred, gold, schema, {}) == (4, 4)
    assert score({'rows':[{'id':'a','amount':1}]}, gold, schema, {}) == (2, 4)


def test_public_baseline_coverage():
    root = D.SOURCE
    ids = {p.stem for p in (root/'schemas').glob('*.json')}
    assert len(ids) == 72
    assert {p.stem for p in (root/'documents').iterdir() if p.is_file()} == ids
    assert ids <= {p.stem for p in (root/'results/docupipe_high').glob('*.json')}


def test_v2_scalar_windows_keep_middle_pages(monkeypatch):
    import resource_profile_v2 as R2
    from docquorum.agents import reader, whole, oneshot
    from docquorum.tools import llm, pdf as PDF
    for obj, attrs in [(whole, ['MAX_IMAGE_PAGES','WINDOW_PAGES','MAX_IN_TOKENS','TEXT_WINDOW_TOKENS','MAX_OUT_TOKENS']),
                       (reader, ['MAX_IMAGES_PER_CALL','_read_scalars']), (oneshot, ['read']), (llm, ['client'])]:
        for attr in attrs: monkeypatch.setattr(obj, attr, getattr(obj, attr))
    pages = ['header', 'early', 'middle value', 'late', 'tail']
    captured = {}
    def partitions(cl, schema, pdf, actual_pages, has_text, n_pages, **kw):
        captured['pages'] = actual_pages
        captured['kw'] = kw
        return {'identifier':'middle value'}, [(1,'stop',True)]
    monkeypatch.setattr(whole, 'read_parts', partitions)
    monkeypatch.setattr(PDF, 'npages', lambda _: len(pages))
    R2.install()
    stat = {'calls':0}
    got = reader._read_scalars(None, {'properties':{'identifier':{'type':'string'}}}, 'doc.pdf', pages, False, stat)
    assert got == {'identifier':'middle value'}
    assert captured['pages'] == pages
    assert captured['kw']['text_windows'] is True
    assert stat['calls'] == 1


def test_v2_oneshot_rejects_partial_output_without_dropping_pages(monkeypatch):
    import resource_profile_v2 as R2
    from docquorum.agents import reader, whole, oneshot
    from docquorum.tools import llm
    for obj, attrs in [(whole, ['MAX_IMAGE_PAGES','WINDOW_PAGES','MAX_IN_TOKENS','TEXT_WINDOW_TOKENS','MAX_OUT_TOKENS']),
                       (reader, ['MAX_IMAGES_PER_CALL','_read_scalars']), (oneshot, ['read']), (llm, ['client'])]:
        for attr in attrs: monkeypatch.setattr(obj, attr, getattr(obj, attr))
    seen = []
    def call(schema, pages, **kw):
        seen.extend(pages)
        return {'data':{'a':'partial'},'truncated':True,'finish_reason':'length'}
    prov = SimpleNamespace(_prepare_schema=lambda s:s, _render_page_images=lambda p:['first','middle','last'],
                           _call_api=call)
    R2.install()
    with pytest.raises(RuntimeError, match='incomplete'):
        oneshot.read('source.pdf', {}, prov)
    assert seen == ['first','middle','last']
