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
import leaderboard as B
import contextual as X
import resource_profile_v3 as R3
import longextract as LX
import resource_profile_v4 as R4


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


def test_pilot_cannot_receive_a_rank_even_above_every_leader():
    peers = [{'system':'first','score':98}, {'system':'second','score':97}, {'system':'third','score':96}]
    row = B.reference('benchmark','pilot',100,peers,False,1)
    assert row['reference_score_rank'] is None
    assert row['gap_to_leader_pp'] is None
    assert not row['official_submission']


def test_unrounded_measurement_does_not_turn_published_tie_into_win():
    peers = [{'system':'Gemini','score':82.37}, {'system':'second','score':80.2}, {'system':'third','score':79.12}]
    row = B.reference('UNIKIE','tuned',82.374571,peers,True,2)
    assert row['reference_score_rank'] == 1
    assert row['ties_at_published_precision'] == ['Gemini']


def test_wrapped_contextual_schema_does_not_accept_every_prediction():
    import jsonschema
    wrapper = {'name':'resume', 'schema_definition':{'type':'object',
        'properties':{'name':{'type':'string'}}, 'required':['name']}}
    actual = X.actual_schema(wrapper)
    assert list(jsonschema.Draft202012Validator(actual).iter_errors({'name':None}))
    with pytest.raises(ValueError, match='No JSON Schema'):
        X.actual_schema({'name':'metadata wrapper'})


@pytest.fixture
def install_v3(monkeypatch):
    from docquorum.agents import whole, reader, oneshot
    from docquorum.tools import llm
    for obj, attrs in [(whole, ['MAX_IMAGE_PAGES','WINDOW_PAGES','MAX_IN_TOKENS','TEXT_WINDOW_TOKENS',
                               'MAX_OUT_TOKENS','merge_filled','read_parts']),
                       (reader, ['MAX_IMAGES_PER_CALL','_read_scalars','OUT_BUDGET','split_columns','_harvest','_ask_chunk']),
                       (oneshot, ['read']), (llm, ['client'])]:
        for attr in attrs: monkeypatch.setattr(obj, attr, getattr(obj, attr))
    return R3.install


def test_disjoint_windows_preserve_shorter_lists_and_repeated_rows():
    first = {'rows':[{'id':'repeat'},{'id':'repeat'}], 'meta':{'issuer':'A','date':None}}
    second = {'rows':[{'id':'B'}], 'meta':{'issuer':None,'date':'2026'}}
    merged = R3.merge_windows(first, second)
    assert merged['rows'] == [{'id':'repeat'},{'id':'repeat'},{'id':'B'}]
    assert merged['meta'] == {'issuer':'A','date':'2026'}
    assert len(first['rows']) == 2


def test_one_incomplete_partition_forces_reader_fallback(monkeypatch, install_v3):
    from docquorum.agents import whole
    monkeypatch.setattr(whole, 'read_parts', lambda *a, **kw: ({'rows':['partial']},
        [(1,'stop',True),(1,'length',True)]))
    install_v3()
    got, statuses = whole.read_parts()
    assert got is None
    assert statuses == [(1,'stop',True),(1,'length',False)]


def test_dense_table_keeps_identifiers_with_values(monkeypatch, install_v3):
    import threading
    from docquorum.agents import reader
    install_v3()
    text = '\n'.join(f'PART-{i:04d} UNIT                  {i+1000}                 {i+2000}.00' for i in range(80))
    seen = []
    def harvest(cl, actual, imgs, meta, label, depth, stat):
        seen.append(actual)
        return [{'field_0':'PART-0000', 'field_1':'2000.00'}]
    monkeypatch.setattr(reader, '_harvest', harvest)
    item = {'type':'object', 'properties':{f'field_{i}':{'type':'string'} for i in range(20)}}
    reader._read_list(None, {}, None, [text], False, 'rows', item, '', 1, {'lock':threading.Lock()})
    assert seen == [text]


