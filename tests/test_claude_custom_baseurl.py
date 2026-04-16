#!/usr/bin/env python3
"""
测试支持第三方代理的 Claude CLI ACP Adapter
"""

import sys
import os
import json
import time

sys.path.insert(0, '/root/.hermes/plugins/acp-client')

# 确保环境变量正确设置
print("="*60)
print("环境变量配置")
print("="*60)
print(f"ANTHROPIC_API_KEY: {'✅' if os.environ.get('ANTHROPIC_API_KEY') else '❌'}")
print(f"ANTHROPIC_BASE_URL: {os.environ.get('ANTHROPIC_BASE_URL', 'default')}")
print(f"ANTHROPIC_MODEL: {os.environ.get('ANTHROPIC_MODEL', 'default')}")
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
        if isinstance(update, dict) and 'content' in update:
            text = update.get('content', {}).get('text', '')
            if text:
                print(f"  {text[:200]}")
        elif 'status' in update:
            status = update.get('status')
            print(f"  状态：{status}")
            if status == 'completed':
                result = update.get('result', {})
                if isinstance(result, dict):
                    output = result.get('result', '')
                    if output:
                        print(f"  结果：{output[:200]}...")

print("="*60)
print("测试 claude-cli adapter (支持第三方代理)")
print("="*60 + "\n")

# 1. 初始化
print("1. 初始化 transport (worker: claude-cli)...")
initialized = initialize_transport(
    worker="claude-cli",
    request_timeout=120,
    on_notification=on_notification
)

print(f"初始化：{'✅ 成功' if initialized else '❌ 失败'}\n")

if not initialized:
    print("初始化失败，退出")
    sys.exit(1)

try:
    transport = get_transport("claude-cli")
    
    # 2. 创建会话
    print("2. 创建会话...")
    session_resp = transport.create_session(name="custom-base-url-test")
    
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
    prompt = "你好！请用一句话回答：巴黎是哪个国家的首都？"
    print(f"提示：{prompt}\n")
    
    result = transport.send_prompt(session_id, prompt)
    
    print(f"\n等待 Claude 响应 (最多 30 秒)...")
    
    # 4. 等待并检查通知
    start_time = time.time()
    timeout = 30
    
    while time.time() - start_time < timeout:
        time.sleep(2)
        
        # 检查是否有完成的通知
        for notif in notifications:
            params = notif.get('params', {})
            if 'update' in params:
                update = params['update']
                if isinstance(update, dict):
                    status = update.get('status')
                    if status == 'completed':
                        print(f"\n✅ 任务完成!")
                        
                        # 提取结果
                        result_data = update.get('result', {})
                        if isinstance(result_data, dict):
                            output = result_data.get('result', '')
                            if output:
                                print(f"\n📝 Claude 回复:")
                                print("-" * 60)
                                print(output)
                                print("-" * 60)
                                
                                # 验证是否包含正确答案
                                if '巴黎' in output or '法国' in output or 'Paris' in output or 'France' in output:
                                    print("\n✅ 回答正确!")
                                    print("\n🎉 claude-cli adapter 工作正常，支持第三方代理！")
                                    sys.exit(0)
                                else:
                                    print("\n⚠️  回答可能不正确")
                                    sys.exit(1)
                    
                    elif status == 'failed':
                        error = update.get('error', '')
                        print(f"\n❌ 任务失败：{error}")
                        sys.exit(1)
        
        elapsed = time.time() - start_time
        print(f"  等待中... ({elapsed:.1f}s)")
    
    print(f"\n⏱️  超时 ({timeout}s)")
    print(f"收到 {len(notifications)} 个通知")
    
    # 显示所有通知
    for i, notif in enumerate(notifications):
        print(f"\n通知 {i+1}: {json.dumps(notif, indent=2, ensure_ascii=False)[:500]}")
    
    sys.exit(1)
    
finally:
    shutdown_transport("claude-cli")
    print("\n清理完成")
