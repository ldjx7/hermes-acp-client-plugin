#!/usr/bin/env python3
"""让 Claude 分析项目并生成优化报告 v3.0"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import acp_dispatch, acp_result
import json
import time

task = """请分析 ACP Client 插件项目，生成优化报告 v3.0。

核心文件：
- acp/heartbeat_monitor.py - 心跳监控器（简化版，230 行）
- acp/transport.py - ACP 传输层  
- tools.py - acp_dispatch 入口
- tools/claude-cli-acp.js - Claude CLI 适配器

已完成：
1. 心跳机制（简化版）- 只进度反馈，不超时判断
2. Worker 修复 - Gemini 和 Claude 都正常工作

请生成优化报告，包含：
1. 架构分析
2. 已实现审查
3. 优化建议（高/中/低优先级）
4. 与之前报告的差异

Markdown 格式，中文。
"""

print('='*70)
print('任务：Claude 分析 ACP Client 插件 - 优化报告 v3.0')
print('='*70)

print('\n发送分析任务...')
start = time.time()
result = acp_dispatch(task, worker='claude-cli')
session_id = json.loads(result).get('sessionId')
print(f'Session: {session_id}')

print('\n等待完成（最多 8 分钟）...')
for i in range(32):  # 8 分钟
    time.sleep(15)
    
    r = json.loads(acp_result(session_id, wait=False))
    
    if r.get('result'):
        elapsed = time.time() - start
        print(f'\n✅ 完成！耗时：{elapsed:.0f}秒，{len(r["result"])} 字符')
        
        with open('docs/OPTIMIZATION_REPORT_V3.md', 'w', encoding='utf-8') as f:
            f.write(r['result'])
        print('已保存到 docs/OPTIMIZATION_REPORT_V3.md')
        
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
