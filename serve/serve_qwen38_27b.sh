#!/bin/bash
# Qwen3.8-27B (FP8) -- the model behind the leaderboard's "Qwen3.8 27B" open-weight entry
# (one-shot: Overall 89.75, Short 94.68, Medium 87.54, Long 38.45), so our pipeline and the
# benchmark's own baseline can be compared on the same weights.
# VLLM_ENV: folder of a Python env with vllm==0.27.1 (optional; default: the `vllm` on your PATH)
export HF_HOME=${HF_HOME:-$HOME/.cache/huggingface}
[ -n "$VLLM_ENV" ] && export PATH="$VLLM_ENV/bin:$PATH"
export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_USE_DEEP_GEMM=0      # FP8 DeepGEMM JIT needs nvcc >= 12.3, not installed
unset CUDA_HOME
# MM_SPEC sizes vLLM's startup profiling: with 12 images at the model's MAXIMUM resolution
# the dummy batch left no memory for the KV cache. Pages are sent at ~150 DPI (<= 2.6 MP).
MM_SPEC=${MM_SPEC:-'{"image":{"count":12,"width":1700,"height":1700}}'}
exec vllm serve Qwen/Qwen3.8-27B-FP8 \
  --port 8079 --served-model-name qwen3vl \
  --gpu-memory-utilization ${GPU_UTIL:-0.74} \
  --max-model-len ${MAX_LEN:-131072} --limit-mm-per-prompt "$MM_SPEC" \
  --max-num-seqs ${MAX_SEQS:-48} --max-num-batched-tokens ${MAX_BATCH:-8192}
