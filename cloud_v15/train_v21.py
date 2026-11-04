# -*- coding: utf-8 -*-
# ============================================================================
# 【v1.5 云端训练脚本（AutoDL 4090 用）】
# 由 train_v14.py 改造，三处变化：
#   ① BASE 换成 Qwen2.5-7B-Instruct（本地目录 /root/autodl-tmp/Qwen2.5-7B-Instruct）；
#   ② DATA 换成 poemly_sft_v21.json（2250 条，含 35 首金标准 + 一键多原型立意）；
#   ③ 4090 显存 24GB 富余：per_device_batch 1→4、累积 16→4（等效 batch 仍=16，
#      优化动力学不变，速度提升约 3-4 倍）。
# 其余配方与 v1.2/v1.3/v1.4 完全一致：2 epoch、lr 1e-4、余弦退火、预热 15 步、
# 4bit NF4 双量化、LoRA r=16 alpha=32、paged_adamw_8bit、梯度检查点。
# 输出：/root/autodl-tmp/adapters_v21/final 下的 LoRA 权重与分词器。
# ============================================================================
"""v2.1 云训：Qwen2.5-7B 基座 + poemly_sft_v21 数据，全新 LoRA 从零训练。"""
import json, os
import torch
from torch.utils.data import Dataset
from transformers import (AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig,
                          TrainingArguments, Trainer)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

# 基座：云端本地目录（run_v21_train.sh 已用 hf-mirror 下载好）
BASE = "/root/autodl-tmp/Qwen2.5-7B-Instruct"
# v1.5 数据：2250 条原创样本
DATA = "/root/autodl-tmp/poemly_sft_v21.json"
# 本轮输出目录
OUT = "/root/autodl-tmp/adapters_v21"
# 反抄袭版人设：与 v1.4 保持一致——独立创作、绝不抄录古人现成诗句
PERSONA = "你是poemly，一位精通古典诗词的创作助手。用韵依平水韵，讲究平仄对仗，先立意后作诗，写完逐联解意象。作诗必须独立创作，绝不抄录古人现成诗句；只有用户要求默写时才引原作。"

# 加载分词器
tok = AutoTokenizer.from_pretrained(BASE)
raw = json.load(open(DATA, encoding="utf-8"))
print("样本数:", len(raw), flush=True)
# 单条最大 token 数：与 v1.4 一致，超长截断防显存爆
MAX_LEN = 896

# Alpaca 样本 →（编号序列, 标签序列）；回答部分才算损失，问题部分 -100 屏蔽
def build(example):
    sys_text = example.get("_system") or PERSONA
    msgs = [{"role": "system", "content": sys_text},
            {"role": "user", "content": example["instruction"]},
            {"role": "assistant", "content": example["output"]}]
    full = tok.apply_chat_template(msgs, tokenize=False)
    prompt = tok.apply_chat_template(msgs[:2], tokenize=False)
    full_ids = tok(full, add_special_tokens=False)["input_ids"][:MAX_LEN]
    prompt_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids):]
    return full_ids, labels[:MAX_LEN]

class SFT(Dataset):
    def __init__(self, items):
        self.data = [build(x) for x in items]
    def __len__(self):
        return len(self.data)
    def __getitem__(self, i):
        return dict(zip(("input_ids", "labels"), self.data[i]))

# 动态 padding 拼批
def collate(batch):
    maxlen = max(len(x["input_ids"]) for x in batch)
    pad = tok.pad_token_id or 0
    return {"input_ids": torch.tensor([x["input_ids"] + [pad] * (maxlen - len(x["input_ids"])) for x in batch]),
            "labels": torch.tensor([x["labels"] + [-100] * (maxlen - len(x["labels"])) for x in batch]),
            "attention_mask": torch.tensor([[1] * len(x["input_ids"]) + [0] * (maxlen - len(x["input_ids"])) for x in batch])}

# 载入基座：大显存(>=40GB)直接 bf16 LoRA，稳且准；小卡走 4bit QLoRA
MEM = torch.cuda.get_device_properties(0).total_memory / 1024**3
if MEM >= 40:
    print(f"[load] GPU {MEM:.1f}GB -> bf16 LoRA（不量化）", flush=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16, device_map={"": 0})
else:
    print(f"[load] GPU {MEM:.1f}GB -> 4bit QLoRA", flush=True)
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, device_map={"": 0})
    model = prepare_model_for_kbit_training(model)
model.config.use_cache = False
# LoRA 配置（QLoRA 的 LoRA）：r=16、alpha=32、七个线性层全插旁路
lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                  target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
model = get_peft_model(model, lora)
model.print_trainable_parameters()

# 超参：按显存自适应批大小，等效 batch 恒为 16（优化动力学不变）
# 24GB(4090)=4x4；16GB(4060Ti/4080)=2x8；12GB(3080)=1x16
BS = 4 if MEM >= 20 else (2 if MEM >= 14 else 1)
GA = 16 // BS
print(f"GPU 显存 {MEM:.1f}GB -> batch {BS} x accum {GA} (等效 {BS * GA})", flush=True)
args = TrainingArguments(
    output_dir=OUT, num_train_epochs=2, per_device_train_batch_size=BS, gradient_accumulation_steps=GA,
    learning_rate=1e-4, lr_scheduler_type="cosine", warmup_steps=15, bf16=torch.cuda.is_bf16_supported(),
    gradient_checkpointing=True, logging_steps=5, save_strategy="no", report_to=[],
    optim="paged_adamw_8bit", dataloader_num_workers=0, seed=42)

trainer = Trainer(model=model, args=args, train_dataset=SFT(raw), data_collator=collate)
trainer.train()
model.save_pretrained(os.path.join(OUT, "final"))
tok.save_pretrained(os.path.join(OUT, "final"))
print("TRAIN_DONE")

