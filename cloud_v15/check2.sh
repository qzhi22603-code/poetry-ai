#!/bin/bash
echo "=== train 进程 ==="
ps aux | grep "train_v15" | grep -v grep | awk '{print $2, $9, $10, $11, $12}'
echo "=== train.log 启动标记数 ==="
grep -c "样本数" /root/autodl-tmp/train.log
grep -c "trainable params" /root/autodl-tmp/train.log
echo "=== 日志头 5 行 ==="
head -5 /root/autodl-tmp/train.log
echo "=== 日志尾 3 行 ==="
tail -3 /root/autodl-tmp/train.log | head -c 300
echo ""
echo "=== 文件时间 ==="
ls -la /root/autodl-tmp/train.log
date
