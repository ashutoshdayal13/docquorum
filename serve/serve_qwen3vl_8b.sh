#!/bin/bash
ENV=${VLLM_ENV:-/home/krudra_mtp/miniconda3/envs/dae-vllm}   # a Python env with vllm==0.27.1
export HF_HOME=${HF_HOME:-/home/krudra_mtp/ashutosh/hf_cache}
export PATH="$ENV/bin:$PATH"
export VLLM_USE_FLASHINFER_SAMPLER=0
unset CUDA_HOME
exec $ENV/bin/vllm serve Qwen/Qwen3-VL-8B-Instruct \
  --port 8078 --served-model-name qwen3vl \
  --gpu-memory-utilization 0.80 \
  --max-model-len 32768 --limit-mm-per-prompt '{"image":4}' \
  --max-num-seqs 48
