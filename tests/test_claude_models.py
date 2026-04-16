#!/usr/bin/env python3
"""
测试通过 ACP 插件调用 Claude Code - 使用不同模型
"""

import sys
import json
import time
import os

sys.path.insert(0, '/root/.hermes/plugins/acp-client')

from acp.transport import get_transport, initialize_transport, shutdown_transport

def test_claude_with_model(model="sonnet"):
    """测试使用指定模型"""
    print("="*60)
    print(f"测试：Claude Code ({model} 模型)")
    print("="*60 + "\n")
    
    # 设置模型环境变量
    os.environ["CLAUDE_MODEL"] = model
    print(f"使用模型：{model}\n")
    
    # 通知回调
    notifications = []
    def on_notification(data):
        notifications.append(data)
        method = data.get('method')
        params = data.get('params', {})
        print(f"[通知] {method}")
        
        if 'update' in params:
            update = params['update']
            if isinstance(update, dict) and 'content' in update:
                content = update.get('content', {})
                text = content.get('text', '')
                if text and len(text) < 200:
                    print(f"  内容：{text[:100]}...")
    
    # 初始化
    print("初始化 transport...")
    initialized = initialize_transport(
        worker="claude",
        request_timeout=120,
        on_notification=on_notification
    )
    
    if not initialized:
        print("❌ 初始化失败\n")
        return False
    
    try:
        transport = get_transport("claude")
        
        # 创建会话
        print("创建会话...")
        session_resp = transport.create_session(name=f"test-{model}")
        
        session_id = None
        if session_resp and "result" in session_resp:
            session_id = session_resp["result"].get("sessionId")
        
        if not session_id:
            print(f"❌ 无法获取 sessionId")
            print(f"响应：{session_resp}")
            return False
        
        print(f"✅ sessionId: {session_id}\n")
        
        # 发送提示
        prompt = "Hello! Please answer in one sentence: What is 2+2?"
        print(f"发送提示：{prompt}\n")
        
        result = transport.send_prompt(session_id, prompt)
        
        print(f"\n等待响应...")
        time.sleep(5)  # 等待通知
        
        # 检查结果
        print(f"\n最终结果:")
        print(json.dumps(result, indent=2, default=str)[:1000])
        
        # 分析通知
        print(f"\n收到 {len(notifications)} 个通知:")
        for i, notif in enumerate(notifications):
            params = notif.get('params', {})
            if 'update' in params:
                update = params['update']
                if isinstance(update, dict) and 'content' in update:
                    text = update.get('content', {}).get('text', '')
                    if text:
                        print(f"\n通知 {i+1}:")
                        print(f"  {text[:300]}")
        
        # 判断是否成功
        has_error = False
        for notif in notifications:
            params = notif.get('params', {})
            if 'update' in params:
                text = str(params.get('update', {}))
                if 'Error' in text or 'error' in text or '403' in text:
                    has_error = True
                    break
        
        if has_error:
            print(f"\n❌ {model} 模型调用失败")
            return False
        else:
            print(f"\n✅ {model} 模型调用成功")
            return True
        
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        shutdown_transport("claude")
        print("\n清理完成\n")

def main():
    """测试不同模型"""
    models_to_test = ["sonnet", "haiku"]  # 跳过 opus，因为没有权限
    
    results = {}
    for model in models_to_test:
        print("\n" + "="*60)
        print(f"测试模型：{model}")
        print("="*60 + "\n")
        
        results[model] = test_claude_with_model(model)
        
        # 清理环境变量
        if "CLAUDE_MODEL" in os.environ:
            del os.environ["CLAUDE_MODEL"]
        
        time.sleep(2)
    
    # 总结
    print("\n" + "="*60)
    print("测试结果总结")
    print("="*60 + "\n")
    
    for model, success in results.items():
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{model}: {status}")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()
