#!/usr/bin/env python3
"""
实际测试：使用 claude-cli 进行代码审查
"""

import sys
import os
sys.path.insert(0, '/root/.hermes/plugins/acp-client')

from tools import acp_dispatch

# 准备审查的代码
code_to_review = """
def calculate_sum(numbers):
    total = 0
    for num in numbers:
        total += num
    return total

def find_max(numbers):
    max_num = numbers[0]
    for num in numbers:
        if num > max_num:
            max_num = num
    return max_num
"""

print("="*60)
print("实际测试：Claude Code 代码审查")
print("="*60 + "\n")

print("待审查代码:")
print("-" * 60)
print(code_to_review)
print("-" * 60)
print()

# 调用 Claude 进行代码审查
print("调用 Claude Code 进行审查...\n")

try:
    result = acp_dispatch(
        task=f"""
请审查以下 Python 代码，提供：
1. 代码质量评价（1-10 分）
2. 发现的问题
3. 改进建议
4. 改进后的代码示例

代码：
```python
{code_to_review}
```

请用中文回答，简洁明了。
""",
        worker="claude-cli",  # 使用新的 adapter
        timeout=300,
        auto_fallback=True  # 失败时自动切换到 Gemini
    )
    
    print("\n" + "="*60)
    print("Claude Code 审查结果")
    print("="*60 + "\n")
    
    # 解析结果
    import json
    try:
        data = json.loads(result)
        
        if isinstance(data, dict):
            if "sessionId" in data:
                print(f"✅ sessionId: {data['sessionId']}")
                print(f"状态：{data.get('status', 'unknown')}")
                print(f"worker: {data.get('worker', 'unknown')}")
                
                # 等待并获取完整结果
                print("\n等待审查完成...")
                from acp.session_manager import get_session_manager
                import time
                
                session_id = data.get("sessionId")
                for i in range(30):
                    time.sleep(2)
                    sessions = get_session_manager()._sessions
                    if session_id in sessions:
                        session = sessions[session_id]
                        if session.status.value == "completed":
                            print(f"\n✅ 审查完成!\n")
                            print("="*60)
                            print(session.result)
                            print("="*60)
                            break
                        elif session.status.value == "failed":
                            print(f"\n❌ 审查失败：{session.error}")
                            break
                    print(f"  等待中... ({(i+1)*2}s)")
                else:
                    print("\n⏱️ 等待超时")
            else:
                print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(result)
            
    except json.JSONDecodeError:
        print(result)
    
except Exception as e:
    print(f"\n❌ 错误：{e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60 + "\n")
