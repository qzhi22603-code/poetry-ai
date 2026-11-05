#!/bin/bash
# 只补 GGUF：克隆 llama.cpp → 编译 → 转换 → Q6_K 量化
{
echo "[0] start $(date)"
cd /root/autodl-tmp || exit 1
source /etc/network_turbo 2>/dev/null || true

echo "[1] clone llama.cpp $(date)"
rm -rf /root/autodl-tmp/llama.cpp
ok=0
for i in 1 2 3; do
  git clone --depth 1 https://github.com/ggerganov/llama.cpp /root/autodl-tmp/llama.cpp && ok=1 && break
  echo "retry $i"; sleep 10
done
if [ $ok -ne 1 ]; then
  echo "CLONE_FAILED"
  echo "ALL_DONE $(date)"
  exit 0
fi

echo "[2] build $(date)"
cd /root/autodl-tmp/llama.cpp
cmake -B build -DGGML_CUDA=OFF
cmake --build build --target llama-quantize -j 2>/dev/null || cmake --build build -j
find . -name "llama-quantize" -type f

echo "[3] convert $(date)"
cd /root/autodl-tmp
python llama.cpp/convert_hf_to_gguf.py merged_v21 --outfile poemly-v21-f16.gguf --outtype f16
rm -rf merged_v21
df -h /root/autodl-tmp

echo "[4] quantize $(date)"
Q=$(find /root/autodl-tmp/llama.cpp -name llama-quantize -type f | head -1)
echo "bin: $Q"
"$Q" poemly-v21-f16.gguf poemly-v21-Q6_K.gguf q6_k
rm -f poemly-v21-f16.gguf

echo "[5] done $(date)"
df -h /root/autodl-tmp
ls -la /root/autodl-tmp/poemly-v21-Q6_K.gguf
echo "ALL_DONE $(date)"
} > /root/autodl-tmp/t21h.log 2>&1
