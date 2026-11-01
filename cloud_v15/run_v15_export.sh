#!/bin/bash
# v1.5 云训第二步：合并 LoRA → 转 GGUF → Q6_K 量化（约 20-40 分钟）
set -e
cd /root/autodl-tmp

# 1) 合并 LoRA 回基座（GPU 上约 5-10 分钟）
python merge_v15.py

# 2) 装 llama.cpp 构建工具
pip install -q cmake gguf -i https://pypi.tuna.tsinghua.edu.cn/simple
if [ ! -d /root/autodl-tmp/llama.cpp ]; then
  git clone --depth 1 https://github.com/ggerganov/llama.cpp
fi
cd /root/autodl-tmp/llama.cpp
cmake -B build > /dev/null
cmake --build build -j --target llama-quantize

# 3) 转 GGUF（f16 全量，约 15GB）→ 删中间产物腾空间 → 量化 Q6_K（约 6.3GB，带回本地的那份）
# 注：数据盘仅 50GB，f16 转完后立刻删除 merged 目录（约 15GB），否则量化阶段磁盘溢出
python convert_hf_to_gguf.py /root/autodl-tmp/merged_v15 --outfile /root/autodl-tmp/poemly-v15-f16.gguf --outtype f16
rm -rf /root/autodl-tmp/merged_v15
./build/bin/llama-quantize /root/autodl-tmp/poemly-v15-f16.gguf /root/autodl-tmp/poemly-v15-Q6_K.gguf Q6_K

ls -lh /root/autodl-tmp/*.gguf
echo ALL_DONE
