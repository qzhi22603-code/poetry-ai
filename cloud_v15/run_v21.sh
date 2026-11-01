#!/bin/bash
# v2.1 云端一键流程：训练 → 合并 → GGUF → Q6_K 量化
# 用法: nohup bash run_v21.sh > t21.log 2>&1 &
set -e
cd /root/autodl-tmp
echo "[1/4] train $(date)"
python train_v21.py
echo "[2/4] merge $(date)"
python merge_v21.py
echo "[3/4] convert-hf-to-gguf $(date)"
python llama.cpp/convert_hf_to_gguf.py merged_v21 --outfile poemly-v21-f16.gguf --outtype f16
echo "[4/4] quantize $(date)"
LLAMA_Q=$(find /root/autodl-tmp/llama.cpp -name llama-quantize -type f | head -1)
echo "quantize bin: $LLAMA_Q"
"$LLAMA_Q" poemly-v21-f16.gguf poemly-v21-Q6_K.gguf q6_k
echo "ALL_DONE $(date)"
