#!/usr/bin/env python3
"""
快速测试 Gemini 和 Claude Code 调用
"""

import sys
import time
import json

sys.path.insert(0, '/root/.hermes/plugins/acp-client')

from tools import acp_dispatch
from acp.session_manager import get_session_manager

def wait_for_result(session_id, timeout=120, check_interval=3):
    """等待任务完成并获取结果"""
    print(f"等待任务完成 (session: {session_id})...")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        time.sleep(check_interval)
        
        sessions = get_session_manager()._sessions
        if session_id in sessions:
            session = sessions[session_id]
            status = session.status.value
            
            print(f"  [{int(time.time()-start_time)}s] 状态：{status}", end="")
            if session.progress:
                print(f", 进度：{session.progress}%", end="")
            print()
            
            if status == "completed":
                return {"status": "success", "result": session.result}
            elif status == "failed":
                return {"status": "failed", "error": session.error}
            elif status == "cancelled":
                return {"status": "cancelled"}
    
    return {"status": "timeout"}

def test_gemini():
    """测试 Gemini 调用"""
    print("\n" + "="*60)
    print("测试 1: Gemini 代码审查")
    print("="*60 + "\n")
    
    task = "请用一句话回答：Python 中什么是列表推导式？"
    print(f"任务：{task}\n")
    
    try:
        result = acp_dispatch(
            task=task,
            worker="gemini",
            timeout=120,
            auto_fallback=False
        )
        
        print(f"派发结果：{result[:300]}\n")
        
        # 解析响应
        try:
            data = json.loads(result)
            session_id = data.get("sessionId")
            
            if session_id:
                print(f"✅ sessionId 提取成功：{session_id}\n")
                
                # 等待完成
                final_result = wait_for_result(session_id, timeout=90)
                
                if final_result["status"] == "success":
                    print("\n✅ Gemini 响应:")
                    print("-" * 60)
                    print(final_result["result"][:1000])
                    print("-" * 60)
                    return True
                elif final_result["status"] == "failed":
                    print(f"\n❌ 任务失败：{final_result['error']}")
                else:
                    print(f"\n⏱️ 任务超时")
            else:
                print(f"❌ sessionId 提取失败")
                print(f"响应数据：{data}")
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析失败：{e}")
            print(f"原始响应：{result[:500]}")
            
    except Exception as e:
        print(f"❌ 错误：{e}")
        import traceback
        traceback.print_exc()
    
    return False

def test_claude():
    """测试 Claude Code 调用"""
    print("\n" + "="*60)
    print("测试 2: Claude Code 代码审查")
    print("="*60 + "\n")
    
    task = "Hello! Please respond with one sentence: What is list comprehension in Python?"
    print(f"任务：{task}\n")
    
    try:
        result = acp_dispatch(
            task=task,
            worker="claude",
            timeout=120,
            auto_fallback=False
        )
        
        print(f"派发结果：{result[:300]}\n")
        
        # 解析响应
        try:
            data = json.loads(result)
            session_id = data.get("sessionId")
            
            if session_id:
                print(f"✅ sessionId 提取成功：{session_id}\n")
                
                # 等待完成
                final_result = wait_for_result(session_id, timeout=90)
                
                if final_result["status"] == "success":
                    print("\n✅ Claude Code 响应:")
                    print("-" * 60)
                    print(final_result["result"][:1000])
                    print("-" * 60)
                    return True
                elif final_result["status"] == "failed":
                    print(f"\n❌ 任务失败：{final_result['error']}")
                else:
                    print(f"\n⏱️ 任务超时")
            else:
                print(f"❌ sessionId 提取失败")
                print(f"响应数据：{data}")
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析失败：{e}")
            print(f"原始响应：{result[:500]}")
            
    except Exception as e:
        print(f"❌ 错误：{e}")
        import traceback
        traceback.print_exc()
    
    return False

def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("ACP Client 协议修复验证测试")
    print("="*60)
    
    gemini_result = test_gemini()
    claude_result = test_claude()
    
    print("\n" + "="*60)
    print("测试结果总结")
    print("="*60 + "\n")
    
    print(f"Gemini: {'✅ 成功' if gemini_result else '❌ 失败'}")
    print(f"Claude Code: {'✅ 成功' if claude_result else '❌ 失败'}")
    
    if gemini_result and claude_result:
        print("\n🎉 所有测试通过！ACP 协议兼容性修复成功！")
    else:
        print("\n⚠️ 部分测试失败，需要进一步调试")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()
