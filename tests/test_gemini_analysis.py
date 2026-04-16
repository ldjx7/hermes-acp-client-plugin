#!/usr/bin/env python3
"""让 Gemini 分析项目并生成独立优化报告"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import acp_dispatch, acp_result
import json
import time

task = """请分析 ACP Client 插件项目，生成独立的优化报告。

核心文件：
- acp/heartbeat_monitor.py (239 行) - 心跳监控器（简化版）
- acp/transport.py (769 行) - ACP 传输层
- tools.py (520 行) - acp_dispatch 入口
- tools/claude-cli-acp.js (349 行) - Claude CLI 适配器
- acp/session_manager.py (133 行)
- acp/worker_manager.py (355 行)
- acp/openacp_bridge.py (452 行)

已完成功能：
1. 心跳机制简化 - 只进度反馈，不超时判断
2. Worker 修复 - Gemini 和 Claude 都正常工作

请从你的视角分析：
1. 架构设计优点和不足
2. 代码质量问题
3. 性能瓶颈
4. 优化建议（按优先级）
5. 你最关注的重点问题

请独立分析，不要参考之前的报告。Markdown 格式，中文。
"""

print('='*70)
print('任务：Gemini 分析 ACP Client 插件 - 独立优化报告')
print('='*70)

print('\n发送分析任务...')
start = time.time()
result = acp_dispatch(task, worker='gemini')
session_id = json.loads(result).get('sessionId')
print(f'Session: {session_id}')

print('\n等待完成（最多 5 分钟）...')
for i in range(20):
    time.sleep(15)
    
    r = json.loads(acp_result(session_id, wait=False))
    
    if r.get('result'):
        elapsed = time.time() - start
        print(f'\n✅ Gemini 完成！耗时：{elapsed:.0f}秒，{len(r["result"])} 字符')
        
        with open('docs/OPTIMIZATION_REPORT_GEMINI.md', 'w', encoding='utf-8') as f:
            f.write(r['result'])
        print('已保存到 docs/OPTIMIZATION_REPORT_GEMINI.md')
        
        print('\n摘要（前 60 行）:')
        print('='*70)
        for j, line in enumerate(r['result'].split('\n')[:60]):
            print(f'{j+1:3d} | {line}')
        break
    elif r.get('error'):
        print(f'\n❌ 错误：{r.get("error")}')
        break
    else:
        p = r.get('progress', 0)
        m = r.get('progress_message', '')
        if p or m:
            print(f'[{(i+1)*15:3d}s] {p*100:5.1f}% - {m[:60] if m else "分析中..."}')
else:
    print('\n⏱️ 等待超时')
