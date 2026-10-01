#!/bin/bash
ENV=${VLLM_ENV:-/home/krudra_mtp/miniconda3/envs/dae-vllm}   # a Python env with vllm==0.27.1
export HF_HOME=${HF_HOME:-/tmp/hf_parse}
export PATH="$ENV/bin:$PATH"
export VLLM_USE_FLASHINFER_SAMPLER=0
unset CUDA_HOME
exec $ENV/bin/vllm serve opendatalab/MinerU2.5-2509-1.2B \
  --port 8081 --served-model-name mineru \
  --gpu-memory-utilization 0.13 \
  --max-model-len 16384 --limit-mm-per-prompt '{"image":1}' \
  --max-num-seqs 32
