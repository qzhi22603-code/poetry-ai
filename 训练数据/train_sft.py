# -*- coding: utf-8 -*-
"""poemly QLoRA 微调：Qwen2.5-3B-Instruct × poemly_sft_v1.json（3019条）
ChatML 格式，仅对助手回答计损失。产出 adapters/ LoRA 权重。"""
import json, os
import torch
from torch.utils.data import Dataset
from transformers import (AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig,
                          TrainingArguments, Trainer)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

BASE = r"C:\Users\38107\Desktop\ai\训练数据\base_model\models\Qwen--Qwen2.5-3B-Instruct\snapshots\master"
DATA = r"C:\Users\38107\Desktop\ai\训练数据\poemly_sft_v1.json"
OUT = r"C:\Users\38107\Desktop\ai\训练数据\adapters"
PERSONA = "你是poemly，一位精通古典诗词的创作助手。用韵依平水韵，讲究平仄对仗，先立意后作诗，写完逐联解意象，严禁编造典故。"

tok = AutoTokenizer.from_pretrained(BASE)
IM_END = "<|im_end|>"
EOS_ID = tok.convert_tokens_to_ids(IM_END)

raw = json.load(open(DATA, encoding="utf-8"))
print("样本数:", len(raw))

MAX_LEN = 768

def build(example):
    sys_text = example.get("_system") or PERSONA
    msgs = [{"role": "system", "content": sys_text},
            {"role": "user", "content": example["instruction"]},
            {"role": "assistant", "content": example["output"]}]
    full = tok.apply_chat_template(msgs, tokenize=False)
    prompt = tok.apply_chat_template(msgs[:2], tokenize=False)
    full_ids = tok(full, add_special_tokens=False)["input_ids"]
    prompt_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids):]
    return full_ids[:MAX_LEN], labels[:MAX_LEN]

class SFT(Dataset):
    def __init__(self, items):
        self.data = [build(x) for x in items]
        skipped = sum(1 for ids, lb in self.data if len(ids) >= MAX_LEN)
        print("超长截断:", skipped)
    def __len__(self):
        return len(self.data)
    def __getitem__(self, i):
        ids, lb = self.data[i]
        return {"input_ids": ids, "labels": lb}

def collate(batch):
    maxlen = max(len(x["input_ids"]) for x in batch)
    pad = tok.pad_token_id or EOS_ID
    input_ids, labels, attn = [], [], []
    for x in batch:
        n = len(x["input_ids"])
        input_ids.append(x["input_ids"] + [pad] * (maxlen - n))
        labels.append(x["labels"] + [-100] * (maxlen - n))
        attn.append([1] * n + [0] * (maxlen - n))
    return {"input_ids": torch.tensor(input_ids), "labels": torch.tensor(labels),
            "attention_mask": torch.tensor(attn)}

bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                         bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, device_map={"": 0})
model.config.use_cache = False
model = prepare_model_for_kbit_training(model)

lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                  target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
model = get_peft_model(model, lora)
model.print_trainable_parameters()

args = TrainingArguments(
    output_dir=OUT,
    num_train_epochs=3,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,
    learning_rate=1e-4,
    lr_scheduler_type="cosine",
    warmup_steps=20,
    bf16=True,
    gradient_checkpointing=True,
    logging_steps=10,
    save_strategy="no",
    report_to=[],
    optim="paged_adamw_8bit",
    dataloader_num_workers=0,
    seed=42,
)

ds = SFT(raw)
trainer = Trainer(model=model, args=args, train_dataset=ds, data_collator=collate)
trainer.train()
model.save_pretrained(os.path.join(OUT, "final"))
tok.save_pretrained(os.path.join(OUT, "final"))
print("TRAIN_DONE")
