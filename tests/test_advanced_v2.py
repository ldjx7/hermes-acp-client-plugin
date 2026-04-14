#!/usr/bin/env python3
"""
Qwen ACP 高级用法完整测试 v2

改进：
- 更好的错误处理
- 动态超时调整
- 流式响应捕获
- 详细的执行日志
"""

import sys
import json
import time
import os
from datetime import datetime
from typing import Optional, Dict, Any

sys.path.insert(0, '/root/vibecoding/hermes-acp-client-plugin')

from acp.transport import StdioTransport, get_transport
from acp.protocol import InitializeRequest, NewSessionRequest, PromptRequest
from acp.session_manager import get_session_manager

# 配置
OUTPUT_DIR = "/root/vibecoding/hermes-acp-client-plugin/tests/output/advanced_v2"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 日志
log_file = os.path.join(OUTPUT_DIR, "execution_log.json")
execution_log = []


def log_event(event_type: str, data: Dict[str, Any]):
    """记录执行日志"""
    event = {
        "timestamp": datetime.now().isoformat(),
        "type": event_type,
        "data": data
    }
    execution_log.append(event)
    
    # 实时输出
    emoji = {"start": "🚀", "success": "✅", "error": "❌", "info": "ℹ️"}.get(event_type, "•")
    print(f"{emoji} [{event_type}] {json.dumps(data, ensure_ascii=False)[:200]}")


def save_log():
    """保存执行日志"""
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(execution_log, f, ensure_ascii=False, indent=2)


class ACPExecutor:
    """ACP 执行器 - 管理会话和执行"""
    
    def __init__(self, worker: str = "qwen"):
        self.worker = worker
        self.transport: Optional[StdioTransport] = None
        self.session_id: Optional[str] = None
        self.message_history = []
        
    def start(self, timeout: float = 90.0):
        """启动 transport 和会话"""
        log_event("start", {"worker": self.worker, "timeout": timeout})
        
        self.transport = StdioTransport(
            worker=self.worker,
            request_timeout=timeout,
            max_retries=2
        )
        
        if not self.transport.start():
            raise RuntimeError("Failed to start transport")
        
        time.sleep(1)
        
        # Initialize
        init_resp = self.transport.send(InitializeRequest(), timeout=timeout)
        if not init_resp or "result" not in init_resp:
            raise RuntimeError(f"Initialize failed: {init_resp}")
        
        agent_info = init_resp["result"].get("agentInfo", {})
        log_event("initialized", {
            "agent": agent_info.get("name"),
            "version": agent_info.get("version")
        })
        
        # Create Session
        session_resp = self.transport.send(
            NewSessionRequest.create(cwd=OUTPUT_DIR, mcp_servers=[]),
            timeout=timeout
        )
        
        if not session_resp or "result" not in session_resp:
            raise RuntimeError(f"Create session failed: {session_resp}")
        
        self.session_id = session_resp["result"]["sessionId"]
        log_event("session_created", {"session_id": self.session_id})
        
        return self
    
    def execute(self, prompt: str, timeout: float = 90.0, 
                capture_stream: bool = True) -> Dict[str, Any]:
        """执行任务"""
        log_event("execute_start", {"prompt_length": len(prompt), "timeout": timeout})
        
        start_time = time.time()
        stream_chunks = [] if capture_stream else None
        
        # 定义回调捕获流式响应
        def on_notification(data):
            if capture_stream and data.get("method") == "session/update":
                update = data.get("params", {}).get("update", {})
                if update.get("sessionUpdate") == "agent_message_chunk":
                    content = update.get("content", {})
                    text = content.get("text", "")
                    if text:
                        stream_chunks.append(text)
        
        self.transport._on_notification = on_notification
        
        # 发送请求
        prompt_req = PromptRequest.create(
            session_id=self.session_id,
            prompt=prompt
        )
        
        self.message_history.append({"role": "user", "content": prompt})
        
        resp = self.transport.send(prompt_req, timeout=timeout)
        elapsed = time.time() - start_time
        
        # 构建结果
        result = {
            "success": "error" not in (resp or {}),
            "elapsed_seconds": round(elapsed, 2),
            "response": resp,
            "stream_content": ''.join(stream_chunks) if stream_chunks else None,
            "message_history": self.message_history.copy()
        }
        
        if result["success"]:
            log_event("execute_success", {
                "elapsed": result["elapsed_seconds"],
                "stream_chunks": len(stream_chunks) if stream_chunks else 0
            })
        else:
            log_event("execute_error", {"response": resp})
        
        return result
    
    def chat(self, message: str, timeout: float = 60.0) -> str:
        """多轮对话"""
        result = self.execute(message, timeout=timeout)
        
        if result["success"] and result["stream_content"]:
            self.message_history.append({
                "role": "assistant",
                "content": result["stream_content"]
            })
            return result["stream_content"]
        elif result["success"]:
            # 从响应提取
            return str(result.get("response", {}))
        else:
            raise RuntimeError(f"Chat failed: {result.get('response')}")
    
    def stop(self):
        """停止"""
        if self.transport:
            self.transport.stop()
            log_event("stopped", {"session_id": self.session_id})


