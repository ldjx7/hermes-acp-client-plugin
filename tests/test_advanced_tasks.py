#!/usr/bin/env python3
"""
Qwen ACP 高级测试 - 实际任务场景

测试场景:
1. 代码生成 - 生成完整 Python 模块
2. 代码审查 - 分析代码并给出建议
3. 文件操作 - 创建/修改文件
4. 复杂任务 - 多步骤任务分解
5. 进度追踪 - 长时间任务监控
"""

import sys
import json
import time
import os
import tempfile
from datetime import datetime

sys.path.insert(0, '/root/vibecoding/hermes-acp-client-plugin')

from acp.transport import StdioTransport
from acp.protocol import InitializeRequest, NewSessionRequest, PromptRequest
from acp.session_manager import get_session_manager

# 配置
WORKER = "qwen"
TIMEOUT = 60.0
OUTPUT_DIR = "/root/vibecoding/hermes-acp-client-plugin/tests/output"

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 70)
print("Qwen ACP 高级测试 - 实际任务场景")
print("=" * 70)


def run_task(task_name: str, prompt: str, timeout: float = TIMEOUT) -> dict:
    """运行单个任务并记录结果"""
    print(f"\n{'='*70}")
    print(f"任务：{task_name}")
    print(f"{'='*70}")
    
    transport = None
    try:
        # 初始化
        transport = StdioTransport(worker=WORKER, request_timeout=timeout)
        if not transport.start():
            return {"error": "Failed to start transport"}
        
        time.sleep(1)
        
        # Initialize
        init_resp = transport.send(InitializeRequest(), timeout=timeout)
        if not init_resp or "result" not in init_resp:
            return {"error": "Initialize failed", "response": init_resp}
        
        # Create Session
        session_req = NewSessionRequest.create(
            name=f"test_{int(time.time())}",
            cwd=OUTPUT_DIR,
            mcp_servers=[]
        )
        session_resp = transport.send(session_req, timeout=timeout)
        if not session_resp or "result" not in session_resp:
            return {"error": "Create session failed", "response": session_resp}
        
        session_id = session_resp["result"].get("sessionId")
        print(f"会话 ID: {session_id}")
        
        # Send Prompt
        start_time = time.time()
        prompt_req = PromptRequest.create(session_id=session_id, prompt=prompt)
        print(f"发送提示... ({len(prompt)} 字符)")
        
        resp = transport.send(prompt_req, timeout=timeout)
        elapsed = time.time() - start_time
        
        result = {
            "task": task_name,
            "session_id": session_id,
            "elapsed_seconds": round(elapsed, 2),
            "response": resp,
            "timestamp": datetime.now().isoformat()
        }
        
        if resp and "result" in resp:
            print(f"✓ 完成 (耗时：{elapsed:.2f}s)")
            print(f"  停止原因：{resp['result'].get('stopReason', 'unknown')}")
        elif resp and "error" in resp:
            print(f"✗ 错误：{resp.get('error')}")
            result["error"] = resp["error"]
        else:
            print(f"? 未知响应")
        
        # 保存结果
        output_file = os.path.join(OUTPUT_DIR, f"{task_name.replace(' ', '_')}.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"结果已保存：{output_file}")
        
        return result
        
    except Exception as e:
        print(f"✗ 异常：{e}")
        return {"error": str(e), "task": task_name}
    finally:
        if transport:
            transport.stop()


# ============== 测试 1: 代码生成 ==============
task1_prompt = """
请生成一个完整的 Python 模块，实现以下功能：

1. 创建一个 Calculator 类，支持：
   - 加法 (add)
   - 减法 (subtract)
   - 乘法 (multiply)
   - 除法 (divide)
   - 幂运算 (power)
   - 平方根 (sqrt)

2. 添加错误处理（如除零错误）

3. 添加类型注解

4. 包含完整的文档字符串

5. 添加单元测试示例

请直接输出完整的 Python 代码，不要解释。
"""

result1 = run_task("代码生成-Calculator", task1_prompt)


# ============== 测试 2: 代码审查 ==============
task2_prompt = """
请审查以下 Python 代码，指出：
1. 潜在的安全问题
2. 性能问题
3. 代码风格问题
4. 改进建议

代码：
```python
def get_user_data(user_id):
    query = "SELECT * FROM users WHERE id = " + str(user_id)
    result = db.execute(query)
    
    data = []
    for row in result:
        data.append({
            'id': row[0],
            'name': row[1],
            'email': row[2],
            'password': row[3]  # 返回密码
        })
    
    return data

def process_items(items):
    result = []
    for i in range(len(items)):
        if items[i] % 2 == 0:
            result.append(items[i] * 2)
        else:
            result.append(items[i])
    return result
```

请用中文回复，给出具体的修改建议。
"""

result2 = run_task("代码审查-Security", task2_prompt)


# ============== 测试 3: 文件操作 ==============
task3_prompt = """
请创建一个完整的 Python 项目结构，包含以下文件：

1. main.py - 程序入口
2. config.py - 配置管理
3. utils/logger.py - 日志工具
4. utils/helpers.py - 辅助函数
5. requirements.txt - 依赖列表
6. README.md - 项目说明

这是一个简单的 CLI 待办事项应用 (Todo App)。

请为每个文件提供完整的代码内容，使用以下格式：

## 文件名：path/to/file.py
```python
# 代码内容
```

开始生成。
"""

result3 = run_task("文件操作-TodoApp", task3_prompt)


# ============== 测试 4: 算法实现 ==============
task4_prompt = """
请实现以下经典算法，使用 Python：

1. 快速排序 (Quick Sort)
2. 二分查找 (Binary Search)
3. 广度优先搜索 (BFS)
4. 深度优先搜索 (DFS)
5. Dijkstra 最短路径算法

要求：
- 每个算法都有完整的类型注解
- 包含详细的文档字符串
- 提供使用示例
- 添加时间复杂度分析

请直接输出代码。
"""

result4 = run_task("算法实现-Classics", task4_prompt)


# ============== 测试 5: API 设计 ==============
task5_prompt = """
请设计一个 RESTful API，用于博客系统。

需要包含：
1. 用户认证 (注册/登录/JWT)
2. 文章管理 (CRUD)
3. 评论系统
4. 标签分类
5. 分页查询

请提供：
1. API 端点列表 (URL + 方法)
2. 请求/响应格式 (JSON Schema)
3. 错误码定义
4. Python Flask/FastAPI 实现示例

用中文说明。
"""

result5 = run_task("API 设计-Blog", task5_prompt)


# ============== 测试 6: 数据分析 ==============
task6_prompt = """
请生成一个 Python 数据分析脚本，用于分析销售数据。

功能需求：
1. 读取 CSV 文件 (sales.csv)
2. 数据清洗 (处理缺失值、异常值)
3. 计算统计指标 (均值、中位数、标准差)
4. 按月份/地区/产品分组分析
5. 生成可视化图表 (使用 matplotlib)
6. 导出分析报告 (PDF 或 HTML)

请提供完整的可运行代码。
"""

result6 = run_task("数据分析-Sales", task6_prompt)


# ============== 汇总结果 ==============
print("\n" + "=" * 70)
print("测试汇总")
print("=" * 70)

tasks = [
    ("代码生成-Calculator", result1),
    ("代码审查-Security", result2),
    ("文件操作-TodoApp", result3),
    ("算法实现-Classics", result4),
    ("API 设计-Blog", result5),
    ("数据分析-Sales", result6),
]

success_count = 0
total_time = 0

for name, result in tasks:
    if "error" not in result:
        success_count += 1
        total_time += result.get("elapsed_seconds", 0)
        status = "✓"
    else:
        status = "✗"
    
    elapsed = result.get("elapsed_seconds", 0)
    print(f"{status} {name}: {elapsed:.2f}s")

print(f"\n总计：{success_count}/{len(tasks)} 成功")
print(f"总耗时：{total_time:.2f}s")
print(f"平均耗时：{total_time/success_count:.2f}s" if success_count > 0 else "")

# 保存汇总
summary = {
    "timestamp": datetime.now().isoformat(),
    "worker": WORKER,
    "total_tasks": len(tasks),
    "successful": success_count,
    "failed": len(tasks) - success_count,
    "total_time_seconds": round(total_time, 2),
    "average_time_seconds": round(total_time / success_count, 2) if success_count > 0 else 0,
    "tasks": [
        {
            "name": name,
            "success": "error" not in result,
            "elapsed": result.get("elapsed_seconds", 0),
            "error": result.get("error")
        }
        for name, result in tasks
    ]
}

summary_file = os.path.join(OUTPUT_DIR, "summary.json")
with open(summary_file, 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"\n汇总已保存：{summary_file}")
print("\n" + "=" * 70)
print("高级测试完成!")
print("=" * 70)
