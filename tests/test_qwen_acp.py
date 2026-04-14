#!/usr/bin/env python3
"""
Qwen CLI ACP 模式端到端测试

测试 Qwen CLI 的 ACP 协议兼容性
"""

import sys
import json
import time
import logging

sys.path.insert(0, '/root/vibecoding/hermes-acp-client-plugin')

from acp.transport import StdioTransport, get_transport, initialize_transport, shutdown_transport
from acp.protocol import InitializeRequest, NewSessionRequest, PromptRequest
from acp.session_manager import get_session_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("qwen_test")

print("=" * 70)
print("Qwen CLI ACP 模式端到端测试")
print("=" * 70)

# 测试配置
WORKER = "qwen"
TEST_PROMPT = "用中文回复：你好，世界！"
TIMEOUT = 30.0

try:
    # 1. 初始化 Transport
    print("\n[步骤 1] 初始化 Transport...")
    transport = StdioTransport(worker=WORKER, request_timeout=TIMEOUT)
    
    if not transport.start():
        print("✗ Transport 启动失败")
        sys.exit(1)
    
    print(f"✓ Transport 启动成功 (PID: {transport.process.pid})")
    time.sleep(1)
    
    # 2. Initialize 握手
    print("\n[步骤 2] Initialize 握手...")
    init_resp = transport.send(InitializeRequest(), timeout=TIMEOUT)
    
    if init_resp and "result" in init_resp:
        agent_info = init_resp["result"].get("agentInfo", {})
        print(f"✓ Initialize 成功")
        print(f"   Agent: {agent_info.get('name', 'Unknown')} v{agent_info.get('version', '?')}")
    else:
        print(f"✗ Initialize 失败：{init_resp}")
        sys.exit(1)
    
    # 3. 创建会话
    print("\n[步骤 3] 创建会话...")
    session_req = NewSessionRequest.create(name="qwen_e2e_test", cwd="/tmp")
    session_resp = transport.send(session_req, timeout=TIMEOUT)
    
    if session_resp and "result" in session_resp:
        session_id = session_resp["result"].get("sessionId")
        print(f"✓ 会话创建成功：{session_id}")
    else:
        print(f"✗ 创建会话失败：{session_resp}")
        sys.exit(1)
    
    # 4. 发送提示
    print(f"\n[步骤 4] 发送提示...")
    print(f"   提示：{TEST_PROMPT}")
    
    prompt_req = PromptRequest.create(session_id=session_id, prompt=TEST_PROMPT)
    prompt_resp = transport.send(prompt_req, timeout=TIMEOUT)
    
    if prompt_resp:
        if "result" in prompt_resp:
            print(f"✓ 提示发送成功")
            print(f"   停止原因：{prompt_resp['result'].get('stopReason', 'unknown')}")
        elif "error" in prompt_resp:
            print(f"⚠ 提示错误：{prompt_resp.get('error')}")
        else:
            print(f"   响应：{json.dumps(prompt_resp, indent=2)[:300]}")
    else:
        print(f"✗ 无响应")
    
    # 5. 清理
    print("\n[步骤 5] 清理...")
    transport.stop()
    print("✓ Transport 已关闭")
    
    print("\n" + "=" * 70)
    print("✅ Qwen CLI ACP 测试完成!")
    print("=" * 70)
    
except Exception as e:
    print(f"\n✗ 测试失败：{e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
