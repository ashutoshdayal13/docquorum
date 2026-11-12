#!/bin/bash
export HF_HOME=${HF_HOME:-$HOME/.cache/huggingface}
[ -n "$VLLM_ENV" ] && export PATH="$VLLM_ENV/bin:$PATH"
export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_USE_DEEP_GEMM=0
unset CUDA_HOME
exec vllm serve Qwen/Qwen3-VL-32B-Instruct-FP8 \
  --port 8079 --served-model-name qwen3vl \
  --gpu-memory-utilization ${GPU_UTIL:-0.90} \
  --max-model-len 32768 --limit-mm-per-prompt '{"image":2}' \
  --max-num-seqs 96
