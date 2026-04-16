#!/usr/bin/env python3
"""
简单测试：Claude Code 实现快速排序
"""

import sys
import time
sys.path.insert(0, '/root/.hermes/plugins/acp-client')

from acp.transport import initialize_transport, get_transport, shutdown_transport
from acp.session_manager import get_session_manager
from tools import handle_notification

print("="*60)
print("测试：Claude Code 实现快速排序算法")
print("="*60 + "\n")

task = """请用 Python 实现快速排序算法。

要求：
1. 完整的快速排序实现
2. 中文注释
3. 使用示例
4. 时间复杂度分析

请输出完整代码。"""

print(f"任务：{task[:80]}...\n")

# 初始化
print("1. 初始化...")
initialized = initialize_transport(
    worker="claude-cli",
    request_timeout=300,
    on_notification=handle_notification
)
print(f"   {'✅' if initialized else '❌'}\n")

if not initialized:
    sys.exit(1)

try:
    transport = get_transport("claude-cli")
    
    # 创建会话
    print("2. 创建会话...")
    session_resp = transport.create_session(name="quicksort")
    session_id = session_resp.get("result", {}).get("sessionId")
    print(f"   sessionId: {session_id}\n")
    
    # 创建记录
    manager = get_session_manager()
    manager.create_session(prompt=task, session_id=session_id)
    print(f"   初始状态：{manager._sessions[session_id].status.value}\n")
    
    # 发送
    print("3. 发送请求...")
    start = time.time()
    result = transport.send_prompt(session_id, task)
    print(f"   已发送\n")
    
    # 等待
    print("4. 等待 Claude Code 实现...\n")
    for i in range(60):
        time.sleep(3)
        elapsed = time.time() - start
        
        session = manager._sessions.get(session_id)
        if session:
            status = session.status.value
            print(f"[{elapsed:.0f}s] {status}")
            
            if status == "completed":
                print(f"\n{'='*60}")
                print("✅ 任务完成!")
                print(f"{'='*60}\n")
                
                result_text = session.result
                if result_text:
                    print("📝 Claude Code 的实现:\n")
                    print("-" * 60)
                    print(result_text[:2500])
                    if len(result_text) > 2500:
                        print(f"\n... [共 {len(result_text)} 字符]")
                    print("-" * 60)
                    
                    # 验证
                    print("\n✅ 验证:")
                    checks = [
                        ("def quick", "quick 函数"),
                        ("时间复杂度", "复杂度分析"),
                        ("示例", "使用示例")
                    ]
                    for keyword, desc in checks:
                        if keyword.lower() in result_text.lower():
                            print(f"  ✅ {desc}")
                    
                    # 保存
                    with open("/tmp/quicksort.py", "w") as f:
                        f.write(result_text)
                    print(f"\n💾 已保存：/tmp/quicksort.py")
                    print(f"⏱️  总耗时：{elapsed:.1f}s")
                break
            elif status == "failed":
                print(f"\n❌ 失败：{session.error}")
                break
    
finally:
    shutdown_transport("claude-cli")
    print("\n清理完成")
