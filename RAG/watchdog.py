# -*- coding: utf-8 -*-
"""poemly RAG 代理看门狗：
   - 每 30 秒探测 11499 端口，代理掉线自动拉起
   - 通过 11498 端口锁保证自身单实例
   - 由 pythonw 启动（无窗口），独立于任何终端/IDE 的进程树
"""
import socket, subprocess, sys, time, os

RAG = r"C:\Users\38107\Desktop\ai\RAG"
PROXY = os.path.join(RAG, "rag_proxy.py")
LOG = os.path.join(RAG, "watchdog.log")
PORT = 11499
LOCK = 11498


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg + "\n")
    except Exception:
        pass


def alive(port):
    s = socket.socket()
    s.settimeout(2)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except Exception:
        return False
    finally:
        s.close()


# 单实例锁：占住 11498，占不住说明已有看门狗
lock_sock = socket.socket()
try:
    lock_sock.bind(("127.0.0.1", LOCK))
    lock_sock.listen(1)
except OSError:
    log("已有看门狗在运行，本实例退出")
    sys.exit(0)

log("watchdog 启动 (pid=%d)" % os.getpid())
while True:
    try:
        if not alive(PORT):
            log("端口无响应，拉起代理")
            subprocess.Popen(
                [sys.executable, PROXY],
                cwd=RAG,
                stdout=open(os.path.join(RAG, "proxy_stdout.log"), "ab"),
                stderr=subprocess.STDOUT,
                creationflags=0x00000008,  # DETACHED_PROCESS
            )
            time.sleep(12)
            log("重启后状态: " + ("OK" if alive(PORT) else "仍失败"))
    except Exception as e:
        log("err: " + str(e))
    time.sleep(30)
