#!/bin/bash
# VLLM_ENV: folder of a Python env with vllm==0.27.1 (optional; default: the `vllm` on your PATH)
export HF_HOME=${HF_HOME:-$HOME/.cache/huggingface}
[ -n "$VLLM_ENV" ] && export PATH="$VLLM_ENV/bin:$PATH"
export VLLM_USE_FLASHINFER_SAMPLER=0
unset CUDA_HOME
exec vllm serve opendatalab/MinerU2.5-2509-1.2B \
  --port 8081 --served-model-name mineru \
  --gpu-memory-utilization 0.13 \
  --max-model-len 16384 --limit-mm-per-prompt '{"image":1}' \
  --max-num-seqs 32
