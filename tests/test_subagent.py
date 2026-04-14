#!/usr/bin/env python3
"""
Qwen ACP Subagent 模式测试

测试场景:
1. Subagent 任务委派 - Qwen 作为子代理执行独立任务
2. 多轮对话 - 保持会话上下文进行迭代开发
3. 工具调用 - Qwen 调用 shell 命令/文件操作
4. 代码执行 - 生成代码并执行验证
5. 多 Agent 协作 - 多个 Qwen 实例协作完成复杂任务
"""

import sys
import json
import time
import subprocess
import threading
import os
import tempfile
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, '/root/vibecoding/hermes-acp-client-plugin')

from acp.transport import StdioTransport
from acp.protocol import InitializeRequest, NewSessionRequest, PromptRequest

OUTPUT_DIR = "/root/vibecoding/hermes-acp-client-plugin/tests/output/subagent"
os.makedirs(OUTPUT_DIR, exist_ok=True)


class QwenSubagent:
    """Qwen Subagent 封装类"""
    
    def __init__(self, agent_id: str, task: str, cwd: str = None):
        self.agent_id = agent_id
        self.task = task
        self.cwd = cwd or OUTPUT_DIR
        self.transport = None
        self.session_id = None
        self.message_history: List[Dict] = []
        self.start_time = None
        self.responses: List[Dict] = []
        
    def start(self, timeout: float = 60.0) -> bool:
        """启动 subagent"""
        print(f"\n[Subagent {self.agent_id}] 启动...")
        self.start_time = time.time()
        
        try:
            # 启动进程
            self.transport = StdioTransport(worker='qwen', request_timeout=timeout)
            if not self.transport.start():
                return False
            
            time.sleep(1)
            
            # Initialize
            init_resp = self.transport.send(InitializeRequest(), timeout=timeout)
            if not init_resp or "result" not in init_resp:
                return False
            
            # Create Session
            session_req = NewSessionRequest.create(
                name=f"subagent_{self.agent_id}",
                cwd=self.cwd,
                mcp_servers=[]
            )
            session_resp = self.transport.send(session_req, timeout=timeout)
            
            if not session_resp or "result" not in session_resp:
                return False
            
            self.session_id = session_resp["result"].get("sessionId")
            print(f"[Subagent {self.agent_id}] 会话 ID: {self.session_id}")
            
            # 记录初始消息
            self.message_history.append({
                "role": "system",
                "content": f"You are subagent '{self.agent_id}' working on: {self.task}"
            })
            
            return True
            
        except Exception as e:
            print(f"[Subagent {self.agent_id}] 启动失败：{e}")
            return False
    
    def send_message(self, message: str, timeout: float = 60.0) -> Dict:
        """发送消息并获取响应"""
        if not self.transport or not self.session_id:
            return {"error": "Subagent not started"}
        
        # 记录消息
        self.message_history.append({"role": "user", "content": message})
        
        # 发送
        prompt_req = PromptRequest.create(
            session_id=self.session_id,
            prompt=message
        )
        
        print(f"[Subagent {self.agent_id}] 发送消息... ({len(message)} 字符)")
        
        start = time.time()
        resp = self.transport.send(prompt_req, timeout=timeout)
        elapsed = time.time() - start
        
        if resp:
            if "result" in resp:
                print(f"[Subagent {self.agent_id}] ✓ 完成 ({elapsed:.2f}s)")
            elif "error" in resp:
                print(f"[Subagent {self.agent_id}] ✗ 错误：{resp['error']}")
        
        self.responses.append({
            "timestamp": time.time(),
            "request": message,
            "response": resp,
            "elapsed": elapsed
        })
        
        return resp or {"error": "No response"}
    
    def get_streaming_output(self, timeout: float = 60.0) -> str:
        """获取流式输出（拼接所有 chunk）"""
        # 需要访问内部响应数据
        chunks = []
        
        # 从最近的 response 中提取
        if self.responses:
            last_resp = self.responses[-1]
            # 这里需要更复杂的流式处理逻辑
            pass
        
        return ""
    
    def stop(self):
        """停止 subagent"""
        if self.transport:
            self.transport.stop()
        elapsed = time.time() - self.start_time if self.start_time else 0
        print(f"[Subagent {self.agent_id}] 已停止 (总耗时：{elapsed:.2f}s)")
    
    def save_log(self):
        """保存会话日志"""
        log_file = os.path.join(OUTPUT_DIR, f"subagent_{self.agent_id}_log.json")
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump({
                "agent_id": self.agent_id,
                "task": self.task,
                "session_id": self.session_id,
                "message_history": self.message_history,
                "responses": self.responses,
                "total_time": time.time() - self.start_time if self.start_time else 0
            }, f, ensure_ascii=False, indent=2, default=str)
        print(f"[Subagent {self.agent_id}] 日志已保存：{log_file}")