def test_complete_refinement_replaces_longer_truncated_reply(monkeypatch, install_v3):
    import threading
    from docquorum.agents import reader
    install_v3()
    responses = iter([([{'id':'invalid'}]*10,True), ([{'id':'a'}],False), ([{'id':'b'}],False)])
    monkeypatch.setattr(reader, '_ask_chunk', lambda *a:next(responses))
    monkeypatch.setattr(reader, 'split_text', lambda text,n:['left','right'])
    got = reader._harvest(None, 'source', (), None, 'page1', 0, {'lock':threading.Lock(),'refined':0})
    assert got == [{'id':'a'},{'id':'b'}]


def test_record_call_failure_cannot_be_reported_as_empty_success(monkeypatch, install_v3):
    import threading
    from docquorum.agents import reader
    from docquorum.tools import llm
    install_v3()
    def fail(*args, **kw): raise ConnectionError('endpoint unavailable')
    monkeypatch.setattr(llm, 'ask', fail)
    stat = {'lock':threading.Lock(),'calls':0,'tok':0,'truncated':0}
    with pytest.raises(ConnectionError, match='unavailable'):
        reader._ask_chunk(None, 'source', (), ('rows','','{}',{}), 'page1', stat)


def test_longextract_accuracy_keeps_omissions_and_failures_visible(monkeypatch, tmp_path):
    monkeypatch.setattr(LX, 'OUT', tmp_path)
    schema = {'properties':{'rows':{'type':'array','items':{'type':'object',
        'properties':{'id':{'type':'string'},'amount':{'type':'number'}}}}}}
    gold = {'rows':[{'id':'A','amount':1},{'id':'B','amount':2}]}
    records = []
    for name in ('done','missing'):
        folder = tmp_path/'source'/name; folder.mkdir(parents=True)
        (folder/'schema.json').write_text(json.dumps(schema))
        (folder/'ground_truth.json').write_text(json.dumps(gold))
        records.append({'id':name,'schema':str(folder/'schema.json'),'pdf':str(folder/'document.pdf')})
    monkeypatch.setattr(LX, 'cohort', lambda _:records)
    V.write(tmp_path/'predictions/done.json', {'rows':[{'id':'A','amount':1}]})
    V.write(tmp_path/'reports/done.json', {'status':'completed','seconds':10})
    LX.score('full')
    summary = json.loads((tmp_path/'scores/full/summary.json').read_text())
    assert summary['leaf_accuracy'] == 100
    assert summary['row_recall'] == .5
    assert (summary['successful'],summary['failed'],summary['expected']) == (1,1,2)
    assert not summary['eligible_for_public50_comparison']
    assert summary['reference_score_rank'] is None


def test_scan_chunks_do_not_drop_every_second_physical_page(monkeypatch, install_v3):
    from docquorum.agents import reader
    monkeypatch.setattr(reader, 'load_pages', reader.load_pages)
    monkeypatch.setattr(reader, 'plan_chunks', reader.plan_chunks)
    R4.install()
    chunks, size, _ = reader.plan_chunks(['']*5, 3)
    assert size == 1
    assert chunks == [(0,1),(1,2),(2,3),(3,4),(4,5)]


def test_mixed_pdf_uses_images_for_its_unreadable_data_page(monkeypatch, install_v3):
    from docquorum.agents import reader
    pages = ['', 'Instructions and legend. '*20]
    monkeypatch.setattr(reader, 'load_pages', lambda *args, **kwargs:(pages,False))
    monkeypatch.setattr(reader, 'plan_chunks', reader.plan_chunks)
    R4.install()
    actual, parsed = reader.load_pages('doc.pdf','mixed')
    assert actual == ['', ''] and not parsed
    assert pages[1] != ''
    pages[0] = 'Native first-page text. '*20
    actual, _ = reader.load_pages('doc.pdf','native')
    assert actual == pages
    assert reader.plan_chunks(actual, 3)[1] == 2
