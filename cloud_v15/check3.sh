#!/bin/bash
echo "=== 最新进度 ==="
tail -c 200 /root/autodl-tmp/train.log
echo ""
echo "=== loss 尾迹 ==="
grep -o "loss: [0-9.]*" /root/autodl-tmp/train.log | tail -4
echo "=== TRAIN_DONE ==="
grep -c TRAIN_DONE /root/autodl-tmp/train.log
