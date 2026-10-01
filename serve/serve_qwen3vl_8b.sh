#!/bin/bash
# VLLM_ENV: folder of a Python env with vllm==0.27.1 (optional; default: the `vllm` on your PATH)
export HF_HOME=${HF_HOME:-$HOME/.cache/huggingface}
[ -n "$VLLM_ENV" ] && export PATH="$VLLM_ENV/bin:$PATH"
export VLLM_USE_FLASHINFER_SAMPLER=0
unset CUDA_HOME
exec vllm serve Qwen/Qwen3-VL-8B-Instruct \
  --port 8078 --served-model-name qwen3vl \
  --gpu-memory-utilization 0.80 \
  --max-model-len 32768 --limit-mm-per-prompt '{"image":4}' \
  --max-num-seqs 48
