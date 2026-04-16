#!/usr/bin/env python3
"""
最终测试：使用 acp_dispatch 调用 claude-cli
"""

import sys
import os
import json
import time

sys.path.insert(0, '/root/.hermes/plugins/acp-client')

# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

from tools import acp_dispatch
from acp.session_manager import get_session_manager

print("="*60)
print("最终测试：acp_dispatch 调用 claude-cli")
print("="*60 + "\n")

# 简单测试
task = "请用一句话回答：2+2 等于几？"
print(f"任务：{task}\n")

print("调用 acp_dispatch...")
result = acp_dispatch(
    task=task,
    worker="claude-cli",
    timeout=60,
    auto_fallback=False
)

print(f"\n派发结果：{result[:500]}\n")

# 解析结果
try:
    data = json.loads(result)
    session_id = data.get("sessionId")
    
    if session_id:
        print(f"✅ sessionId: {session_id}\n")
        
        # 等待完成
        print("等待任务完成...\n")
        
        for i in range(30):
            time.sleep(2)
            
            # 检查会话管理器
            sessions = get_session_manager()._sessions
            
            if session_id in sessions:
                session = sessions[session_id]
                print(f"[{i*2+2}s] 状态：{session.status.value}")
                
                if session.status.value == "completed":
                    print(f"\n✅ 任务完成!")
                    print(f"\n结果:\n{session.result[:500]}")
                    break
                elif session.status.value == "failed":
                    print(f"\n❌ 任务失败：{session.error}")
                    break
            else:
                # 显示所有会话
                if sessions:
                    print(f"[{i*2+2}s] 会话管理器中有 {len(sessions)} 个会话，但不包含 {session_id[:20]}...")
                    for sid in sessions.keys():
                        print(f"  - {sid[:30]}...")
                else:
                    print(f"[{i*2+2}s] 会话管理器为空")
        else:
            print(f"\n⏱️  等待超时")
            
            # 显示最终状态
            sessions = get_session_manager()._sessions
            print(f"\n最终会话管理器状态：{len(sessions)} 个会话")
            for sid, session in sessions.items():
                print(f"  {sid[:30]}...: {session.status.value}")
    else:
        print(f"❌ 没有 sessionId")
        print(f"结果：{data}")
        
except json.JSONDecodeError as e:
    print(f"❌ JSON 解析失败：{e}")
    print(f"原始结果：{result}")

print("\n" + "="*60 + "\n")
