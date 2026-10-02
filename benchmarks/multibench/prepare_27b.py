"""Cache one pinned INT4 27B candidate without allocating GPU memory.

Existing 8B inference continues unchanged. GPU fit, extraction quality and
throughput must be measured separately before using this model in a cohort.
"""
import json
from pathlib import Path
import shutil

from huggingface_hub import HfApi,snapshot_download

REPO='ulkaa/Qwen3.8-27B-AWQ-INT4'
REVISION='2bf7f1646dc0875cff4404fdfef976cfb0ff2199'
ROOT=Path(__file__).resolve().parents[2]


def main():
    info=HfApi().model_info(REPO,revision=REVISION,files_metadata=True)
    if info.sha!=REVISION:raise ValueError('Model revision changed')
    weights=sum(f.size or 0 for f in info.siblings if f.rfilename.endswith('.safetensors'))
    # Download directly into the model cache, with room for temporary transfers.
    if shutil.disk_usage('/tmp').free<weights+5*2**30:
        raise RuntimeError('Insufficient disk for weights and transfer headroom')
    path=Path(snapshot_download(REPO,revision=REVISION,max_workers=2,
        allow_patterns=['*.safetensors','*.json','*.jinja','*.txt','README.md']))
    index=json.loads((path/'model.safetensors.index.json').read_text())
    files=set(index['weight_map'].values())
    if any(not (path/f).exists() for f in files):raise RuntimeError('Incomplete weight shards')
    out={'repo':REPO,'revision':REVISION,'snapshot':str(path),'weight_shards':len(files),
        'weights_bytes':weights,'mtp_tensors_present':any('mtp.' in k for k in index['weight_map']),
        'gpu_fit_verified':False,'extraction_score':None,'ready_on_disk':True,
        'source':'https://huggingface.co/'+REPO+'/tree/'+REVISION,
        'note':'CPU-only download. Keep existing GPU jobs and backbone measurements separate.'}
    (ROOT/'results/multibench/backbone_27b_int4_ready.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2),flush=True)


if __name__=='__main__':main()
