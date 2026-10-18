# -*- coding: utf-8 -*-
"""端到端测试：以 stdio 方式启动 rag_server，走 MCP 协议调用检索工具。"""
import subprocess, json, sys, time

PY = r"C:\Users\38107\AppData\Local\Programs\Python\Python313\python.exe"
p = subprocess.Popen([PY, r"C:\Users\38107\Desktop\ai\RAG\rag_server.py"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                     text=True, encoding="utf-8", bufsize=1)

def send(obj):
    p.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
    p.stdin.flush()

def recv(want_id):
    while True:
        line = p.stdout.readline()
        if not line:
            raise RuntimeError("server closed")
        msg = json.loads(line)
        if msg.get("id") == want_id:
            return msg

t0 = time.time()
send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
      "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                 "clientInfo": {"name": "test", "version": "0"}}})
r = recv(1)
print("initialize ok:", r["result"]["serverInfo"])
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
r = recv(2)
tools = [t["name"] for t in r["result"]["tools"]]
print("tools:", tools)

for q in ["庄生晓梦迷蝴蝶 典故出处", "平水韵 上平声一东 韵字", "写秋雨 约客 赵师秀"]:
    send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
          "params": {"name": "search_poetry_knowledge", "arguments": {"query": q, "top_k": 2}}})
    r = recv(3)
    text = r["result"]["content"][0]["text"]
    print(f"\n=== 查询: {q}  ({time.time()-t0:.1f}s)")
    print(text[:300].replace("\n", " | "))
p.kill()
print("\nALL TESTS DONE")