def run_test(test_name: str, test_func):
    """运行测试并记录结果"""
    print(f"\n{'='*70}")
    print(f"测试：{test_name}")
    print(f"{'='*70}")
    
    start = time.time()
    try:
        result = test_func()
        elapsed = time.time() - start
        
        test_result = {
            "name": test_name,
            "success": True,
            "elapsed": round(elapsed, 2),
            "result": result
        }
        
        print(f"✅ {test_name} 完成 ({elapsed:.2f}s)")
        return test_result
        
    except Exception as e:
        elapsed = time.time() - start
        test_result = {
            "name": test_name,
            "success": False,
            "elapsed": round(elapsed, 2),
            "error": str(e)
        }
        
        print(f"❌ {test_name} 失败：{e}")
        return test_result


# ============== 测试 1: 代码生成 ==============
def test_code_generation():
    """测试 1: 生成完整代码模块"""
    executor = ACPExecutor(worker="qwen")
    executor.start(timeout=90.0)
    
    prompt = """
生成一个 Python 模块 email_validator，包含：

1. 函数 validate_email(email: str) -> bool
   - 使用正则表达式验证邮箱格式
   - 检查常见域名

2. 函数 validate_email_strict(email: str) -> dict
   - 返回详细验证结果
   - 包含错误信息

3. 类 EmailValidator
   - 支持自定义域名白名单/黑名单
   - 支持批量验证

要求：
- 完整的类型注解
- 详细的文档字符串
- 单元测试示例
- 使用示例

直接输出完整代码。
"""
    
    result = executor.execute(prompt, timeout=120.0)
    executor.stop()
    
    # 保存生成的代码
    if result["success"] and result["stream_content"]:
        code_file = os.path.join(OUTPUT_DIR, "email_validator.py")
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(result["stream_content"])
        result["saved_to"] = code_file
    
    return result


# ============== 测试 2: 代码审查 ==============
def test_code_review():
    """测试 2: 代码安全审查"""
    executor = ACPExecutor(worker="qwen")
    executor.start(timeout=90.0)
    
    prompt = """
请审查以下 Python 代码的安全问题：

```python
import sqlite3

class UserService:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
    
    def get_user(self, user_id):
        query = f"SELECT * FROM users WHERE id = {user_id}"
        return self.conn.execute(query).fetchone()
    
    def update_email(self, user_id, email):
        sql = "UPDATE users SET email = '" + email + "' WHERE id = " + str(user_id)
        self.conn.execute(sql)
        self.conn.commit()
    
    def delete_user(self, user_id):
        if user_id == 1:  # 管理员
            return False
        self.conn.execute(f"DELETE FROM users WHERE id = {user_id}")
        return True
```

请指出：
1. 所有 SQL 注入漏洞
2. 其他安全问题
3. 修复建议（提供修复后的代码）
"""
    
    result = executor.execute(prompt, timeout=120.0)
    executor.stop()
    
    if result["success"] and result["stream_content"]:
        review_file = os.path.join(OUTPUT_DIR, "security_review.md")
        with open(review_file, 'w', encoding='utf-8') as f:
            f.write(result["stream_content"])
        result["saved_to"] = review_file
    
    return result


