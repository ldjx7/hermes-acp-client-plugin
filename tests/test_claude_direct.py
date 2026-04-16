#!/usr/bin/env python3
"""
测试通过 ACP 插件调用 Claude Code (cc-acp)
"""

import sys
import json
import time
import logging

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

sys.path.insert(0, '/root/.hermes/plugins/acp-client')

from acp.transport import get_transport, initialize_transport, shutdown_transport

def test_claude_direct():
    """直接测试 Claude Code ACP 调用"""
    print("="*60)
    print("测试：通过 ACP 插件直接调用 Claude Code")
    print("="*60 + "\n")
    
    # 1. 初始化 transport
    print("1. 初始化 Claude transport...")
    
    def on_notification(data):
        print(f"\n[通知回调] 收到通知:")
        print(f"  method: {data.get('method')}")
        print(f"  params: {json.dumps(data.get('params', {}), indent=4)}")
    
    initialized = initialize_transport(
        worker="claude",
        request_timeout=120,
        on_notification=on_notification
    )
    
    print(f"初始化结果：{'✅ 成功' if initialized else '❌ 失败'}\n")
    
    if not initialized:
        print("初始化失败，退出测试")
        return False
    
    # 2. 获取 transport
    print("2. 获取 transport 实例...")
    transport = get_transport("claude")
    print(f"transport: {transport}")
    print(f"worker: {transport.worker}")
    print(f"进程状态：{'运行中' if transport.process else '未运行'}\n")
    
    # 3. 创建会话
    print("3. 创建会话...")
    session_resp = transport.create_session(name="claude-test")
    
    print(f"会话响应：{json.dumps(session_resp, indent=2, default=str)[:500]}\n")
    
    # 检查 sessionId
    session_id = None
    if session_resp:
        # 尝试多种路径提取 sessionId
        if "result" in session_resp and isinstance(session_resp["result"], dict):
            session_id = session_resp["result"].get("sessionId") or session_resp["result"].get("id")
        if not session_id:
            session_id = session_resp.get("sessionId") or session_resp.get("id")
        if not session_id and "params" in session_resp:
            session_id = session_resp["params"].get("sessionId")
    
    if session_id:
        print(f"✅ sessionId 提取成功：{session_id}\n")
    else:
        print(f"⚠️  sessionId 提取失败，使用默认值")
        session_id = "test-session-1"
    
    # 4. 发送提示
    print("4. 发送提示到 Claude...")
    prompt = "Hello Claude! Please respond with exactly one sentence: What is 2+2?"
    print(f"提示：{prompt}\n")
    
    print("发送请求...")
    start_time = time.time()
    
    try:
        result = transport.send_prompt(session_id, prompt)
        elapsed = time.time() - start_time
        
        print(f"\n✅ 请求完成 (耗时：{elapsed:.2f}s)")
        print(f"\n响应内容:")
        print(json.dumps(result, indent=2, default=str)[:2000])
        
        # 检查结果
        if result:
            if "error" in result:
                print(f"\n❌ 响应包含错误：{result['error']}")
            elif "result" in result:
                print(f"\n✅ 成功获取结果!")
                result_data = result.get("result", {})
                
                # 提取输出
                if isinstance(result_data, dict):
                    output = result_data.get("result", result_data.get("output", ""))
                    if output:
                        print(f"\n📝 Claude 回复:")
                        print("-" * 60)
                        print(output[:500])
                        print("-" * 60)
                        return True
            
            print(f"\n⚠️  响应格式未知")
            return False
        else:
            print(f"\n❌ 响应为空")
            return False
            
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ 请求失败 (耗时：{elapsed:.2f}s)")
        print(f"错误：{e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # 5. 清理
        print("\n5. 关闭 transport...")
        shutdown_transport("claude")
        print("✅ 清理完成")

def main():
    """运行测试"""
    success = test_claude_direct()
    
    print("\n" + "="*60)
    print("测试结果")
    print("="*60)
    print(f"Claude Code 调用：{'✅ 成功' if success else '❌ 失败'}")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
