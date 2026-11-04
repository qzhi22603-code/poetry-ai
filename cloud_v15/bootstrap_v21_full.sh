#!/bin/bash
# v2.1 新实例一键自举：依赖 → 数据 → 底模 → llama.cpp → 训练 → 合并 → GGUF → Q6_K
# 全流程输出写 /root/autodl-tmp/t21.log
{
echo "[0] start $(date)"
cd /root/autodl-tmp || exit 1
source /etc/network_turbo 2>/dev/null || true

echo "[1] deps $(date)"
pip install -q transformers peft "bitsandbytes>=0.45" accelerate datasets gguf modelscope

echo "[2] clone repo $(date)"
rm -rf poetry-ai
git clone --depth 1 https://github.com/qzhi22603-code/poetry-ai

echo "[3] copy data+scripts $(date)"
find poetry-ai -name "poemly_sft_v21.json" -exec cp {} /root/autodl-tmp/ \;
cp poetry-ai/cloud_v15/train_v21.py poetry-ai/cloud_v15/merge_v21.py /root/autodl-tmp/
ls -la /root/autodl-tmp/poemly_sft_v21.json /root/autodl-tmp/train_v21.py

echo "[4] base model $(date)"
if [ ! -f /root/autodl-tmp/Qwen2.5-7B-Instruct/config.json ]; then
  python -c "from modelscope import snapshot_download; snapshot_download('Qwen/Qwen2.5-7B-Instruct', local_dir='/root/autodl-tmp/Qwen2.5-7B-Instruct')"
fi
du -sh /root/autodl-tmp/Qwen2.5-7B-Instruct

echo "[5] llama.cpp $(date)"
if [ ! -d /root/autodl-tmp/llama.cpp ]; then
  git clone --depth 1 https://github.com/ggerganov/llama.cpp /root/autodl-tmp/llama.cpp
fi
cd /root/autodl-tmp/llama.cpp
if [ ! -d build ]; then
  cmake -B build -DGGML_CUDA=OFF
  cmake --build build --target llama-quantize -j 2>/dev/null || cmake --build build -j
fi
find . -name "llama-quantize" -type f

echo "[6] train $(date)"
cd /root/autodl-tmp
python train_v21.py

echo "[7] merge $(date)"
python merge_v21.py

echo "[8] gguf$(date)"
python llama.cpp/convert_hf_to_gguf.py merged_v21 --outfile poemly-v21-f16.gguf --outtype f16
Q=$(find /root/autodl-tmp/llama.cpp -name llama-quantize -type f | head -1)
echo "quantize bin: $Q"
"$Q" poemly-v21-f16.gguf poemly-v21-Q6_K.gguf q6_k
rm -f poemly-v21-f16.gguf
rm -rf merged_v21

echo "[9] disk $(date)"
df -h /root/autodl-tmp
ls -la /root/autodl-tmp/poemly-v21-Q6_K.gguf
echo "ALL_DONE $(date)"
} > /root/autodl-tmp/t21.log 2>&1
