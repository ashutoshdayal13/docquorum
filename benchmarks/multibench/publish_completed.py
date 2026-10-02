"""Publish complete benchmark scores to the authorized experiment branch.

--watch checks every 30 seconds. Pilots and partial cohorts cannot enter the
completed table. Only the README and evaluation summaries/manifests are staged;
raw data, predictions, model files and implementation edits are never staged.
"""
import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import time

import leaderboard as B

BRANCH = 'experiment/multibench-20261002'
START = '<!-- completed-results:start -->'
END = '<!-- completed-results:end -->'


def completed_report(report):
    rows = [r for r in report['rows'] if r['full_comparison_eligible']
            and r.get('attempted') == r.get('expected') and r.get('expected',0) > 0]
    diagnostics = []
    for folder in ['longextract_v3','longextract_v4','longextract_v5']:
        source = folder+'/scores/full/summary.json'
        s = B.load(source)
        if s and s.get('eligible_for_public50_comparison') and s['attempted']==s['expected']==50:
            diagnostics.append({'benchmark':'LongExtractBench public 50', 'variant':s['profile'],
                'score':s['leaf_accuracy'], 'row_precision':s['row_precision'], 'row_recall':s['row_recall'],
                'successful':s['successful'],'failed':s['failed'],'expected':50,
                'reference_score_rank':None,'source_summary':source})
    return {'branch':BRANCH, 'rows':rows, 'unranked_complete_cohorts':diagnostics,
            'note':'Published-score references, not accepted external leaderboard ranks. Development and stored-output measurements retain their scope.'}


def render_completed(report):
    lines = [START, '## Completed full-cohort results', '',
        'These results cover every task in their stated cohort. Reference ranks compare published scores; no external leaderboard submission has been accepted. Stored-output and development results are labelled explicitly.', '',
        '| Benchmark | Configuration / measurement | Tasks | Score (%) | Reference rank | Gap to leader (pp) |',
        '|---|---|---:|---:|---|---:|']
    names = {'three_original_readings':'Original 3 readings; stored-output re-score',
             'four_readings':'Development 4 readings; stored-output re-score',
             'six_readings':'Tuned 6 readings; stored-output re-score'}
    for r in report['rows']:
        rank = str(r['reference_score_rank'])
        if r['ties_at_published_precision']: rank += ' (displayed tie)'
        gap = r['gap_to_leader_pp']
        if r['leader']['system'] in r['ties_at_published_precision']: gap = 0.
        variant = names.get(r['variant'],r['variant'])
        source = r['source_summary']
        lines.append(f"| {r['benchmark']} | [{variant}](results/multibench/{source}) | {r['expected']} | **{r['score']:.4f}** | {rank} | {gap:.4f} |")
    for r in report['unranked_complete_cohorts']:
        lines.append(f"| {r['benchmark']} | [{r['variant']}](results/multibench/{r['source_summary']}); {r['successful']}/50 successful | 50 | **{r['score']:.4f}** | Unknown on matching public cohort | — |")
    for r in report['unranked_complete_cohorts']:
        lines.extend(['',f"{r['variant']} public-50 row precision: {100*r['row_precision']:.4f}%; recall: {100*r['row_recall']:.4f}%; failures: {r['failed']}/50. Leaf accuracy averages successful documents only."])
    lines.extend(['', 'Pilots, selected routing checks and incomplete runs remain below in the experiment notes. They receive no full-cohort rank. This table refreshes and is committed/pushed whenever a complete score changes.', END])
    return '\n'.join(lines)


def update_readme(text, report):
    block = render_completed(report)
    if START in text:
        if text.count(START)!=1 or text.count(END)!=1: raise ValueError('Ambiguous README result markers')
        before, rest = text.split(START,1)
        _, after = rest.split(END,1)
        return before + block + after
    # Keep hand-written scope, protocol, caveats and reproduction notes intact.
    head, rest = text.split('\n',1)
    return head+'\n\n'+block+'\n'+rest


def git(*args):
    return subprocess.run(['git',*args],cwd=B.ROOT,check=True,text=True,capture_output=True).stdout.strip()


def publish_once():
    if git('branch','--show-current') != BRANCH:
        raise RuntimeError('Refusing to publish outside the authorized experiment branch')
    with (B.ROOT/'logs/multibench/publisher.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        all_results = B.build_report()
        complete = completed_report(all_results)
        path = B.ROOT/'RESULTS_README.md'
        current = path.read_text()
        updated = update_readme(current,complete)
        complete_path = B.OUT/'completed_results.json'
        encoded = json.dumps(complete,indent=2,ensure_ascii=False)+'\n'
        if updated == current and complete_path.exists() and complete_path.read_text() == encoded:
            # Retry a failed previous push without creating duplicate commits.
            dirty = git('status','--porcelain','--','RESULTS_README.md','results/multibench/completed_results.json','results/multibench/leaderboard.json')
            if not dirty:
                if git('rev-parse','HEAD') != git('rev-parse','refs/remotes/origin/'+BRANCH):
                    git('push','origin',BRANCH)
                return False
        path.write_text(updated)
        complete_path.write_text(encoded)
        temp = B.OUT/'publisher_leaderboard.json.tmp'
        temp.write_text(json.dumps(all_results,indent=2,ensure_ascii=False)+'\n')
        temp.replace(B.OUT/'leaderboard.json')
        paths = {path,complete_path,B.OUT/'leaderboard.json'}
        for r in complete['rows']+complete['unranked_complete_cohorts']:
            source = B.OUT/r['source_summary']
            paths.add(source)
            family = B.OUT/Path(r['source_summary']).parts[0]
            if family.is_dir():
                paths.update(p for p in family.glob('policy*.json'))
                if (family/'manifest.json').exists(): paths.add(family/'manifest.json')
        relative = sorted(str(p.relative_to(B.ROOT)) for p in paths)
        # Do not commit another worker's staged implementation changes.
        staged = set(git('diff','--cached','--name-only').splitlines())
        if staged-set(relative): raise RuntimeError('Unrelated staged changes; retry after the implementation commit')
        git('add','--',*relative)
        git('diff','--cached','--check')
        benchmarks = ', '.join(sorted({r['benchmark'] for r in complete['rows']+complete['unranked_complete_cohorts']}))
        message = 'Update completed benchmark results: '+benchmarks
        git('commit','-m',message)
        git('push','origin',BRANCH)
        print(f"Published {len(complete['rows'])} comparable full-cohort rows: {git('rev-parse','--short','HEAD')}",flush=True)
        return True


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch',action='store_true')
    args = parser.parse_args()
    (B.ROOT/'logs/multibench').mkdir(parents=True,exist_ok=True)
    while True:
        try: publish_once()
        except Exception as error:
            if not args.watch: raise
            print(f'Publication will retry: {type(error).__name__}: {error}',flush=True)
        if not args.watch: break
        time.sleep(30)
