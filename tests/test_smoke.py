#!/usr/bin/env python3
"""
Hermes ACP Client Plugin - Phase 1 冒烟测试

测试 StdioTransport 和 Gemini CLI ACP 服务器的通信。
"""

import sys
import os

# 添加插件目录到路径
plugin_dir = os.path.expanduser("~/.hermes/plugins/acp-client")
sys.path.insert(0, plugin_dir)

from acp.transport import StdioTransport

def test_transport():
    """测试 StdioTransport 基本功能"""
    print("=" * 50)
    print("Hermes ACP Client Plugin - Phase 1 冒烟测试")
    print("=" * 50)
    
    transport = StdioTransport()
    
    try:
        print("\n[1] 启动 ACP 服务器...")
        transport.start()
        print("✓ ACP 服务器已启动")
        
        # 发送一个简单的测试请求
        print("\n[2] 发送测试请求...")
        test_request = {
            "method": "test",
            "params": {"message": "Hello, ACP!"}
        }
        
        response = transport.send_request(test_request)
        print(f"✓ 响应：{response}")
        
        print("\n[3] 停止 ACP 服务器...")
        transport.stop()
        print("✓ ACP 服务器已停止")
        
        print("\n" + "=" * 50)
        print("✓ 冒烟测试通过")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败：{e}")
        transport.stop()
        return False

if __name__ == "__main__":
    success = test_transport()
    sys.exit(0 if success else 1)