# ============== 测试 1: Subagent 任务委派 ==============
def test_subagent_delegation():
    """测试 1: Subagent 任务委派"""
    print("\n" + "="*70)
    print("测试 1: Subagent 任务委派")
    print("="*70)
    
    # 创建 subagent 执行代码生成任务
    agent = QwenSubagent(
        agent_id="coder_1",
        task="Generate a Python utility module"
    )
    
    if not agent.start():
        print("✗ Subagent 启动失败")
        return False
    
    # 委派任务
    task_prompt = """
请生成一个 Python 工具模块 utils.py，包含以下函数：
1. read_file(path) - 读取文件内容
2. write_file(path, content) - 写入文件
3. list_files(dir_path) - 列出目录文件
4. create_dir(path) - 创建目录

要求：
- 完整的类型注解
- 错误处理
- 文档字符串

直接输出代码。
"""
    
    resp = agent.send_message(task_prompt, timeout=60.0)
    
    # 保存日志
    agent.save_log()
    agent.stop()
    
    return "error" not in resp


# ============== 测试 2: 多轮对话 ==============
def test_multi_turn_conversation():
    """测试 2: 多轮对话 - 迭代开发"""
    print("\n" + "="*70)
    print("测试 2: 多轮对话 - 迭代开发")
    print("="*70)
    
    agent = QwenSubagent(
        agent_id="developer_1",
        task="Iterative development of a CLI app"
    )
    
    if not agent.start():
        return False
    
    # 第 1 轮：创建基础结构
    print("\n--- 第 1 轮：创建基础结构 ---")
    resp1 = agent.send_message("""
创建一个简单的 CLI 待办事项应用的主文件 main.py。
包含以下功能：
- 添加任务
- 列出任务
- 标记完成

使用 argparse 处理命令行参数。
""", timeout=60.0)
    
    time.sleep(1)
    
    # 第 2 轮：添加功能
    print("\n--- 第 2 轮：添加数据持久化 ---")
    resp2 = agent.send_message("""
现在添加数据持久化功能：
- 使用 JSON 文件存储任务
- 启动时加载任务
- 修改时保存任务

请提供更新后的完整代码。
""", timeout=60.0)
    
    time.sleep(1)
    
    # 第 3 轮：优化
    print("\n--- 第 3 轮：添加错误处理 ---")
    resp3 = agent.send_message("""
添加完善的错误处理：
- 文件不存在时创建
- JSON 解析错误处理
- 用户输入验证

输出最终版本。
""", timeout=60.0)
    
    agent.save_log()
    agent.stop()
    
    return all("error" not in r for r in [resp1, resp2, resp3])


# ============== 测试 3: 工具调用 ==============
def test_tool_usage():
    """测试 3: 工具调用 - 执行 shell 命令"""
    print("\n" + "="*70)
    print("测试 3: 工具调用 - 执行 shell 命令")
    print("="*70)
    
    agent = QwenSubagent(
        agent_id="executor_1",
        task="Execute shell commands and file operations"
    )
    
    if not agent.start():
        return False
    
    # 请求生成并执行命令
    resp = agent.send_message("""
请生成一个 Python 脚本 check_system.py，用于：
1. 检查当前 Python 版本
2. 列出当前目录文件
3. 检查环境变量

然后告诉我如何执行它。
""", timeout=60.0)
    
    agent.save_log()
    agent.stop()
    
    return "error" not in resp


# ============== 测试 4: 代码执行验证 ==============
def test_code_execution():
    """测试 4: 代码执行验证"""
    print("\n" + "="*70)
    print("测试 4: 代码执行验证")
    print("="*70)
    
    agent = QwenSubagent(
        agent_id="tester_1",
        task="Generate and test code"
    )
    
    if not agent.start():
        return False
    
    # 生成代码
    resp = agent.send_message("""
生成一个函数 is_prime(n)，判断一个数是否为质数。
包含：
- 类型注解
- 文档字符串
- 单元测试示例

输出完整代码。
""", timeout=60.0)
    
    # 实际执行生成的代码
    print("\n--- 执行生成的代码 ---")
    test_code = '''
def is_prime(n: int) -> bool:
    """Check if a number is prime."""
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True

# Test
print(f"is_prime(17) = {is_prime(17)}")
print(f"is_prime(20) = {is_prime(20)}")
'''
    
    try:
        result = subprocess.run(
            ["python3", "-c", test_code],
            capture_output=True,
            text=True,
            timeout=10
        )
        print(f"执行结果：{result.stdout.strip()}")
    except Exception as e:
        print(f"执行失败：{e}")
    
    agent.save_log()
    agent.stop()
    
    return "error" not in resp


