#!/usr/bin/env python3
"""
测试 Claude Code - 使用正确的环境变量
"""

import sys
import os
import json
import time

sys.path.insert(0, '/root/.hermes/plugins/acp-client')

# 设置 cc-acp 需要的环境变量
os.environ["CLAUDE_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "")
os.environ["CLAUDE_BASE_URL"] = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
os.environ["CLAUDE_MODEL"] = "claude-3-5-sonnet-20241022"  # 使用可用的模型

print("="*60)
print("环境变量配置")
print("="*60)
print(f"CLAUDE_API_KEY: {'✅ 已设置' if os.environ.get('CLAUDE_API_KEY') else '❌ 未设置'}")
print(f"CLAUDE_BASE_URL: {os.environ.get('CLAUDE_BASE_URL')}")
print(f"CLAUDE_MODEL: {os.environ.get('CLAUDE_MODEL')}")
print()

from acp.transport import initialize_transport, get_transport, shutdown_transport
from acp.session_manager import get_session_manager

# 通知回调
notifications = []
def on_notification(data):
    notifications.append(data)
    method = data.get('method')
    params = data.get('params', {})
    
    print(f"\n[通知] {method}")
    
    if 'update' in params:
        update = params['update']
        if isinstance(update, dict):
            content = update.get('content', {})
            text = content.get('text', '') if isinstance(content, dict) else str(content)
            if text:
                # 检查是否是错误
                if 'Error' in text or 'error' in text or '403' in text or '401' in text:
                    print(f"  ❌ {text[:200]}")
                else:
                    print(f"  ✅ {text[:200]}")

print("="*60)
print("测试 Claude Code ACP 调用")
print("="*60 + "\n")

# 1. 初始化
print("1. 初始化 transport...")
initialized = initialize_transport(
    worker="claude",
    request_timeout=120,
    on_notification=on_notification
)

print(f"初始化：{'✅ 成功' if initialized else '❌ 失败'}\n")

if not initialized:
    print("初始化失败，退出")
    sys.exit(1)

try:
    transport = get_transport("claude")
    
    # 2. 创建会话
    print("2. 创建会话...")
    session_resp = transport.create_session(name="final-test")
    
    session_id = None
    if session_resp and "result" in session_resp:
        session_id = session_resp["result"].get("sessionId")
    
    if not session_id:
        print(f"❌ 无法获取 sessionId")
        print(f"响应：{session_resp}")
        sys.exit(1)
    
    print(f"✅ sessionId: {session_id}\n")
    
    # 3. 发送提示
    print("3. 发送提示...")
    prompt = "Hello Claude! Please answer in one sentence: What is the capital of France?"
    print(f"提示：{prompt}\n")
    
    result = transport.send_prompt(session_id, prompt)
    
    print(f"\n等待 Claude 响应...")
    time.sleep(8)  # 等待更多时间让 Claude 响应
    
    # 4. 检查结果
    print(f"\n4. 检查结果...")
    print(f"收到 {len(notifications)} 个通知\n")
    
    # 分析通知
    has_success = False
    has_error = False
    
    for i, notif in enumerate(notifications):
        params = notif.get('params', {})
        if 'update' in params:
            update = params['update']
            if isinstance(update, dict) and 'content' in update:
                content = update.get('content', {})
                text = content.get('text', '') if isinstance(content, dict) else str(content)
                
                if text:
                    print(f"通知 {i+1}:")
                    print(f"  {text[:300]}")
                    print()
                    
                    # 检查是否成功
                    if 'Paris' in text or 'capital' in text.lower():
                        has_success = True
                    
                    # 检查是否错误
                    if any(x in text for x in ['Error', 'error', '403', '401', 'Invalid']):
                        has_error = True
    
    # 5. 总结
    print("="*60)
    print("测试结果")
    print("="*60 + "\n")
    
    if has_success and not has_error:
        print("✅ Claude Code 调用成功!")
        print("\nACP 插件完全正常工作，可以调用 Claude Code！")
    elif has_error:
        print("❌ Claude Code 调用失败")
        print("\n原因：认证或 API 权限问题")
        print("\n建议:")
        print("1. 检查 API key 是否有效")
        print("2. 检查 base URL 是否正确")
        print("3. 检查模型名称是否正确")
    else:
        print("⚠️ 未收到有效响应")
        print("\n可能需要更长的等待时间或检查网络")
    
    print("\n" + "="*60 + "\n")

finally:
    shutdown_transport("claude")
    print("清理完成\n")
