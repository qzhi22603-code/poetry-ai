#!/bin/bash
pip install -q sentencepiece protobuf -i https://pypi.tuna.tsinghua.edu.cn/simple
cd /root/autodl-tmp/llama.cpp
cmake -B build > /dev/null
cmake --build build -j --target llama-quantize
python convert_hf_to_gguf.py /root/autodl-tmp/merged_v15 --outfile /root/autodl-tmp/poemly-v15-f16.gguf --outtype f16
rm -rf /root/autodl-tmp/merged_v15
./build/bin/llama-quantize /root/autodl-tmp/poemly-v15-f16.gguf /root/autodl-tmp/poemly-v15-Q6_K.gguf Q6_K
ls -lh /root/autodl-tmp/*.gguf
echo ALL_DONE
