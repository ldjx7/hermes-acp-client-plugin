#!/usr/bin/env python3
"""
调试测试：检查通知回调是否正确触发
"""

import sys
import os
import json
import time

sys.path.insert(0, '/root/.hermes/plugins/acp-client')

from acp.transport import initialize_transport, get_transport, shutdown_transport
from acp.session_manager import get_session_manager

# 通知记录
notifications_received = []

def on_notification(data):
    """通知回调"""
    notifications_received.append(data)
    print(f"\n[✅ 收到通知]")
    print(f"  method: {data.get('method')}")
    print(f"  params: {json.dumps(data.get('params', {}), indent=4, ensure_ascii=False)[:500]}")
    
    # 手动更新会话管理器
    from tools import handle_notification
    print(f"\n[调用 handle_notification...]")
    try:
        handle_notification(data)
        print(f"✅ handle_notification 执行成功")
    except Exception as e:
        print(f"❌ handle_notification 执行失败：{e}")
        import traceback
        traceback.print_exc()

print("="*60)
print("调试测试：通知回调")
print("="*60 + "\n")

# 初始化
print("1. 初始化 transport...")
initialized = initialize_transport(
    worker="claude-cli",
    request_timeout=60,
    on_notification=on_notification
)

print(f"初始化：{'✅' if initialized else '❌'}\n")

if not initialized:
    sys.exit(1)

try:
    transport = get_transport("claude-cli")
    
    # 创建会话
    print("2. 创建会话...")
    session_resp = transport.create_session(name="debug-test")
    
    session_id = None
    if session_resp and "result" in session_resp:
        session_id = session_resp["result"].get("sessionId")
    
    print(f"sessionId: {session_id}\n")
    
    if not session_id:
        print("❌ sessionId 提取失败")
        print(f"响应：{session_resp}")
        sys.exit(1)
    
    # 发送简单提示
    print("3. 发送简单提示...")
    prompt = "Hi! Reply with just 'OK'."
    
    result = transport.send_prompt(session_id, prompt)
    
    print(f"\n等待响应 (30 秒)...\n")
    
    # 等待
    for i in range(15):
        time.sleep(2)
        
        # 检查会话管理器
        sessions = get_session_manager()._sessions
        if sessions:
            print(f"\n✅ 会话管理器中有 {len(sessions)} 个会话!")
            for sid, session in sessions.items():
                print(f"\n会话：{sid}")
                print(f"  状态：{session.status.value}")
                print(f"  结果：{session.result[:200] if session.result else 'None'}...")
            break
        
        print(f"  等待中... ({(i+1)*2}s)", end='\r')
    
    # 总结
    print(f"\n\n收到 {len(notifications_received)} 个通知\n")
    
    if len(notifications_received) == 0:
        print("❌ 没有收到任何通知")
        print("\n可能的问题:")
        print("1. claude-cli-acp 没有发送通知")
        print("2. 通知格式不正确")
        print("3. 回调没有正确注册")
    else:
        print("✅ 收到通知!")
        for i, notif in enumerate(notifications_received):
            print(f"\n通知 {i+1}:")
            print(f"  method: {notif.get('method')}")
            params = notif.get('params', {})
            if 'state' in params:
                print(f"  state: {params['state']}")
    
finally:
    shutdown_transport("claude-cli")
    print("\n\n清理完成")
