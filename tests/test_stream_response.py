#!/usr/bin/env python3
"""
Qwen ACP 流式响应测试 - 捕获完整输出

监听 Qwen 的所有流式更新，获取完整响应
"""

import sys
import json
import time
import subprocess
import threading
import os
from datetime import datetime

OUTPUT_DIR = "/root/vibecoding/hermes-acp-client-plugin/tests/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 70)
print("Qwen ACP 流式响应测试")
print("=" * 70)

# 存储所有响应
all_responses = []
response_lock = threading.Lock()

def read_stdout(proc):
    """后台线程持续读取 stdout"""
    try:
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            try:
                data = json.loads(line)
                with response_lock:
                    all_responses.append({
                        "timestamp": time.time(),
                        "data": data
                    })
                # 打印通知
                method = data.get("method", "response")
                if method:
                    params = data.get("params", {})
                    update = params.get("update", {})
                    update_type = update.get("sessionUpdate", "unknown")
                    print(f"  [{method}] {update_type}")
            except json.JSONDecodeError:
                print(f"  [raw] {line[:100]}...")
    except Exception as e:
        print(f"读取错误：{e}")

# 启动进程
print("\n启动 Qwen ACP...")
proc = subprocess.Popen(
    ["qwen", "--acp"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)

# 启动读取线程
reader_thread = threading.Thread(target=read_stdout, args=(proc,), daemon=True)
reader_thread.start()

def send_request(req: dict):
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()

# 1. Initialize
print("\n1. Initialize...")
send_request({
    "jsonrpc": "2.0",
    "id": "init_1",
    "method": "initialize",
    "params": {
        "protocolVersion": 1,
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"}
    }
})
time.sleep(2)

# 2. Create Session
print("\n2. 创建会话...")
send_request({
    "jsonrpc": "2.0",
    "id": "session_1",
    "method": "session/new",
    "params": {
        "name": "stream_test",
        "cwd": OUTPUT_DIR,
        "mcpServers": []
    }
})
time.sleep(2)

# 获取 session_id
session_id = None
with response_lock:
    for r in all_responses:
        if r["data"].get("method") == "session/new" and "result" in r["data"]:
            session_id = r["data"]["result"].get("sessionId")
            break

if not session_id:
    # 从最后一个 session/new 响应获取
    for r in reversed(all_responses):
        if r["data"].get("id") == "session_1" and "result" in r["data"]:
            session_id = r["data"]["result"].get("sessionId")
            break

print(f"   会话 ID: {session_id}")

if not session_id:
    print("✗ 无法获取会话 ID")
    proc.terminate()
    sys.exit(1)

# 3. 发送提示
print("\n3. 发送代码生成任务...")
prompt = """
生成一个 Python Calculator 类，支持加减乘除和平方根。
包含类型注解和文档字符串。
直接输出代码。
"""

send_request({
    "jsonrpc": "2.0",
    "id": "prompt_1",
    "method": "session/prompt",
    "params": {
        "sessionId": session_id,
        "prompt": [{"type": "text", "text": prompt}]
    }
})

# 等待响应 (最多 60 秒)
print("   等待响应...")
start = time.time()
while time.time() - start < 60:
    time.sleep(1)
    # 检查是否有完成信号
    with response_lock:
        for r in all_responses:
            if r["data"].get("id") == "prompt_1" and "result" in r["data"]:
                print(f"   收到最终响应!")
                break
    
    # 检查是否有 session/update 表示完成
    with response_lock:
        latest = all_responses[-1] if all_responses else None
        if latest and latest["data"].get("result"):
            break

elapsed = time.time() - start
print(f"   总耗时：{elapsed:.2f}s")

# 4. 分析响应
print("\n4. 响应分析...")
print(f"   总响应数：{len(all_responses)}")

# 查找最终响应
final_response = None
with response_lock:
    for r in reversed(all_responses):
        if r["data"].get("id") == "prompt_1":
            if "result" in r["data"]:
                final_response = r["data"]
                break
            elif "error" in r["data"]:
                final_response = r["data"]
                break

if final_response:
    print(f"   最终响应：{json.dumps(final_response, indent=2)[:500]}")
else:
    print("   未找到最终响应")

# 5. 保存所有响应
output_file = os.path.join(OUTPUT_DIR, "stream_responses.json")
with response_lock:
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "session_id": session_id,
            "elapsed_seconds": round(elapsed, 2),
            "total_responses": len(all_responses),
            "final_response": final_response,
            "all_responses": all_responses,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2, default=str)

print(f"\n结果已保存：{output_file}")

# 清理
proc.terminate()
try:
    proc.wait(timeout=5)
except:
    proc.kill()

print("\n测试完成!")
