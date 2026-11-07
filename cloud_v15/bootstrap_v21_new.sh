#!/bin/bash
# v2.1 全新实例一键：torch(cu128) → 依赖 → 代码+数据 → 底模 → llama.cpp → 训练 → 合并 → 量化
{
echo "[0] start $(date)"
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
cd /root/autodl-tmp || exit 1

echo "[1] torch $(date)"
pip install -q -U torch -i https://mirrors.aliyun.com/pypi/simple/
pip uninstall -y torchvision torchaudio 2>/dev/null
echo "[2] deps $(date)"
pip install -q -U transformers peft accelerate datasets gguf modelscope bitsandbytes sentencepiece -i https://mirrors.aliyun.com/pypi/simple/

echo "[3] verify $(date)"
python - <<'PY'
import torch
print("torch", torch.__version__, "| cuda", torch.version.cuda, "| avail", torch.cuda.is_available())
if torch.cuda.is_available():
    print("dev", torch.cuda.get_device_name(0), "| cap", torch.cuda.get_device_capability(0))
import transformers, peft
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
print("imports OK |", transformers.__version__, peft.__version__)
PY

echo "[4] repo+data $(date)"
source /etc/network_turbo 2>/dev/null || true
rm -rf /root/autodl-tmp/poetry-ai
git clone --depth 1 https://github.com/qzhi22603-code/poetry-ai /root/autodl-tmp/poetry-ai
python - <<'PY'
import glob, shutil
s = glob.glob('/root/autodl-tmp/poetry-ai/**/poemly_sft_v21.json', recursive=True)
print("data found:", s)
shutil.copy(s[0], '/root/autodl-tmp/poemly_sft_v21.json')
print("copied")
PY
cp /root/autodl-tmp/poetry-ai/cloud_v15/train_v21.py /root/autodl-tmp/poetry-ai/cloud_v15/merge_v21.py /root/autodl-tmp/

echo "[5] model $(date)"
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
python -c "from modelscope import snapshot_download; snapshot_download('Qwen/Qwen2.5-7B-Instruct', local_dir='/root/autodl-tmp/Qwen2.5-7B-Instruct')"
du -sh /root/autodl-tmp/Qwen2.5-7B-Instruct

echo "[6] llama.cpp $(date)"
source /etc/network_turbo 2>/dev/null || true
git clone --depth 1 https://github.com/ggerganov/llama.cpp /root/autodl-tmp/llama.cpp
cd /root/autodl-tmp/llama.cpp
cmake -B build -DGGML_CUDA=OFF
cmake --build build --target llama-quantize -j 2>/dev/null || cmake --build build -j
find . -name "llama-quantize" -type f

echo "[7] train $(date)"
cd /root/autodl-tmp
python train_v21.py

echo "[8] merge $(date)"
python merge_v21.py

echo "[9] gguf $(date)"
python llama.cpp/convert_hf_to_gguf.py merged_v21 --outfile poemly-v21-f16.gguf --outtype f16
rm -rf merged_v21
Q=$(find /root/autodl-tmp/llama.cpp -name llama-quantize -type f | head -1)
echo "quantize bin: $Q"
"$Q" poemly-v21-f16.gguf poemly-v21-Q6_K.gguf q6_k
rm -f poemly-v21-f16.gguf

echo "[10] disk $(date)"
df -h /root/autodl-tmp
ls -la /root/autodl-tmp/poemly-v21-Q6_K.gguf
echo "ALL_DONE $(date)"
} > /root/autodl-tmp/t21f.log 2>&1
