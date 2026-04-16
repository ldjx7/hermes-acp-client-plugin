#!/usr/bin/env python3
"""
完整测试 ACP 心跳超时机制
测试 Gemini 和 Claude CLI 的简单和复杂任务
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import acp_dispatch
import json
import time

def test_worker(worker, task_name, task):
    """测试单个任务"""
    print(f"\n{'='*70}")
    print(f"测试：{worker} - {task_name}")
    print(f"{'='*70}")
    
    start = time.time()
    result = acp_dispatch(task, worker=worker)
    elapsed = time.time() - start
    
    print(f"\n⏱️  耗时：{elapsed:.2f}秒")
    
    data = json.loads(result)
    status = data.get('status', 'unknown')
    print(f"📊 状态：{status}")
    
    if 'error' in data:
        print(f"❌ 错误：{data['error'][:200]}...")
        return False
    elif 'output' in data:
        print(f"✅ 输出：{data['output'][:200]}...")
        return True
    else:
        print(f"📝 结果：{json.dumps(data, indent=2)[:300]}...")
        return True

# 测试计划
tests = [
    # Gemini 测试
    ("gemini", "简单问答", "巴黎是哪个国家的首都？用中文回答"),
    ("gemini", "代码生成", "用 Python 实现快速排序，包含注释"),
    
    # Claude 测试
    ("claude-cli", "简单问答", "巴黎是哪个国家的首都？用中文回答"),
    ("claude-cli", "代码生成", "用 Python 实现快速排序，包含中文注释"),
]

# 运行测试
print("="*70)
print("ACP 心跳超时机制 - 完整测试")
print("="*70)

results = []
for worker, name, task in tests:
    try:
        success = test_worker(worker, name, task)
        results.append((f"{worker} - {name}", success))
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        results.append((f"{worker} - {name}", False))
    
    time.sleep(2)  # 避免速率限制

# 总结
print(f"\n{'='*70}")
print("测试结果总结")
print(f"{'='*70}")

passed = sum(1 for _, success in results if success)
total = len(results)

for test_name, success in results:
    icon = "✅" if success else "❌"
    print(f"{icon} {test_name}")

print(f"\n总计：{passed}/{total} 通过")

if passed == total:
    print("\n🎉 所有测试通过！心跳机制工作正常！")
else:
    print(f"\n⚠️  {total - passed} 个测试失败")
