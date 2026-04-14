#!/usr/bin/env python3
"""
Qwen ACP 代码生成测试 - 带输出捕获

通过持续对话获取 Qwen 生成的完整代码
"""

import sys
import json
import time
import subprocess
import os

sys.path.insert(0, '/root/vibecoding/hermes-acp-client-plugin')

from acp.transport import StdioTransport
from acp.protocol import InitializeRequest, NewSessionRequest, PromptRequest

OUTPUT_DIR = "/root/vibecoding/hermes-acp-client-plugin/tests/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 70)
print("Qwen ACP 代码生成测试 - 带输出捕获")
print("=" * 70)

# 启动 Qwen ACP 进程
print("\n启动 Qwen ACP 进程...")
proc = subprocess.Popen(
    ["qwen", "--acp"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)

def send_request(req: dict, timeout: float = 60.0):
    """发送请求并获取响应"""
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    
    start = time.time()
    while time.time() - start < timeout:
        line = proc.stdout.readline()
        if line:
            try:
                return json.loads(line)
            except:
                continue
    return None

# 1. Initialize
print("1. Initialize...")
init_req = {
    "jsonrpc": "2.0",
    "id": "init_1",
    "method": "initialize",
    "params": {
        "protocolVersion": 1,
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"}
    }
}
resp = send_request(init_req)
print(f"   Initialize: {json.dumps(resp.get('result', {}), indent=2)[:200]}")

# 2. Create Session
print("\n2. 创建会话...")
session_req = {
    "jsonrpc": "2.0",
    "id": "session_1",
    "method": "session/new",
    "params": {
        "name": "code_gen_test",
        "cwd": OUTPUT_DIR,
        "mcpServers": []
    }
}
resp = send_request(session_req)
session_id = resp.get("result", {}).get("sessionId")
print(f"   会话 ID: {session_id}")

# 3. 发送代码生成任务
print("\n3. 生成代码...")
prompt = """
生成一个 Python 类 Calculator，实现加减乘除和平方根运算。
包含类型注解和文档字符串。
直接输出代码，不要解释。
"""

prompt_req = {
    "jsonrpc": "2.0",
    "id": "prompt_1",
    "method": "session/prompt",
    "params": {
        "sessionId": session_id,
        "prompt": [{"type": "text", "text": prompt}]
    }
}

print("   发送请求，等待响应...")
start = time.time()
resp = send_request(prompt_req, timeout=120.0)
elapsed = time.time() - start

print(f"   耗时：{elapsed:.2f}s")
print(f"   响应：{json.dumps(resp, indent=2)[:500]}")

# 保存结果
result = {
    "session_id": session_id,
    "elapsed_seconds": round(elapsed, 2),
    "response": resp,
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
}

with open(os.path.join(OUTPUT_DIR, "calculator_gen.json"), 'w') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"\n结果已保存")

# 清理
proc.terminate()
proc.wait(timeout=5)

print("\n测试完成!")
