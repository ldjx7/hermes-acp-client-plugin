#!/usr/bin/env python3
"""
直接测试 Gemini ACP 输出，查看实际返回的 JSON 格式
"""

import subprocess
import json
import time
import sys

def test_gemini_output():
    """直接捕获 Gemini 输出"""
    print("="*60)
    print("直接测试 Gemini ACP 输出")
    print("="*60 + "\n")
    
    # 启动 Gemini
    cmd = ["gemini", "--acp", "--model", "gemini-2.5-flash"]
    print(f"启动命令：{' '.join(cmd)}\n")
    
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    # 发送初始化
    init_msg = {
        "jsonrpc": "2.0",
        "id": "init-1",
        "method": "initialize",
        "params": {
            "protocolVersion": 1,
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0.0"}
        }
    }
    
    print(f"发送初始化：{json.dumps(init_msg)[:100]}...\n")
    process.stdin.write(json.dumps(init_msg) + "\n")
    process.stdin.flush()
    
    # 读取响应（等待 10 秒）
    print("读取初始化响应...")
    start = time.time()
    while time.time() - start < 10:
        try:
            line = process.stdout.readline()
            if line:
                print(f"收到：{line.strip()[:200]}")
                if line.strip().startswith('{'):
                    try:
                        data = json.loads(line)
                        print(f"解析成功：{json.dumps(data, indent=2)[:300]}")
                    except:
                        pass
        except Exception as e:
            print(f"读取错误：{e}")
            break
    
    # 发送创建会话
    session_msg = {
        "jsonrpc": "2.0",
        "id": "session-1",
        "method": "session/new",
        "params": {
            "name": "test",
            "cwd": "/tmp",
            "mcpServers": []
        }
    }
    
    print(f"\n发送创建会话：{json.dumps(session_msg)[:100]}...\n")
    process.stdin.write(json.dumps(session_msg) + "\n")
    process.stdin.flush()
    
    # 读取响应
    print("读取会话创建响应...")
    start = time.time()
    while time.time() - start < 10:
        try:
            line = process.stdout.readline()
            if line:
                print(f"收到：{line.strip()[:200]}")
                if line.strip().startswith('{'):
                    try:
                        data = json.loads(line)
                        print(f"解析成功：{json.dumps(data, indent=2)[:500]}")
                        
                        # 检查 sessionId
                        if "result" in data:
                            result = data["result"]
                            if isinstance(result, dict):
                                session_id = result.get("sessionId") or result.get("id")
                                if session_id:
                                    print(f"\n✅ sessionId 找到：{session_id}")
                                    break
                    except json.JSONDecodeError as e:
                        print(f"JSON 错误：{e}")
        except Exception as e:
            print(f"读取错误：{e}")
            break
    
    # 清理
    process.terminate()
    try:
        process.wait(timeout=5)
    except:
        process.kill()
    
    print("\n完成")

if __name__ == "__main__":
    test_gemini_output()