# ============== 测试 3: 多轮对话 ==============
def test_multi_turn_chat():
    """测试 3: 多轮对话构建项目"""
    executor = ACPExecutor(worker="qwen")
    executor.start(timeout=90.0)
    
    turns = [
        "创建一个 Python 类 TaskManager，支持添加、删除、完成任务。",
        "添加任务优先级功能（高、中、低）。",
        "添加按优先级排序和过滤功能。",
        "添加保存到文件和从文件加载功能。"
    ]
    
    responses = []
    for i, turn in enumerate(turns, 1):
        log_event("chat_turn", {"turn": i, "total": len(turns)})
        response = executor.chat(turn, timeout=60.0)
        responses.append({"turn": i, "response_length": len(response)})
        time.sleep(0.5)
    
    executor.stop()
    
    return {
        "turns": len(turns),
        "responses": responses,
        "total_length": sum(r["response_length"] for r in responses)
    }


# ============== 测试 4: 数据分析 ==============
def test_data_analysis():
    """测试 4: 生成数据分析脚本"""
    executor = ACPExecutor(worker="qwen")
    executor.start(timeout=90.0)
    
    prompt = """
生成一个 Python 脚本分析销售数据：

需求：
1. 读取 CSV 文件 sales_data.csv
2. 计算：
   - 总销售额
   - 平均订单金额
   - 最畅销产品
   - 月度趋势
3. 生成可视化图表（matplotlib）
4. 导出分析报告（JSON 格式）

提供完整可运行的代码。
"""
    
    result = executor.execute(prompt, timeout=120.0)
    executor.stop()
    
    if result["success"] and result["stream_content"]:
        script_file = os.path.join(OUTPUT_DIR, "sales_analysis.py")
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(result["stream_content"])
        result["saved_to"] = script_file
    
    return result


# ============== 测试 5: API 设计 ==============
def test_api_design():
    """测试 5: RESTful API 设计"""
    executor = ACPExecutor(worker="qwen")
    executor.start(timeout=90.0)
    
    prompt = """
设计一个博客系统的 RESTful API：

功能：
1. 用户认证（注册、登录、JWT）
2. 文章管理（CRUD）
3. 评论系统
4. 标签分类

输出：
1. API 端点列表（URL + 方法）
2. 请求/响应示例（JSON）
3. FastAPI 实现代码

用中文说明。
"""
    
    result = executor.execute(prompt, timeout=120.0)
    executor.stop()
    
    if result["success"] and result["stream_content"]:
        api_file = os.path.join(OUTPUT_DIR, "blog_api_design.md")
        with open(api_file, 'w', encoding='utf-8') as f:
            f.write(result["stream_content"])
        result["saved_to"] = api_file
    
    return result


# ============== 运行所有测试 ==============
if __name__ == "__main__":
    print("="*70)
    print("Qwen ACP 高级用法完整测试 v2")
    print("="*70)
    print(f"输出目录：{OUTPUT_DIR}")
    print()
    
    tests = [
        ("代码生成-email_validator", test_code_generation),
        ("代码审查-sql_injection", test_code_review),
        ("多轮对话-TaskManager", test_multi_turn_chat),
        ("数据分析-sales_analysis", test_data_analysis),
        ("API 设计-blog_api", test_api_design),
    ]
    
    results = []
    start_time = time.time()
    
    for test_name, test_func in tests:
        result = run_test(test_name, test_func)
        results.append(result)
        
        # 保存中间结果
        save_log()
        
        # 休息一下
        time.sleep(2)
    
    # 汇总
    total_time = time.time() - start_time
    success_count = sum(1 for r in results if r["success"])
    
    print("\n" + "="*70)
    print("测试汇总")
    print("="*70)
    
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_time_seconds": round(total_time, 2),
        "total_tests": len(results),
        "successful": success_count,
        "failed": len(results) - success_count,
        "tests": [
            {
                "name": r["name"],
                "success": r["success"],
                "elapsed": r["elapsed"],
                "error": r.get("error"),
                "saved_to": r.get("result", {}).get("saved_to")
            }
            for r in results
        ]
    }
    
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"{status} {r['name']}: {r['elapsed']}s" + 
              (f" -> {r['result'].get('saved_to', '')}" if r["success"] else f" - {r.get('error', '')}"))
    
    print(f"\n总计：{success_count}/{len(results)} 成功")
    print(f"总耗时：{total_time:.2f}s")
    
    # 保存汇总
    with open(os.path.join(OUTPUT_DIR, "summary.json"), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    save_log()
    
    print(f"\n结果已保存：{OUTPUT_DIR}")
    print("="*70)
    
    sys.exit(0 if success_count >= len(results) * 0.8 else 1)
