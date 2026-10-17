"""Fresh ExtractBench input isolation, provenance and complete-cohort checks."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'benchmarks/multibench'))
import run_llama as R


def test_fresh_inference_only_receives_source_and_schema(monkeypatch,tmp_path):
    monkeypatch.setattr(R,'OUT',tmp_path)
    schema={'type':'object','properties':{'amount':{'type':'number'}}}
    schema_path=tmp_path/'schema.json'
    schema_path.write_text(json.dumps(schema))
    row={'id':'short/a','split':'short','name':'a','pdf':str(tmp_path/'source.pdf'),
        'schema':str(schema_path),'expected_output':{'amount':'gold sentinel'},
        'field_rules':{'secret':'rule sentinel'},'repeated_structure':{'secret':'identity sentinel'}}
    calls=[]
    def infer(pdf,actual,**kw):
        calls.append((pdf,actual,kw))
        return {'amount':17},{'readings':['primary']}
    monkeypatch.setattr(R,'extract',infer)
    assert R.infer_one(row,'policy')=='short/a'
    assert calls[0][0]==tmp_path/'source.pdf'
    assert calls[0][1]==schema and set(calls[0][2])=={'workers','log'}
    assert R.infer_one(row,'policy')=='short/a'
    assert len(calls)==1
    saved=R.checkpoint(tmp_path/'predictions/short/a.json','policy')
    assert saved['data']=={'amount':17} and saved['meta']['status']=='completed'
    assert 'sentinel' not in json.dumps(saved)


def test_checkpoint_detects_mutation_and_rejects_policy_mix(tmp_path):
    path=tmp_path/'a.json'
    saved={'data':{'x':1},'meta':{'policy_sha256':'policy','prediction_sha256':R.value_digest({'x':1}),
        'status':'completed'}}
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError,match='changed'):R.checkpoint(path,'other policy')
    saved['data']['x']=2
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError,match='changed'):R.checkpoint(path,'policy')


def test_missing_and_failed_documents_remain_in_full_denominator():
    rows=[{'id':str(i),'status':'completed','score':1.} for i in range(370)]
    rows[0].update(status='missing',score=0.)
    rows[1].update(status='failed',score=0.)
    policy={'profile':{'profile':'candidate'}}
    manifest={'dataset_revision':'data','scorer_revision':'scorer'}
    result=R.aggregate(rows,policy,manifest)
    assert result['score']==pytest.approx(100*368/370)
    assert result['attempted']==369 and result['completed']==368
    assert not result['eligible_for_full_ranking']
    rows[0]['status']='failed'
    assert R.aggregate(rows,policy,manifest)['eligible_for_full_ranking']
    with pytest.raises(ValueError,match='370 unique'):R.aggregate(rows[:-1],policy,manifest)


def test_pdf_provenance_accepts_upstream_git_blob_and_rejects_changes(tmp_path):
    path=tmp_path/'a.pdf'
    data=b'%PDF-source'
    path.write_bytes(data)
    blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    evidence={'hash_algorithm':'git_blob_sha1','matches_current':True,'upstream_content_hash':blob}
    assert R.verify_pdf(path,evidence)==hashlib.sha256(data).hexdigest()
    path.write_bytes(data+b'changed')
    with pytest.raises(ValueError,match='differs'):R.verify_pdf(path,evidence)


def test_inference_failure_is_one_resumable_atomic_checkpoint(monkeypatch,tmp_path):
    monkeypatch.setattr(R,'OUT',tmp_path)
    schema=tmp_path/'schema.json'
    schema.write_text('{}')
    row={'id':'short/a','split':'short','name':'a','pdf':'source.pdf','schema':str(schema)}
    def fail(*args,**kw):raise RuntimeError('inference unavailable')
    monkeypatch.setattr(R,'extract',fail)
    R.infer_one(row,'policy')
    saved=R.checkpoint(tmp_path/'predictions/short/a.json','policy')
    assert saved['meta']['status']=='failed' and saved['data']=={}
    assert R.infer_one(row,'policy')=='short/a'
