#!/bin/bash
# Qwen3-VL-32B-Instruct, dense, FP8 (native on the H100 NVL). Served under the same model
# name as the 8B so every script works unchanged; the two cannot share the card.
# VLLM_ENV: folder of a Python env with vllm==0.27.1 (optional; default: the `vllm` on your PATH)
export HF_HOME=${HF_HOME:-$HOME/.cache/huggingface}
[ -n "$VLLM_ENV" ] && export PATH="$VLLM_ENV/bin:$PATH"
export VLLM_USE_FLASHINFER_SAMPLER=0
# FP8 would JIT-compile DeepGEMM kernels, which need nvcc >= 12.3; this env has no CUDA
# toolkit, so use the prebuilt CUTLASS / Triton FP8 kernels instead.
export VLLM_USE_DEEP_GEMM=0
unset CUDA_HOME
exec vllm serve Qwen/Qwen3-VL-32B-Instruct-FP8 \
  --port 8079 --served-model-name qwen3vl \
  --gpu-memory-utilization ${GPU_UTIL:-0.90} \
  --max-model-len 32768 --limit-mm-per-prompt '{"image":2}' \
  --max-num-seqs 96
