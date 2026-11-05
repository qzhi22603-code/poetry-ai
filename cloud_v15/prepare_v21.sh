#!/bin/bash
# v2.1 prepare：修环境（卸载不兼容的 torchvision）+ 验证 import 链，不训练
{
echo "[0] start $(date)"
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY

echo "[1] remove incompatible torchvision $(date)"
pip uninstall -y torchvision torchaudio 2>/dev/null
echo "[2] verify imports $(date)"
python - <<'PY'
import torch
print("torch", torch.__version__, "| cuda", torch.version.cuda)
import transformers, peft, accelerate, datasets
print("transformers", transformers.__version__, "| peft", peft.__version__, "| accelerate", accelerate.__version__)
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
print("core imports OK")
try:
    from transformers import BitsAndBytesConfig
    print("BitsAndBytesConfig OK")
except Exception as e:
    print("BitsAndBytesConfig MISSING:", e)
print("GPU available:", torch.cuda.is_available())
PY
echo "[3] check assets $(date)"
ls -la /root/autodl-tmp/poemly_sft_v21.json /root/autodl-tmp/train_v21.py /root/autodl-tmp/merge_v21.py
ls -la /root/autodl-tmp/Qwen2.5-7B-Instruct/config.json
find /root/autodl-tmp/llama.cpp -name llama-quantize -type f
df -h /root/autodl-tmp
echo "PREPARE_DONE $(date)"
} > /root/autodl-tmp/prep.log 2>&1
