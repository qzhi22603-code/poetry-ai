#!/bin/bash
# v2.1 续跑：修优化器(bnb)问题 → 补建 llama.cpp → 训练 → 合并 → GGUF → 量化
{
echo "[0] start $(date)"
cd /root/autodl-tmp || exit 1
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY

echo "[1] bitsandbytes $(date)"
pip install -q -U bitsandbytes -i https://pypi.tuna.tsinghua.edu.cn/simple

echo "[2] refresh code $(date)"
source /etc/network_turbo 2>/dev/null || true
cd /root/autodl-tmp/poetry-ai
git fetch --depth 1 origin main && git reset --hard origin/main
cp cloud_v15/train_v21.py cloud_v15/merge_v21.py /root/autodl-tmp/
grep -n "OPT = " /root/autodl-tmp/train_v21.py
cd /root/autodl-tmp

echo "[3] llama.cpp $(date)"
rm -rf /root/autodl-tmp/llama.cpp
for i in 1 2; do
  git clone --depth 1 https://github.com/ggerganov/llama.cpp /root/autodl-tmp/llama.cpp && break
  echo "clone retry $i"
  sleep 5
done
if [ -d /root/autodl-tmp/llama.cpp ]; then
  cd /root/autodl-tmp/llama.cpp
  cmake -B build -DGGML_CUDA=OFF
  cmake --build build --target llama-quantize -j 2>/dev/null || cmake --build build -j
  find . -name "llama-quantize" -type f
else
  echo "WARN: llama.cpp clone failed, GGUF step will be skipped"
fi

echo "[4] train $(date)"
cd /root/autodl-tmp
python train_v21.py

echo "[5] merge $(date)"
python merge_v21.py

echo "[6] gguf $(date)"
if [ -f /root/autodl-tmp/llama.cpp/convert_hf_to_gguf.py ]; then
  python /root/autodl-tmp/llama.cpp/convert_hf_to_gguf.py merged_v21 --outfile poemly-v21-f16.gguf --outtype f16
  rm -rf merged_v21
  Q=$(find /root/autodl-tmp/llama.cpp -name llama-quantize -type f | head -1)
  echo "quantize bin: $Q"
  "$Q" poemly-v21-f16.gguf poemly-v21-Q6_K.gguf q6_k
  rm -f poemly-v21-f16.gguf
else
  echo "SKIP gguf: llama.cpp missing, adapters kept at adapters_v21/final"
fi

echo "[7] disk $(date)"
df -h /root/autodl-tmp
ls -la /root/autodl-tmp/adapters_v21/final 2>/dev/null | head -5
ls -la /root/autodl-tmp/poemly-v21-Q6_K.gguf 2>/dev/null
echo "ALL_DONE $(date)"
} > /root/autodl-tmp/t21g.log 2>&1
