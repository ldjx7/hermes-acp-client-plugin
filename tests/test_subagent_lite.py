#!/usr/bin/env python3
"""
Qwen ACP Subagent 精简测试

快速验证 subagent 模式的核心功能
"""

import sys
import json
import time
import os

sys.path.insert(0, '/root/vibecoding/hermes-acp-client-plugin')

from acp.transport import StdioTransport
from acp.protocol import InitializeRequest, NewSessionRequest, PromptRequest

OUTPUT_DIR = "/root/vibecoding/hermes-acp-client-plugin/tests/output/subagent_lite"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("="*70)
print("Qwen ACP Subagent 精简测试")
print("="*70)


def run_subagent_task(agent_id: str, prompt: str, timeout: float = 90.0) -> dict:
    """运行单个 subagent 任务"""
    print(f"\n[{agent_id}] 开始任务...")
    
    transport = None
    start = time.time()
    
    try:
        # 启动
        transport = StdioTransport(worker='qwen', request_timeout=timeout)
        if not transport.start():
            return {"error": "启动失败"}
        time.sleep(1)
        
        # Initialize
        resp = transport.send(InitializeRequest(), timeout=timeout)
        if not resp or "result" not in resp:
            return {"error": "Initialize 失败"}
        
        # Create Session
        session_req = NewSessionRequest.create(cwd=OUTPUT_DIR, mcp_servers=[])
        session_resp = transport.send(session_req, timeout=timeout)
        if not session_resp or "result" not in session_resp:
            return {"error": "创建会话失败"}
        
        session_id = session_resp["result"]["sessionId"]
        print(f"[{agent_id}] 会话：{session_id}")
        
        # Send Prompt
        print(f"[{agent_id}] 发送任务... ({len(prompt)} 字符)")
        prompt_req = PromptRequest.create(session_id=session_id, prompt=prompt)
        resp = transport.send(prompt_req, timeout=timeout)
        
        elapsed = time.time() - start
        
        result = {
            "agent_id": agent_id,
            "session_id": session_id,
            "elapsed": round(elapsed, 2),
            "success": "result" in (resp or {}),
            "response": resp
        }
        
        if result["success"]:
            print(f"[{agent_id}] ✓ 完成 ({elapsed:.2f}s)")
        else:
            print(f"[{agent_id}] ✗ 失败：{resp}")
        
        # 保存日志
        log_file = os.path.join(OUTPUT_DIR, f"{agent_id}.json")
        with open(log_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        
        return result
        
    finally:
        if transport:
            transport.stop()


# ============== 测试 1: 代码生成 ==============
print("\n" + "="*70)
print("测试 1: 代码生成")
print("="*70)

result1 = run_subagent_task(
    "code_generator",
    """生成一个 Python 函数 fibonacci(n)，返回第 n 个斐波那契数。
要求：
- 类型注解
- 文档字符串
- 使用缓存优化性能
- 包含单元测试

直接输出代码。"""
)


# ============== 测试 2: 代码审查 ==============
print("\n" + "="*70)
print("测试 2: 代码审查")
print("="*70)

result2 = run_subagent_task(
    "code_reviewer",
    """审查以下代码的问题：

```python
def get_user(user_id):
    sql = "SELECT * FROM users WHERE id=" + user_id
    return db.query(sql)

def process(data):
    result = []
    for i in range(len(data)):
        if data[i] > 0:
            result.append(data[i] * 2)
    return result
```

指出安全问题和改进建议。"""
)


# ============== 测试 3: 多轮对话 ==============
print("\n" + "="*70)
print("测试 3: 多轮对话")
print("="*70)

transport = None
try:
    transport = StdioTransport(worker='qwen', request_timeout=90.0)
    transport.start()
    time.sleep(1)
    transport.send(InitializeRequest())
    
    session_resp = transport.send(NewSessionRequest.create(cwd=OUTPUT_DIR))
    session_id = session_resp["result"]["sessionId"]
    print(f"多轮对话会话：{session_id}")
    
    # 第 1 轮
    print("\n--- 第 1 轮：创建类 ---")
    resp1 = transport.send(PromptRequest.create(
        session_id=session_id,
        prompt="创建一个 Python 类 Logger，支持日志记录到文件和控制台。"
    ))
    print(f"响应：{'✓' if 'result' in (resp1 or {}) else '✗'}")
    
    time.sleep(1)
    
    # 第 2 轮
    print("\n--- 第 2 轮：添加功能 ---")
    resp2 = transport.send(PromptRequest.create(
        session_id=session_id,
        prompt="添加日志级别功能 (DEBUG, INFO, WARNING, ERROR)。"
    ))
    print(f"响应：{'✓' if 'result' in (resp2 or {}) else '✗'}")
    
    time.sleep(1)
    
    # 第 3 轮
    print("\n--- 第 3 轮：添加格式化 ---")
    resp3 = transport.send(PromptRequest.create(
        session_id=session_id,
        prompt="添加自定义日志格式，包含时间戳和日志级别。"
    ))
    print(f"响应：{'✓' if 'result' in (resp3 or {}) else '✗'}")
    
    result3 = {
        "agent_id": "multi_turn",
        "session_id": session_id,
        "rounds": 3,
        "success": all('result' in (r or {}) for r in [resp1, resp2, resp3])
    }
    
    # 保存
    log_file = os.path.join(OUTPUT_DIR, "multi_turn.json")
    with open(log_file, 'w') as f:
        json.dump(result3, f, indent=2, default=str)
    
except Exception as e:
    print(f"多轮对话失败：{e}")
    result3 = {"agent_id": "multi_turn", "success": False, "error": str(e)}
finally:
    if transport:
        transport.stop()


# ============== 汇总 ==============
print("\n" + "="*70)
print("测试结果汇总")
print("="*70)

results = {
    "代码生成": result1,
    "代码审查": result2,
    "多轮对话": result3
}

for name, result in results.items():
    status = "✓" if result.get("success") else "✗"
    elapsed = result.get("elapsed", "N/A")
    print(f"{status} {name}: {elapsed}s" if elapsed != "N/A" else f"{status} {name}")

success_count = sum(1 for r in results.values() if r.get("success"))
print(f"\n总计：{success_count}/{len(results)} 成功")

# 保存汇总
summary = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "tests": {
        name: "passed" if r.get("success") else "failed"
        for name, r in results.items()
    },
    "passed": success_count,
    "total": len(results)
}

with open(os.path.join(OUTPUT_DIR, "summary.json"), 'w') as f:
    json.dump(summary, f, indent=2)

print(f"\n结果已保存：{OUTPUT_DIR}")
print("="*70)
