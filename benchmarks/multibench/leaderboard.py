"""Collect benchmark-specific results without promoting incomplete runs to ranks."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/multibench'


def load(relative):
    path = OUT / relative
    return json.loads(path.read_text()) if path.exists() else None


def reference(benchmark, variant, score, peers, eligible, decimals, **extra):
    rounded = round(score, decimals)
    higher = sum(round(p['score'], decimals) > rounded for p in peers)
    ties = [p['system'] for p in peers if round(p['score'], decimals) == rounded]
    sorted_peers = sorted(peers, key=lambda r: -r['score'])
    return {'benchmark':benchmark, 'variant':variant, 'score':score,
            'full_comparison_eligible':eligible, 'official_submission':False,
            'reference_score_rank': 1+higher if eligible else None,
            'ties_at_published_precision':ties if eligible else [],
            'leader':sorted_peers[0], 'third_place_target':sorted_peers[2],
            'gap_to_leader_pp': sorted_peers[0]['score']-score if eligible else None,
            'gap_to_third_pp': sorted_peers[2]['score']-score if eligible else None,
            'comparison':'Published reference scores; not an official accepted rank', **extra}


def main():
    rows = []
    eb = load('extractbench_current_reference.json')
    if eb:
        rows.append(reference('run-llama ExtractBench','Stored primary, current public annotations',eb['score'],
            load('extractbench_public_rows.json')['rows'], True, 2, provenance='Archived evaluation, input and revision hashes revalidated'))
    u = load('unikie_audit.json')
    if u:
        for name in ['three_original_readings','four_readings','six_readings']:
            result=u['docquorum'][name]
            rows.append(reference('UNIKIE constrained-category',name,result['score'],u['published_results'],True,2,
                documents=4472, scope=result['configuration']))
    d = load('docubench_public_audit.json')
    if d:
        peers=[r for r in d['results'] if r['rank_eligible']]
        for folder in ['docubench','docubench_v2']:
            s=load(folder+'/summary.json')
            if s:
                rows.append(reference('DocuBench v0.2.0',s['engine'],s['score'],peers,s['eligible_for_full_ranking'],8,
                    attempted=s['attempted'], expected=72, completed=s['completed']))
    v = load('varex_public_audit.json')
    if v:
        for scope in ['pilot','full']:
            s=load(f'varex/scores/{scope}/summary.json')
            if s:
                for name, result in s['systems'].items():
                    rows.append(reference('VAREX image_only','8B '+name,100*result['exact_match_normalized'],v['results'],
                        result['eligible_for_full_ranking'],1,scope=scope,attempted=result['attempted'],expected=s['docs']))
    peers=[{'system':'Extend MAX','score':99.2},{'system':'Reducto Deep Extract','score':97.4},{'system':'Claude Opus 4.7','score':83.1}]
    for folder in ['longarray','longarray_v2']:
        for scope in ['pilot','full']:
            s=load(f'{folder}/scores/{scope}/summary.json')
            if s:
                rows.append(reference('LongArray-Extract',s['profile'],s['score'],peers,s['eligible_for_full_ranking'],1,
                    scope=scope,attempted=s['attempted'],expected=s['expected'],completed=s['completed']))
    pending=[{'benchmark':b,'status':state,'reference_score_rank':None} for b,state in [
        ('DocuBench','Full run in progress; refresh after scoring'),
        ('VAREX','Full run in progress; pilot does not establish a rank'),
        ('LongArray-Extract','Pilot deferred to prioritize shorter complete cohorts'),
        ('Contextual AI Extract Bench','26/35 schema-valid; official judge and paper/scorer field-count reconciliation needed'),
        ('LongExtractBench public 50','Inputs available; published 225-document cohort cannot supply a matching rank')]]
    present_full={r['benchmark'] for r in rows if r['full_comparison_eligible']}
    pending=[p for p in pending if not any(p['benchmark'] in name for name in present_full)]
    report={'branch':'experiment/multibench-20261002','rows':rows,'pending':pending,
            'note':'Different metrics and cohorts remain separate. No cross-benchmark aggregate or superiority claim.'}
    (OUT/'leaderboard.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    for row in rows:
        print(row['benchmark'],row['variant'],f"{row['score']:.4f}", 'rank reference '+str(row['reference_score_rank']) if row['full_comparison_eligible'] else 'pilot/incomplete')


if __name__=='__main__': main()
