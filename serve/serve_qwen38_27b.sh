#!/bin/bash
export HF_HOME=${HF_HOME:-$HOME/.cache/huggingface}
[ -n "$VLLM_ENV" ] && export PATH="$VLLM_ENV/bin:$PATH"
export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_USE_DEEP_GEMM=0
unset CUDA_HOME
MM_SPEC=${MM_SPEC:-'{"image":{"count":12,"width":1700,"height":1700}}'}
SPEC=()
[ "${SPEC_TOKENS:-0}" -gt 0 ] && SPEC=(--speculative-config "{\"method\":\"qwen3_5_mtp\",\"num_speculative_tokens\":${SPEC_TOKENS}}")
exec vllm serve Qwen/Qwen3.8-27B-FP8 \
  --port 8079 --served-model-name qwen3vl \
  --gpu-memory-utilization ${GPU_UTIL:-0.74} \
  --max-model-len ${MAX_LEN:-131072} --limit-mm-per-prompt "$MM_SPEC" \
  --max-num-seqs ${MAX_SEQS:-48} --max-num-batched-tokens ${MAX_BATCH:-8192} "${SPEC[@]}"
