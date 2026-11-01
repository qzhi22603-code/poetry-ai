# -*- coding: utf-8 -*-
# ============================================================================
# 【v1.5 云端合并导出脚本（训练完成后运行）】
# 由 merge_and_export.py 改造：把 adapters_v15 的 LoRA 增量数学合并回
# Qwen2.5-7B 基座（W' = W + B·A），导出标准 HF 格式模型目录 merged_v15，
# 供 llama.cpp 转 GGUF + Q6_K 量化。
# 与本地版的差异：BASE 换 7B 云端目录；合并优先在 GPU 上做（7B bf16 约 15GB，
# 4090 的 24GB 放得下，比 CPU 快数倍）；无 GPU 环境自动退回 CPU。
# ============================================================================
"""合并 LoRA → merged_v15（HF 全量），交由 llama.cpp 转 GGUF。"""
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

# 基座：7B 本地目录
BASE = "/root/autodl-tmp/Qwen2.5-7B-Instruct"
# 训练产出的 LoRA adapter
ADP = "/root/autodl-tmp/adapters_v15/final"
# 合并输出目录
MERGED = "/root/autodl-tmp/merged_v15"

tok = AutoTokenizer.from_pretrained(BASE)
# 有 GPU 用 GPU 合并（快），否则退回 CPU
DEV = {"": 0} if torch.cuda.is_available() else "cpu"
model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16, device_map=DEV)
model = PeftModel.from_pretrained(model, ADP)
# ★核心：增量 B·A 加进基座权重并卸载 LoRA 包装，得到纯 transformers 模型
model = model.merge_and_unload()
model.save_pretrained(MERGED, safe_serialization=True)
tok.save_pretrained(MERGED)
print("MERGE_DONE:", MERGED)
