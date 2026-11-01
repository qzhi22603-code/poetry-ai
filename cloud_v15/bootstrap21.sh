#!/bin/bash
{
cd /root/autodl-tmp
rm -f poemly-v15-f16.gguf
source /etc/network_turbo 2>/dev/null
rm -rf poetry-ai
git clone --depth 1 https://github.com/qzhi22603-code/poetry-ai 2>&1
cp "poetry-ai/训练数据/poemly_sft_v21.json" /root/autodl-tmp/poemly_sft_v21.json
cp poetry-ai/cloud_v15/train_v21.py poetry-ai/cloud_v15/merge_v21.py /root/autodl-tmp/
cat > /root/autodl-tmp/run_v21.sh <<'EOS'
#!/bin/bash
set -e
cd /root/autodl-tmp
echo "[1/4] train $(date)"
python train_v21.py
echo "[2/4] merge $(date)"
python merge_v21.py
echo "[3/4] convert $(date)"
cd /root/autodl-tmp/llama.cpp
python convert_hf_to_gguf.py /root/autodl-tmp/merged_v21 --outfile /root/autodl-tmp/poemly-v21-f16.gguf --outtype f16
rm -rf /root/autodl-tmp/merged_v21
./build/bin/llama-quantize /root/autodl-tmp/poemly-v21-f16.gguf /root/autodl-tmp/poemly-v21-Q6_K.gguf Q6_K
rm -f /root/autodl-tmp/poemly-v21-f16.gguf
echo "ALL_DONE $(date)"
EOS
chmod +x /root/autodl-tmp/run_v21.sh
echo "--- disk ---"
df -h /root/autodl-tmp
ls -la /root/autodl-tmp/poemly_sft_v21.json
} > /root/autodl-tmp/f21.log 2>&1
echo BOOTSTRAP_DONE >> /root/autodl-tmp/f21.log
