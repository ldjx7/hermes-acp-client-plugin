#!/usr/bin/env python3
"""
复杂任务测试：让 Claude Code 实现 Dijkstra 最短路径算法
"""

import sys
import os
import json
import time

sys.path.insert(0, '/root/.hermes/plugins/acp-client')

from tools import acp_dispatch
from acp.session_manager import get_session_manager

print("="*60)
print("复杂任务测试：Claude Code 实现 Dijkstra 算法")
print("="*60 + "\n")

# 任务描述
task = """
请用 Python 实现 Dijkstra 最短路径算法。

要求：
1. 实现完整的 Dijkstra 算法
2. 使用优先队列（heapq）优化
3. 包含详细的中文注释
4. 提供使用示例
5. 添加单元测试验证正确性
6. 时间复杂度分析

请输出完整的、可运行的代码。
"""

print("任务描述:")
print("-" * 60)
print(task)
print("-" * 60)
print()

# 调用 Claude Code
print("调用 Claude Code (claude-cli)...\n")

start_time = time.time()

result = acp_dispatch(
    task=task,
    worker="claude-cli",
    timeout=600,  # 10 分钟超时
    auto_fallback=False
)

print(f"\n派发结果：{result[:500]}\n")

# 解析结果
try:
    data = json.loads(result)
    session_id = data.get("sessionId")
    
    if not session_id:
        print(f"❌ 没有 sessionId")
        print(f"结果：{data}")
        sys.exit(1)
    
    print(f"✅ sessionId: {session_id}\n")
    print("等待 Claude Code 完成算法实现...\n")
    print("="*60 + "\n")
    
    # 等待完成
    elapsed = 0
    while elapsed < 300:  # 最多等待 5 分钟
        time.sleep(5)
        elapsed = time.time() - start_time
        
        sessions = get_session_manager()._sessions
        
        if session_id in sessions:
            session = sessions[session_id]
            status = session.status.value
            
            print(f"[{elapsed:.0f}s] 状态：{status}", end="")
            if session.progress_message:
                print(f" - {session.progress_message[:50]}", end="")
            print()
            
            if status == "completed":
                print(f"\n{'='*60}")
                print("✅ 任务完成!")
                print(f"{'='*60}\n")
                
                result_text = session.result
                if result_text:
                    print("📝 Claude Code 的实现:\n")
                    print("-" * 60)
                    
                    # 显示前 3000 字符
                    if len(result_text) > 3000:
                        print(result_text[:3000])
                        print(f"\n... [内容过长，已显示前 3000 字符，共 {len(result_text)} 字符]")
                    else:
                        print(result_text)
                    
                    print("-" * 60)
                    
                    # 验证是否包含关键内容
                    checks = [
                        ("import heapq", "优先队列"),
                        ("def dijkstra", "dijkstra 函数"),
                        ("def test", "单元测试"),
                        ("时间复杂度", "复杂度分析"),
                        ("注释", "中文注释")
                    ]
                    
                    print("\n✅ 验证结果:")
                    for keyword, description in checks:
                        if keyword in result_text or description in result_text:
                            print(f"  ✅ {description}")
                        else:
                            print(f"  ⚠️  {description} (未找到)")
                    
                    print(f"\n⏱️  总耗时：{elapsed:.1f}s")
                    print(f"📄 结果长度：{len(result_text)} 字符")
                    
                    # 保存到文件
                    output_file = "/tmp/dijkstra_implementation.py"
                    with open(output_file, "w") as f:
                        f.write(result_text)
                    print(f"💾 已保存到：{output_file}")
                    
                    sys.exit(0)
                    
            elif status == "failed":
                print(f"\n❌ 任务失败：{session.error}")
                sys.exit(1)
        else:
            print(f"[{elapsed:.0f}s] 等待会话创建...")
    
    print(f"\n⏱️  等待超时 ({elapsed:.0f}s)")
    
except json.JSONDecodeError as e:
    print(f"❌ JSON 解析失败：{e}")
    print(f"原始结果：{result}")

print("\n" + "="*60 + "\n")
