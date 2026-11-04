#!/bin/bash
# v2.1 修正版 3：修复自杀问题（不再 pkill 自身），ModelScope 直连、GitHub 走加速
{
echo "[0] start $(date)"
ps aux | grep -E "root/b\.sh|snapshot_download|modelscope" | grep -v grep
pkill -f "root/b\.sh" 2>/dev/null
pkill -f "snapshot_download" 2>/dev/null
sleep 2
cd /root/autodl-tmp || exit 1

echo "[1] model domestic-direct $(date)"
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
if [ ! -f /root/autodl-tmp/Qwen2.5-7B-Instruct/config.json ]; then
  rm -rf /root/autodl-tmp/Qwen2.5-7B-Instruct
  python -c "from modelscope import snapshot_download; snapshot_download('Qwen/Qwen2.5-7B-Instruct', local_dir='/root/autodl-tmp/Qwen2.5-7B-Instruct')"
fi
du -sh /root/autodl-tmp/Qwen2.5-7B-Instruct

echo "[2] llama.cpp via turbo $(date)"
source /etc/network_turbo 2>/dev/null || true
if [ ! -d /root/autodl-tmp/llama.cpp ]; then
  git clone --depth 1 https://github.com/ggerganov/llama.cpp /root/autodl-tmp/llama.cpp
fi
cd /root/autodl-tmp/llama.cpp
if [ ! -d build ]; then
  cmake -B build -DGGML_CUDA=OFF
  cmake --build build --target llama-quantize -j 2>/dev/null || cmake --build build -j
fi
find . -name "llama-quantize" -type f

echo "[3] train $(date)"
cd /root/autodl-tmp
python train_v21.py

echo "[4] merge $(date)"
python merge_v21.py

echo "[5] gguf $(date)"
python llama.cpp/convert_hf_to_gguf.py merged_v21 --outfile poemly-v21-f16.gguf --outtype f16
rm -rf merged_v21
df -h /root/autodl-tmp
Q=$(find /root/autodl-tmp/llama.cpp -name llama-quantize -type f | head -1)
echo "quantize bin: $Q"
"$Q" poemly-v21-f16.gguf poemly-v21-Q6_K.gguf q6_k
rm -f poemly-v21-f16.gguf

echo "[6] disk $(date)"
df -h /root/autodl-tmp
ls -la /root/autodl-tmp/poemly-v21-Q6_K.gguf
echo "ALL_DONE $(date)"
} > /root/autodl-tmp/t21c.log 2>&1
