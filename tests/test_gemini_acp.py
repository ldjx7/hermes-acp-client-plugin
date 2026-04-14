#!/usr/bin/env python3
"""
Gemini CLI ACP 模式测试

测试 Gemini 的 ACP 协议兼容性和性能
"""

import sys
import json
import time
import os
from datetime import datetime

sys.path.insert(0, '/root/vibecoding/hermes-acp-client-plugin')

from acp.transport import StdioTransport
from acp.protocol import InitializeRequest, NewSessionRequest, PromptRequest

OUTPUT_DIR = "/root/vibecoding/hermes-acp-client-plugin/tests/output/gemini_test"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("="*70)
print("Gemini CLI ACP 模式测试")
print("="*70)


def run_test(test_name: str, prompt: str, timeout: float = 90.0) -> dict:
    """运行单个测试"""
    print(f"\n{'='*70}")
    print(f"测试：{test_name}")
    print(f"{'='*70}")
    
    transport = None
    start = time.time()
    
    try:
        # 启动
        print("启动 Gemini ACP...")
        transport = StdioTransport(worker='gemini', request_timeout=timeout)
        
        if not transport.start():
            return {"error": "启动失败", "test": test_name}
        
        time.sleep(2)
        
        # Initialize
        print("Initialize...")
        init_resp = transport.send(InitializeRequest(), timeout=timeout)
        
        if not init_resp:
            return {"error": "Initialize 无响应", "test": test_name}
        
        if "result" in init_resp:
            agent_info = init_resp["result"].get("agentInfo", {})
            print(f"✓ Agent: {agent_info.get('name', 'Unknown')} v{agent_info.get('version', '?')}")
        elif "error" in init_resp:
            return {"error": init_resp["error"], "test": test_name}
        
        # Create Session
        print("创建会话...")
        session_req = NewSessionRequest.create(
            name=f"gemini_test_{int(time.time())}",
            cwd=OUTPUT_DIR,
            mcp_servers=[]
        )
        session_resp = transport.send(session_req, timeout=timeout)
        
        if not session_resp or "result" not in session_resp:
            return {"error": "创建会话失败", "response": session_resp, "test": test_name}
        
        session_id = session_resp["result"]["sessionId"]
        print(f"✓ 会话 ID: {session_id}")
        
        # Send Prompt
        print(f"发送任务... ({len(prompt)} 字符)")
        prompt_req = PromptRequest.create(session_id=session_id, prompt=prompt)
        
        print(f"等待响应... (超时：{timeout}s)")
        resp = transport.send(prompt_req, timeout=timeout)
        
        elapsed = time.time() - start
        
        result = {
            "test": test_name,
            "session_id": session_id,
            "elapsed": round(elapsed, 2),
            "success": "result" in (resp or {}),
            "response": resp,
            "timestamp": datetime.now().isoformat()
        }
        
        if result["success"]:
            print(f"✓ 完成 (耗时：{elapsed:.2f}s)")
            print(f"  停止原因：{resp['result'].get('stopReason', 'unknown')}")
        else:
            print(f"✗ 失败：{resp}")
        
        # 保存结果
        output_file = os.path.join(OUTPUT_DIR, f"{test_name.replace('/', '_')}.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"结果已保存：{output_file}")
        
        return result
        
    except Exception as e:
        print(f"✗ 异常：{e}")
        return {"error": str(e), "test": test_name, "elapsed": time.time() - start}
    finally:
        if transport:
            transport.stop()


# ============== 测试 1: 代码生成 ==============
result1 = run_test(
    "代码生成-email_validator",
    """生成一个 Python 函数 validate_email(email)，验证邮箱地址格式。
要求：
- 类型注解
- 文档字符串
- 使用正则表达式验证
- 包含单元测试示例

直接输出代码。""",
    timeout=120.0
)


# ============== 测试 2: 代码审查 ==============
result2 = run_test(
    "代码审查-security",
    """审查以下代码的安全问题：

```python
def get_user(user_id):
    sql = f"SELECT * FROM users WHERE id={user_id}"
    return db.query(sql)

def process(data):
    result = []
    for i in range(len(data)):
        if data[i] > 0:
            result.append(data[i] * 2)
    return result
```

指出安全漏洞和改进建议。用中文回复。""",
    timeout=90.0
)


# ============== 测试 3: 算法实现 ==============
result3 = run_test(
    "算法实现-binary_search",
    """实现二分查找算法 binary_search(arr, target)。
要求：
- 类型注解
- 文档字符串
- 时间复杂度分析
- 包含测试用例

直接输出代码。""",
    timeout=90.0
)


# ============== 测试 4: 简单对话 ==============
result4 = run_test(
    "简单对话-hello",
    "你好，请用中文自我介绍。",
    timeout=60.0
)


# ============== 测试 5: 文件操作 ==============
result5 = run_test(
    "文件操作-read_file",
    """生成一个 Python 函数 read_file_safely(filepath)，安全地读取文件内容。
要求：
- 类型注解
- 文档字符串
- 异常处理（文件不存在、权限错误等）
- 使用上下文管理器

直接输出代码。""",
    timeout=90.0
)


# ============== 汇总 ==============
print("\n" + "="*70)
print("测试结果汇总")
print("="*70)

results = {
    "代码生成-email_validator": result1,
    "代码审查-security": result2,
    "算法实现-binary_search": result3,
    "简单对话-hello": result4,
    "文件操作-read_file": result5,
}

success_count = 0
total_time = 0

for name, result in results.items():
    if result.get("success"):
        success_count += 1
        total_time += result.get("elapsed", 0)
        status = "✓"
    else:
        status = "✗"
    
    elapsed = result.get("elapsed", 0)
    error = result.get("error")
    print(f"{status} {name}: {elapsed:.2f}s" + (f" - {error}" if error else ""))

print(f"\n总计：{success_count}/{len(results)} 成功")
print(f"总耗时：{total_time:.2f}s")
print(f"平均耗时：{total_time/success_count:.2f}s" if success_count > 0 else "N/A")

# 保存汇总
summary = {
    "timestamp": datetime.now().isoformat(),
    "worker": "gemini",
    "total_tests": len(results),
    "successful": success_count,
    "failed": len(results) - success_count,
    "total_time_seconds": round(total_time, 2),
    "average_time_seconds": round(total_time / success_count, 2) if success_count > 0 else 0,
    "tests": [
        {
            "name": name,
            "success": result.get("success", False),
            "elapsed": result.get("elapsed", 0),
            "error": result.get("error")
        }
        for name, result in results.items()
    ]
}

summary_file = os.path.join(OUTPUT_DIR, "summary.json")
with open(summary_file, 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"\n汇总已保存：{summary_file}")
print("="*70)
print("Gemini ACP 测试完成!")
print("="*70)