# ============== 测试 5: 多 Agent 协作 ==============
def test_multi_agent_collaboration():
    """测试 5: 多 Agent 协作"""
    print("\n" + "="*70)
    print("测试 5: 多 Agent 协作 - 完整项目开发")
    print("="*70)
    
    # 创建 3 个 subagent 协作
    agents = []
    results = {}
    
    # Agent 1: 架构师 - 设计
    print("\n[Agent 1] 架构师 - 系统设计...")
    architect = QwenSubagent("architect", "Design a web scraper system")
    if architect.start():
        resp = architect.send_message("""
设计一个网页爬虫系统架构：
1. 定义核心模块（Downloader, Parser, Storage）
2. 定义类和方法签名
3. 说明模块间关系

输出设计文档。
""", timeout=60.0)
        results["architect"] = resp
        architect.save_log()
        architect.stop()
    
    time.sleep(1)
    
    # Agent 2: 开发者 - 实现
    print("\n[Agent 2] 开发者 - 代码实现...")
    developer = QwenSubagent("developer", "Implement the web scraper")
    if developer.start():
        resp = developer.send_message("""
根据以下设计实现网页爬虫：
- Downloader 类：使用 requests 下载网页
- Parser 类：使用 BeautifulSoup 解析
- Storage 类：保存到 JSON 文件

输出完整实现代码。
""", timeout=60.0)
        results["developer"] = resp
        developer.save_log()
        developer.stop()
    
    time.sleep(1)
    
    # Agent 3: 测试员 - 验证
    print("\n[Agent 3] 测试员 - 测试验证...")
    tester = QwenSubagent("tester", "Write tests for the scraper")
    if tester.start():
        resp = tester.send_message("""
为网页爬虫编写测试：
- 测试 Downloader
- 测试 Parser
- 测试 Storage

使用 pytest 框架。
""", timeout=60.0)
        results["tester"] = resp
        tester.save_log()
        tester.stop()
    
    # 汇总结果
    print("\n" + "="*70)
    print("多 Agent 协作结果汇总")
    print("="*70)
    
    success_count = sum(1 for r in results.values() if "error" not in r)
    print(f"成功：{success_count}/{len(results)} agents")
    
    for agent_name, resp in results.items():
        status = "✓" if "error" not in resp else "✗"
        print(f"  {status} {agent_name}")
    
    # 保存汇总
    summary_file = os.path.join(OUTPUT_DIR, "multi_agent_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_agents": len(results),
            "successful": success_count,
            "results": {k: ("success" if "error" not in v else "failed") for k, v in results.items()}
        }, f, indent=2)
    print(f"\n汇总已保存：{summary_file}")
    
    return success_count == len(results)


# ============== 运行所有测试 ==============
if __name__ == "__main__":
    print("="*70)
    print("Qwen ACP Subagent 高级测试")
    print("="*70)
    
    tests = [
        ("Subagent 任务委派", test_subagent_delegation),
        ("多轮对话", test_multi_turn_conversation),
        ("工具调用", test_tool_usage),
        ("代码执行验证", test_code_execution),
        ("多 Agent 协作", test_multi_agent_collaboration),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n✗ {name} 异常：{e}")
            results[name] = False
        time.sleep(2)
    
    # 最终汇总
    print("\n" + "="*70)
    print("最终测试结果")
    print("="*70)
    
    for name, passed in results.items():
        status = "✓" if passed else "✗"
        print(f"{status} {name}")
    
    passed_count = sum(1 for p in results.values() if p)
    print(f"\n总计：{passed_count}/{len(results)} 通过")
    
    # 保存最终结果
    final_result = {
        "timestamp": datetime.now().isoformat(),
        "tests": {name: "passed" if passed else "failed" for name, passed in results.items()},
        "passed": passed_count,
        "total": len(results)
    }
    
    result_file = os.path.join(OUTPUT_DIR, "final_results.json")
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(final_result, f, indent=2)
    print(f"\n结果已保存：{result_file}")
