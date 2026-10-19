# -*- coding: utf-8 -*-
"""v1.1：合并 LoRA → 存 HF 全量模型。"""
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

BASE = r"C:\Users\38107\Desktop\ai\训练数据\base_model\models\Qwen--Qwen2.5-3B-Instruct\snapshots\master"
ADP = r"C:\Users\38107\Desktop\ai\训练数据\adapters_v11\final"
MERGED = r"C:\Users\38107\Desktop\ai\训练数据\merged_v11"

tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16, device_map="cpu")
model = PeftModel.from_pretrained(model, ADP)
model = model.merge_and_unload()
model.save_pretrained(MERGED, safe_serialization=True)
tok.save_pretrained(MERGED)
print("MERGE_DONE:", MERGED)
