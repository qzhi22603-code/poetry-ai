#!/bin/bash
cd /root/autodl-tmp
export HF_ENDPOINT=https://hf-mirror.com
python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen2.5-7B-Instruct', local_dir='/root/autodl-tmp/Qwen2.5-7B-Instruct')"
echo HF_DL_DONE
