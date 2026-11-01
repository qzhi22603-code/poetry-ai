【v1.5 云训包使用说明】（配套《02-基座升级操作步骤.md》）

包内文件：
  train_v15.py        训练脚本（Qwen2.5-7B + poemly_sft_v15，4090 调优）
  merge_v15.py        LoRA 合并脚本
  run_v15_train.sh    第一步一键脚本：装依赖 + 下基座 + 开训
  run_v15_export.sh   第二步一键脚本：合并 + 转 GGUF + Q6_K 量化
  poemly_sft_v15.json 训练数据（2043 条）

流程（AutoDL 的 JupyterLab 终端里操作）：
  1. 把整个 cloud_v15.zip 拖进左侧文件面板（落在 /root/autodl-tmp），
     终端执行：  cd /root/autodl-tmp && python -m zipfile -e cloud_v15.zip .
  2. 开训：      bash /root/autodl-tmp/run_v15_train.sh
     （下载基座约 15GB + 训练约 40-80 分钟；看到 TRAIN_DONE 即成功）
  3. 导出：      bash /root/autodl-tmp/run_v15_export.sh
     （看到 ALL_DONE 即成功，产物 poemly-v15-Q6_K.gguf 约 6.3GB）
  4. 下载：JupyterLab 左侧文件面板右键 poemly-v15-Q6_K.gguf → Download
     （或用 AutoDL 网盘中转）
  5. 下载完立即去控制台「关机」停止计费！量化包已到手，实例可释放。

注意事项：
  - 训练中每隔几分钟会打印 loss，正常应从 ~2 一路降到 1 上下；
  - 若 git clone llama.cpp 超时，换：git clone --depth 1 https://ghproxy.net/https://github.com/ggerganov/llama.cpp
  - 任何一步报错，把终端报错整段复制给 agent。
