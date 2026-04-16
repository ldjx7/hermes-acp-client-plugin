#!/usr/bin/env python3
"""
ACP Client 协议兼容性测试

测试修复后的 ACP 协议兼容性，验证能否正确：
1. 创建会话（或处理自动创建）
2. 发送提示并获取响应
3. 提取 sessionId（兼容多种格式）
"""

import sys
import time
import json
sys.path.insert(0, '/root/.hermes/plugins/acp-client')

from acp.transport import get_transport, initialize_transport, shutdown_transport
from tools import acp_dispatch

def test_session_id_extraction():
    """测试 sessionId 提取逻辑"""
    print("="*60)
    print("测试 1: sessionId 提取兼容性")
    print("="*60 + "\n")
    
    # 模拟不同 ACP 实现的响应格式
    test_responses = [
        # 标准 ACP 格式
        {"result": {"sessionId": "std-123"}},
        # Gemini 格式（id 而非 sessionId）
        {"result": {"id": "gemini-456"}},
        # 顶层 sessionId
        {"sessionId": "top-789"},
        # 顶层 id
        {"id": "top-id-012"},
        # params 中的 sessionId（通知回调）
        {"params": {"sessionId": "param-345"}},
        # 复杂嵌套
        {"result": {"sessionId": "nested-678"}, "id": "outer-901"},
    ]
    
    expected_ids = [
        "std-123",
        "gemini-456",
        "top-789",
        "top-id-012",
        "param-345",
        "nested-678",
    ]
    
    for i, resp in enumerate(test_responses):
        # 模拟 tools.py 中的提取逻辑
        session_id = None
        
        # 路径 1: 标准 ACP - resp.result.sessionId
        if not session_id and "result" in resp:
            session_id = resp["result"].get("sessionId")
        
        # 路径 2: Gemini 可能直接返回 sessionId 在 result 中
        if not session_id and "result" in resp and isinstance(resp["result"], dict):
            session_id = resp["result"].get("id")
        
        # 路径 3: 某些实现可能直接返回 sessionId 在顶层
        if not session_id:
            session_id = resp.get("sessionId") or resp.get("id")
        
        # 路径 4: 如果还是没有，尝试从 params 中提取
        if not session_id and "params" in resp:
            session_id = resp["params"].get("sessionId")
        
        expected = expected_ids[i]
        status = "✅" if session_id == expected else "❌"
        print(f"{status} 测试 {i+1}: {session_id} (期望：{expected})")
    
    print()

def test_gemini_dispatch():
    """测试 Gemini 调用"""
    print("="*60)
    print("测试 2: Gemini 实际调用")
    print("="*60 + "\n")
    
    try:
        result = acp_dispatch(
            task="你好，请用一句话回复。",
            worker="gemini",
            timeout=120,
            auto_fallback=False
        )
        
        print(f"响应：{result[:500] if isinstance(result, str) else result}\n")
        
        # 检查响应格式
        try:
            data = json.loads(result)
            if "sessionId" in data:
                print(f"✅ sessionId 提取成功：{data['sessionId']}")
            else:
                print(f"⚠️  响应中没有 sessionId")
                print(f"   响应键：{list(data.keys())}")
        except json.JSONDecodeError:
            print(f"⚠️  响应不是有效 JSON")
        
    except Exception as e:
        print(f"❌ 错误：{e}\n")

def test_claude_dispatch():
    """测试 Claude Code 调用"""
    print("="*60)
    print("测试 3: Claude Code (cc-acp) 调用")
    print("="*60 + "\n")
    
    try:
        result = acp_dispatch(
            task="Hello, please respond with one sentence.",
            worker="claude",
            timeout=120,
            auto_fallback=False
        )
        
        print(f"响应：{result[:500] if isinstance(result, str) else result}\n")
        
        # 检查响应格式
        try:
            data = json.loads(result)
            if "sessionId" in data:
                print(f"✅ sessionId 提取成功：{data['sessionId']}")
            else:
                print(f"⚠️  响应中没有 sessionId")
                print(f"   响应键：{list(data.keys())}")
        except json.JSONDecodeError:
            print(f"⚠️  响应不是有效 JSON")
        
    except Exception as e:
        print(f"❌ 错误：{e}\n")

def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("ACP Client 协议兼容性测试")
    print("="*60 + "\n")
    
    # 测试 1: sessionId 提取
    test_session_id_extraction()
    
    # 测试 2: Gemini 调用
    test_gemini_dispatch()
    
    # 测试 3: Claude 调用
    test_claude_dispatch()
    
    print("="*60)
    print("测试完成")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
