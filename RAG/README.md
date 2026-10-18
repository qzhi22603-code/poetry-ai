# poemly RAG 知识库系统（v3：自动注入架构）

给 poemly 用的本地检索增强。**核心是 `rag_proxy.py` 自动 RAG 代理**：ZCode 的 ollama 供应商 baseUrl 指向 `http://127.0.0.1:11499`，代理拦截对话请求，自动检索知识库 top-3 并作为【知识库检索结果】注入 system，再转发给 Ollama（11434）。模型无需调用工具，检索确定性发生。

- 启动：开机自启（启动文件夹 `poemly-rag-proxy.vbs`，pythonw 静默）；手动：`python rag_proxy.py`；日志 `proxy.log`
- 依赖 Ollama 运行（poemly 生成 + bge-m3 嵌入都靠它）
- MCP 服务 poemly-kb 保留在用户作用域，仅作手动调试用

## 组成

- `知识库\*.txt` —— 15 份语料共 **80,530 条**：全唐诗 56,970、全宋词 21,050、诗经 305、楚辞 216、唐诗三百首 320、千家诗 219、宋词三百首 309、声律启蒙 90、笠翁对韵 30、幼学琼林 191、平水韵字表 106（繁体）、词林正韵字表 115（繁体）、人间词话 190、沧浪诗话 122、龙文鞭影 297。条与条之间空行分隔。
- `rag_server.py` —— MCP 检索服务器 v2：numpy 矢量检索 + 关键词二元组混合评分（0.8 向量 + 0.2 关键词），单查 <1 秒。
- `chunks.json` + `vectors.f32` —— 索引（232MB，bge-m3 已归一化），build_index.py 生成。
- `build_index.py` —— 重建索引（自适应分批防 413，重试防瞬时 400）：`python build_index.py`，约 16 分钟，完成后新开对话生效。
- `convert_corpus.py` / `convert_corpus2.py` / `fetch_liweng.py` / `fetch_wikisource.py` + 各 json/pkl/tang —— 语料原始来源与转换脚本。
- `test_mcp.py` —— 端到端自测。

## 依赖

- Ollama 运行中，装有 `bge-m3`（嵌入）与 `poemly`（对话，qwen2.5:3b 基座）
- Python 3.13：`mcp<2`（**必须 1.x**，2.x 改名会崩）、`numpy`、`opencc`（C++ 版）

## 常见问题

- mcp 被升级到 2.x → `pip install "mcp<2"` 恢复
- 加语料：txt 放入 知识库 → `python build_index.py` → 新开对话
- 维基文库抓取须走代理且 UA 带浏览器串；zh-hans raw 会返回 REDIRECT 占位，要用繁体正题
