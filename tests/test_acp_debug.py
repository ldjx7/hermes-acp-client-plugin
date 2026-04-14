#!/usr/bin/env python3
"""
Qwen ACP 错误捕获和诊断工具

实时显示所有 ACP 输出（包括错误、通知、响应）
"""

import sys
import json
import time
import subprocess
import threading
import os

sys.path.insert(0, '/root/vibecoding/hermes-acp-client-plugin')

OUTPUT_DIR = "/root/vibecoding/hermes-acp-client-plugin/tests/output/debug"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 存储所有消息
all_messages = []
message_lock = threading.Lock()


def save_messages():
    """保存所有消息到文件"""
    with message_lock:
        with open(os.path.join(OUTPUT_DIR, "all_messages.json"), 'w') as f:
            json.dump(all_messages, f, indent=2, default=str)


def monitor_stdout(proc):
    """监控 stdout"""
    print("\n[监控] 开始读取 stdout...")
    try:
        while True:
            line = proc.stdout.readline()
            if not line:
                print("[监控] stdout 关闭")
                break
            
            try:
                data = json.loads(line)
                msg_type = "响应" if "id" in data and "result" in data else \
                          "错误" if "error" in data else \
                          "通知" if "method" in data else "未知"
                
                with message_lock:
                    all_messages.append({
                        "timestamp": time.time(),
                        "direction": "stdout",
                        "type": msg_type,
                        "data": data
                    })
                
                # 显示关键信息
                if "error" in data:
                    print(f"\n❌ 错误：{json.dumps(data['error'], indent=2)}")
                elif "method" in data:
                    method = data["method"]
                    params = data.get("params", {})
                    update = params.get("update", {})
                    update_type = update.get("sessionUpdate", "unknown")
                    print(f"\n📢 通知：{method} - {update_type}")
                    
                    # 显示 content
                    content = update.get("content", {})
                    if isinstance(content, dict) and "text" in content:
                        text = content["text"]
                        if len(text) > 100:
                            text = text[:100] + "..."
                        print(f"   内容：{text}")
                        
                elif "result" in data:
                    print(f"\n✅ 响应：{data.get('id', 'unknown')} - {data['result']}")
                    
            except json.JSONDecodeError:
                print(f"[原始] {line[:200]}")
                
    except Exception as e:
        print(f"[监控] 异常：{e}")


def monitor_stderr(proc):
    """监控 stderr"""
    print("[监控] 开始读取 stderr...")
    try:
        for line in proc.stderr:
            if line.strip():
                with message_lock:
                    all_messages.append({
                        "timestamp": time.time(),
                        "direction": "stderr",
                        "type": "stderr",
                        "content": line.strip()
                    })
                print(f"\n⚠️  STDERR: {line.strip()}")
    except Exception as e:
        print(f"[监控] stderr 异常：{e}")


print("="*70)
print("Qwen ACP 错误捕获和诊断")
print("="*70)

# 启动进程
print("\n启动 Qwen ACP 进程...")
proc = subprocess.Popen(
    ["qwen", "--acp"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)
print(f"PID: {proc.pid}")

# 启动监控线程
stdout_thread = threading.Thread(target=monitor_stdout, args=(proc,), daemon=True)
stderr_thread = threading.Thread(target=monitor_stderr, args=(proc,), daemon=True)

stdout_thread.start()
stderr_thread.start()

time.sleep(2)


def send_request(req: dict):
    """发送请求"""
    print(f"\n➡️  发送：{req.get('method', 'unknown')} (ID: {req.get('id', 'unknown')})")
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()


# 1. Initialize
print("\n" + "="*50)
print("步骤 1: Initialize")
print("="*50)
send_request({
    "jsonrpc": "2.0",
    "id": "init_1",
    "method": "initialize",
    "params": {
        "protocolVersion": 1,
        "capabilities": {},
        "clientInfo": {"name": "debug", "version": "1.0"}
    }
})
time.sleep(3)


# 2. Create Session
print("\n" + "="*50)
print("步骤 2: Create Session")
print("="*50)
send_request({
    "jsonrpc": "2.0",
    "id": "session_1",
    "method": "session/new",
    "params": {
        "name": "debug_test",
        "cwd": OUTPUT_DIR,
        "mcpServers": []
    }
})
time.sleep(3)


# 获取 session_id
session_id = None
with message_lock:
    for msg in all_messages:
        if msg["data"].get("id") == "session_1" and "result" in msg["data"]:
            session_id = msg["data"]["result"].get("sessionId")
            break

if not session_id:
    print("❌ 无法获取会话 ID")
    proc.terminate()
    sys.exit(1)

print(f"\n会话 ID: {session_id}")


# 3. 发送简单任务
print("\n" + "="*50)
print("步骤 3: 发送简单任务")
print("="*50)
send_request({
    "jsonrpc": "2.0",
    "id": "prompt_1",
    "method": "session/prompt",
    "params": {
        "sessionId": session_id,
        "prompt": [{"type": "text", "text": "说你好"}]
    }
})


# 等待响应
print("\n等待响应... (最多 30 秒)")
start = time.time()
while time.time() - start < 30:
    time.sleep(1)
    
    # 检查是否有最终响应
    with message_lock:
        for msg in reversed(all_messages):
            if msg["data"].get("id") == "prompt_1":
                if "result" in msg["data"] or "error" in msg["data"]:
                    print(f"\n收到最终响应!")
                    break
    
    # 检查超时
    if time.time() - start > 30:
        print("⏱️  超时")
        break


# 4. 发送错误触发任务
print("\n" + "="*50)
print("步骤 4: 发送可能出错的任务")
print("="*50)
send_request({
    "jsonrpc": "2.0",
    "id": "prompt_2",
    "method": "session/prompt",
    "params": {
        "sessionId": session_id,
        "prompt": "invalid format test"  # 测试错误处理
    }
})

time.sleep(5)


# 5. 汇总
print("\n" + "="*70)
print("消息汇总")
print("="*70)

with message_lock:
    errors = [m for m in all_messages if m["type"] == "错误" or "error" in m.get("data", {})]
    notifications = [m for m in all_messages if m["data"].get("method")]
    responses = [m for m in all_messages if "result" in m.get("data", {})]
    
    print(f"总消息数：{len(all_messages)}")
    print(f"错误数：{len(errors)}")
    print(f"通知数：{len(notifications)}")
    print(f"响应数：{len(responses)}")
    
    if errors:
        print(f"\n错误详情:")
        for err in errors:
            print(f"  - {err['data'].get('error', 'Unknown')}")


# 保存
save_messages()
print(f"\n完整日志已保存：{OUTPUT_DIR}/all_messages.json")


# 清理
proc.terminate()
try:
    proc.wait(timeout=5)
except:
    proc.kill()

print("\n诊断完成!")
