#!/usr/bin/env python3
"""测试 Claude 复杂任务"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import acp_dispatch, acp_result
import json
import time

task = """
请实现一个完整的 Python 日志分析工具，包含：

1. LogAnalyzer 类，支持：
   - 读取日志文件
   - 按级别过滤（DEBUG, INFO, WARNING, ERROR）
   - 按时间范围过滤
   - 搜索关键词
   - 统计信息（各级别日志数量）

2. 完整的文档字符串和类型注解

3. 单元测试示例

4. 使用示例

请用中文注释，代码要简洁高效。
"""

print('='*70)
print('测试：Claude - 复杂任务（实现日志分析工具）')
print('='*70)

# 发送任务
print('\n[1] 发送任务...')
start = time.time()
dispatch_result = acp_dispatch(task, worker='claude-cli', timeout=600)
dispatch_data = json.loads(dispatch_result)
session_id = dispatch_data.get('sessionId')
print(f'SessionID: {session_id}')

# 等待并显示进度
print('\n[2] 等待 Claude 处理（最多 3 分钟）...')
elapsed = 0
while elapsed < 180:
    time.sleep(10)
    elapsed += 10
    
    result = acp_result(session_id, wait=False)
    result_data = json.loads(result)
    
    progress = result_data.get('progress', 0)
    message = result_data.get('progress_message', '')
    status = result_data.get('status')
    
    if progress or message or status == 'completed':
        print(f'[{elapsed:3d}s] {progress*100:5.1f}% - {message[:60] if message else "处理中..."}')
    
    if result_data.get('result') or result_data.get('error'):
        break

# 获取结果
print('\n[3] 获取最终结果...')
final_result = acp_result(session_id, wait=False)
final_data = json.loads(final_result)

result_text = final_data.get('result', '')
if result_text:
    lines = result_text.split('\n')
    print(f'\n✅ 完成！结果：{len(lines)} 行，{len(result_text)} 字符')
    print(f'\n📝 代码预览（前 50 行）:\n{"="*60}')
    for i, line in enumerate(lines[:50]):
        print(f'{i+1:3d} | {line}')
    if len(lines) > 50:
        print(f'... 还有 {len(lines)-50} 行')
else:
    error = final_data.get('error')
    print(f'\n❌ 错误：{error}')

total_time = time.time() - start
print(f'\n⏱️  总耗时：{total_time:.1f}秒')
