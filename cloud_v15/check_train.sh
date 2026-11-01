#!/bin/bash
echo "=== loss 走势 ==="
grep -o "loss: [0-9.]*" /root/autodl-tmp/train.log | tail -5
echo "=== 最新进度 ==="
tail -1 /root/autodl-tmp/train.log | head -c 120
echo ""
echo "=== TRAIN_DONE 标记 ==="
grep -c TRAIN_DONE /root/autodl-tmp/train.log
echo "=== GPU ==="
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
