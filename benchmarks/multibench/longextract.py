"""Pinned public-50 LongExtractBench adapter; no rank against the private 225.

prepare/run read only original PDFs and supplied schemas. Gold is opened solely
by score, using the publisher's grader and success classifier unchanged.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from docquorum import config as C
from docquorum.extract import extract
from varex import write

SOURCE = ROOT / 'data/multibench_sources/longextract'
DATA = ROOT / 'data/multibench_sources/longextract_data'
OUT = ROOT / 'results/multibench/longextract_v3'
REVISION = 'd4ca332f72f6d3649ecd11b69445a8f4ef5fcb02'
CODE_REVISION = 'b28888d7e864a84dfed810b00c899f308f0d24d0'


def official_module(name):
    path = SOURCE / 'src/longextract_bench' / (name+'.py')
    spec = importlib.util.spec_from_file_location('longextract_official_'+name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare():
    # Use the official filename preferences without opening any answer key.
    grader = official_module('grading')
    docs = []
    for folder in sorted(DATA.iterdir()):
        pdf = folder / 'document.pdf'
        if not pdf.exists(): continue
        schema = grader.find_in(folder, grader.SCHEMA_NAMES)
        if schema is None: raise ValueError(f'Schema missing: {folder.name}')
        docs.append({'id':folder.name, 'pdf':str(pdf), 'schema':str(schema),
            'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
            'schema_sha256':hashlib.sha256(schema.read_bytes()).hexdigest()})
    if len(docs) != 50 or len({r['id'] for r in docs}) != 50:
        raise ValueError('Expected exactly 50 unique public tasks')
    docs.sort(key=lambda r:hashlib.sha256(('multibench-v1:'+r['id']).encode()).hexdigest())
    write(OUT/'manifest.json', {'dataset':'micro1-inc/longextract-bench-50', 'revision':REVISION,
        'scorer_revision':CODE_REVISION, 'docs':docs, 'pilot_ids':[r['id'] for r in docs[:3]],
        'excluded_inputs':['ground_truth', 'ground_truth_pruned_v3', 'target counts', 'provider outputs'],
        'scope':'Public 50; not the published private 225-document cohort'})
    print('Prepared 50 source-only tasks')


def cohort(scope):
    manifest = json.loads((OUT/'manifest.json').read_text())
    return manifest['docs'] if scope == 'full' else [r for r in manifest['docs'] if r['id'] in manifest['pilot_ids']]


def run(scope, workers):
    from resource_profile_v3 import install
    profile = install()
    policy = {'profile':profile, 'model':C.MODEL, 'scope':scope, 'dataset_revision':REVISION,
              'task':'Extract every record and document-level field shown in the document according to the supplied schema.'}
    path = OUT/('policy_'+scope+'.json')
    if path.exists() and json.loads(path.read_text()) != policy: raise ValueError('Run policy changed')
    write(path, policy)
    def one(record):
        name = record['id']; dst = OUT/'predictions'/(name+'.json')
        if dst.exists(): return name
        pdf, schema = Path(record['pdf']), Path(record['schema'])
        for kind, src in [('pdf',pdf),('schema',schema)]:
            if hashlib.sha256(src.read_bytes()).hexdigest() != record[kind+'_sha256']:
                raise ValueError(f'Input changed: {name}/{kind}')
        start = time.monotonic()
        try:
            got, detail = extract(pdf, json.loads(schema.read_text()), task=policy['task'], workers=2,
                log=lambda msg:print(name+': '+msg, flush=True))
            report = {'status':'completed', 'detail':detail}
        except Exception as error:
            got, report = {}, {'status':'failed', 'error':f'{type(error).__name__}: {str(error)[:500]}'}
        report['seconds'] = time.monotonic()-start
        write(OUT/'reports'/(name+'.json'), report)
        write(dst, got)
        return name
    records = cohort(scope)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one,r) for r in records]
        for i, future in enumerate(as_completed(futures), 1):
            print(f'[{i}/{len(records)}] {future.result()}', flush=True)


def score(scope):
    grader, classifier = official_module('grading'), official_module('classify')
    scored = []
    for record in cohort(scope):
        name = record['id']; path = OUT/'predictions'/(name+'.json'); report = OUT/'reports'/(name+'.json')
        meta = json.loads(report.read_text()) if report.exists() else {'status':'missing'}
        pred = json.loads(path.read_text()) if path.exists() else None
        status, reason = classifier.classify({'result':pred, '_meta':meta})
        row = {'id':name, 'attempted':path.exists(), 'status':status, 'reason':reason, 'seconds':meta.get('seconds')}
        if status == 'success':
            gold = grader.load_ground_truth(Path(record['pdf']).parent)
            if gold is None: raise ValueError(f'Missing answer key: {name}')
            row.update(grader.grade(pred, gold, json.loads(Path(record['schema']).read_text())))
        scored.append(row)
    successes = [r for r in scored if r['status']=='success']
    failures = [r for r in scored if r['status']=='failure']
    assert len(successes)+len(failures) == len(cohort(scope))
    latencies = sorted(r['seconds'] for r in successes if r['seconds'] is not None)
    summary = {'benchmark':'LongExtractBench public 50', 'scope':scope, 'profile':'DocQuorum8B-bounded-v3',
        'expected':len(scored), 'attempted':sum(r['attempted'] for r in scored), 'successful':len(successes),
        'failed':len(failures), 'leaf_accuracy':statistics.mean(r['leaf_accuracy'] for r in successes) if successes else 0.,
        'row_precision':statistics.mean(r['precision'] for r in successes) if successes else 0.,
        'row_recall':statistics.mean(r['recall'] for r in successes) if successes else 0.,
        'latency_mean_s':statistics.mean(latencies) if latencies else None,
        'latency_p95_s':latencies[min(len(latencies)-1,int(len(latencies)*.95))] if latencies else None,
        'metric':'Official macro accuracy and row P/R over successful documents only; failures reconciled separately',
        'scorer_sha256':hashlib.sha256((SOURCE/'src/longextract_bench/grading.py').read_bytes()).hexdigest(),
        'dataset_revision':REVISION, 'source_revision':CODE_REVISION,
        'eligible_for_public50_comparison':scope=='full' and all(r['attempted'] for r in scored),
        'eligible_for_published225_ranking':False, 'reference_score_rank':None, 'official_submission':False,
        'per_document':scored}
    write(OUT/'scores'/scope/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='per_document'}, indent=2))


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','run','score'])
    parser.add_argument('--scope',choices=['pilot','full'],default='pilot')
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--workers',type=int,default=2)
    args = parser.parse_args()
    OUT = args.out.resolve()
    if args.action=='prepare':prepare()
    elif args.action=='run':run(args.scope,args.workers)
    else:score(args.scope)
