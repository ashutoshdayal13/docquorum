#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source configs/local.env
export VLLM_USE_FLASHINFER_SAMPLER=0 VLLM_USE_DEEP_GEMM=0
unset CUDA_HOME
exec "$VLLM_ENV/bin/vllm" serve Qwen/Qwen3-VL-8B-Instruct-FP8 \
  --revision 9cdc6310a8cb770ce18efaf4e9935334512aee45 \
  --host 127.0.0.1 --port 8078 --served-model-name dq-multibench8b \
  --generation-config vllm --gpu-memory-utilization 0.18 \
  --max-model-len 32768 --max-num-seqs 4 --max-num-batched-tokens 2048 \
  --limit-mm-per-prompt '{"image":{"count":1,"width":1700,"height":1700}}' \
  --enforce-eager
