# -*- coding: utf-8 -*-
"""v1.2 反抄袭训练：从基座全新开始，作诗样本全部原创。"""
import json, os
import torch
from torch.utils.data import Dataset
from transformers import (AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig,
                          TrainingArguments, Trainer)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

BASE = r"C:\Users\38107\Desktop\ai\训练数据\base_model\models\Qwen--Qwen2.5-3B-Instruct\snapshots\master"
DATA = r"C:\Users\38107\Desktop\ai\训练数据\poemly_sft_v13.json"
OUT = r"C:\Users\38107\Desktop\ai\训练数据\adapters_v13"
PERSONA = "你是poemly，一位精通古典诗词的创作助手。用韵依平水韵，讲究平仄对仗，先立意后作诗，写完逐联解意象。作诗必须独立创作，绝不抄录古人现成诗句；只有用户要求默写时才引原作。"

tok = AutoTokenizer.from_pretrained(BASE)
raw = json.load(open(DATA, encoding="utf-8"))
print("样本数:", len(raw), flush=True)

MAX_LEN = 896

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

def collate(batch):
    maxlen = max(len(x["input_ids"]) for x in batch)
    pad = tok.pad_token_id or 0
    return {"input_ids": torch.tensor([x["input_ids"] + [pad] * (maxlen - len(x["input_ids"])) for x in batch]),
            "labels": torch.tensor([x["labels"] + [-100] * (maxlen - len(x["labels"])) for x in batch]),
            "attention_mask": torch.tensor([[1] * len(x["input_ids"]) + [0] * (maxlen - len(x["input_ids"])) for x in batch])}

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
    output_dir=OUT, num_train_epochs=2, per_device_train_batch_size=1, gradient_accumulation_steps=16,
    learning_rate=1e-4, lr_scheduler_type="cosine", warmup_steps=15, bf16=True,
    gradient_checkpointing=True, logging_steps=5, save_strategy="no", report_to=[],
    optim="paged_adamw_8bit", dataloader_num_workers=0, seed=42)

trainer = Trainer(model=model, args=args, train_dataset=SFT(raw), data_collator=collate)
trainer.train()
model.save_pretrained(os.path.join(OUT, "final"))
tok.save_pretrained(os.path.join(OUT, "final"))
print("TRAIN_DONE")
