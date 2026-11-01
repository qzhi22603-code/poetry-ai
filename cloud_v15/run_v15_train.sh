#!/bin/bash
# v1.5 云训第一步：装依赖 → 下 7B 基座 → 开训（约 40-80 分钟）
set -e
cd /root/autodl-tmp

# 1) 装训练依赖（镜像自带 torch，不必重装）
pip install -q transformers peft bitsandbytes accelerate "huggingface_hub[cli]" -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2) 下载 Qwen2.5-7B-Instruct（约 15GB，机房带宽一般 3-8 分钟）
# 注：huggingface-hub 2.x 已移除 huggingface-cli，改用 Python API 下载
export HF_ENDPOINT=https://hf-mirror.com
if [ ! -d /root/autodl-tmp/Qwen2.5-7B-Instruct ]; then
  python - <<'PYEOF'
from huggingface_hub import snapshot_download
snapshot_download("Qwen/Qwen2.5-7B-Instruct", local_dir="/root/autodl-tmp/Qwen2.5-7B-Instruct")
PYEOF
fi

# 3) 开训（2043 条 × 2 epoch，4090 约 40-80 分钟）
python train_v15.py
