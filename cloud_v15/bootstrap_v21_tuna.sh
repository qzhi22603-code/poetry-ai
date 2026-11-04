#!/bin/bash
# v2.1 修正版 5：走清华源升级 torch(cu128) → 更新代码 → 训练 → 合并 → 量化
{
echo "[0] start $(date)"
pkill -f "root/b4\.sh" 2>/dev/null
sleep 2
cd /root/autodl-tmp || exit 1

echo "[1] torch from tuna $(date)"
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
pip install -q -U torch -i https://pypi.tuna.tsinghua.edu.cn/simple
echo "[2] other deps $(date)"
pip install -q -U transformers peft accelerate datasets gguf modelscope -i https://pypi.tuna.tsinghua.edu.cn/simple

echo "[3] verify $(date)"
python - <<'PY'
import torch
print("torch", torch.__version__, "| cuda", torch.version.cuda, "| avail", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device", torch.cuda.get_device_name(0), "| capability", torch.cuda.get_device_capability(0))
    print("bf16", torch.cuda.is_bf16_supported())
import transformers, peft
print("transformers", transformers.__version__, "| peft", peft.__version__)
PY

echo "[4] refresh code $(date)"
source /etc/network_turbo 2>/dev/null || true
cd /root/autodl-tmp/poetry-ai
git fetch --depth 1 origin main && git reset --hard origin/main
cp cloud_v15/train_v21.py cloud_v15/merge_v21.py /root/autodl-tmp/
cd /root/autodl-tmp

echo "[5] train $(date)"
python train_v21.py

echo "[6] merge $(date)"
python merge_v21.py

echo "[7] gguf $(date)"
python llama.cpp/convert_hf_to_gguf.py merged_v21 --outfile poemly-v21-f16.gguf --outtype f16
rm -rf merged_v21
df -h /root/autodl-tmp
Q=$(find /root/autodl-tmp/llama.cpp -name llama-quantize -type f | head -1)
echo "quantize bin: $Q"
"$Q" poemly-v21-f16.gguf poemly-v21-Q6_K.gguf q6_k
rm -f poemly-v21-f16.gguf

echo "[8] disk $(date)"
df -h /root/autodl-tmp
ls -la /root/autodl-tmp/poemly-v21-Q6_K.gguf
echo "ALL_DONE $(date)"
} > /root/autodl-tmp/t21e.log 2>&1
