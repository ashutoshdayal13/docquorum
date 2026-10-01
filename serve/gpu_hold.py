"""
Hold GPU memory for this week's GPU assignment (run with the assignee's explicit permission).

Takes only memory that is currently FREE, always leaves --margin GB untouched so our own
running vLLM server is never starved, grows as more memory frees up, and never releases on
its own. It releases only when we create the release file -- to hand the memory straight to
our own larger vLLM server:

    python gpu_hold.py &                        # start holding
    touch /tmp/claude-1059/gpu_hold.release     # release (only to restart our own server)

A control file allows a handoff without a full release: writing
    {"pause": true, "keep_gb": 0}
to /tmp/claude-1059/gpu_hold.ctl frees memory down to keep_gb and STOPS re-grabbing, so the
freed memory can go to our own new server; {"pause": false} resumes grabbing.
"""
import argparse, os, signal, time
import torch

ap = argparse.ArgumentParser()
ap.add_argument("--margin", type=float, default=2.5, help="GB always left free")
ap.add_argument("--chunk", type=float, default=1.0, help="GB per allocation")
ap.add_argument("--poll", type=float, default=5.0, help="seconds between checks")
ap.add_argument("--release-file", default="/tmp/claude-1059/gpu_hold.release")
ap.add_argument("--ctl-file", default="/tmp/claude-1059/gpu_hold.ctl")
a = ap.parse_args()
if os.path.exists(a.release_file):
    os.remove(a.release_file)
GB = 1 << 30
held, stop, last = [], False, -1


def _stop(*_):
    global stop
    stop = True


signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)
import json


def control():
    try:
        return json.load(open(a.ctl_file))
    except Exception:
        return {}


while not stop and not os.path.exists(a.release_file):
    c = control()
    if c.get("pause"):
        keep = int(c.get("keep_gb", 0) / a.chunk)
        if len(held) > keep:
            del held[keep:]
            torch.cuda.empty_cache()
            print(f"{time.strftime('%H:%M:%S')} paused: released down to {len(held) * a.chunk:.0f} GB", flush=True)
            last = len(held)
        time.sleep(a.poll)
        continue
    spare = torch.cuda.mem_get_info()[0] / GB - a.margin
    while spare >= a.chunk and not os.path.exists(a.release_file):
        try:
            held.append(torch.empty(int(a.chunk * GB), dtype=torch.uint8, device="cuda"))
        except RuntimeError:
            break
        spare -= a.chunk
    if len(held) != last:
        print(f"{time.strftime('%H:%M:%S')} holding {len(held) * a.chunk:.0f} GB "
              f"(free now {torch.cuda.mem_get_info()[0] / GB:.1f} GB)", flush=True)
        last = len(held)
    time.sleep(a.poll)
held.clear()
torch.cuda.empty_cache()
if os.path.exists(a.release_file):
    os.remove(a.release_file)
print(f"{time.strftime('%H:%M:%S')} released", flush=True)
