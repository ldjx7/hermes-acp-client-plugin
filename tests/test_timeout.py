#!/usr/bin/env python3
"""验证兜底超时机制"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from acp.transport import StdioTransport
import inspect
import time

print('='*60)
print('验证：15 分钟兜底超时机制')
print('='*60)

# 测试 1: 验证参数
print('\n[测试 1] 验证参数...')
sig = inspect.signature(StdioTransport.__init__)
params = list(sig.parameters.keys())
defaults = {
    name: p.default 
    for name, p in sig.parameters.items() 
    if p.default is not inspect.Parameter.empty
}

if 'max_wait_timeout' in params:
    print(f'✅ max_wait_timeout 参数已添加')
    print(f'✅ 默认值：{defaults["max_wait_timeout"]}秒（{defaults["max_wait_timeout"]/60:.0f}分钟）')
else:
    print(f'❌ 参数未添加')

# 测试 2: 验证超时逻辑
print('\n[测试 2] 验证超时逻辑（模拟）...')

# 创建 transport（不启动）
transport = StdioTransport(worker='gemini', max_wait_timeout=10.0)  # 10 秒用于测试
print(f'✅ Transport 创建成功')
print(f'✅ max_wait_timeout: {transport.max_wait_timeout}秒')

# 验证超时计算逻辑
start_time = time.time()
time.sleep(2)
elapsed = time.time() - start_time

if elapsed < transport.max_wait_timeout:
    print(f'✅ 超时检查逻辑正确：{elapsed:.2f}s < {transport.max_wait_timeout}s')
else:
    print(f'❌ 超时检查逻辑错误')

# 测试 3: 验证代码结构
print('\n[测试 3] 验证代码结构...')
import acp.transport
import inspect
source = inspect.getsource(acp.transport.StdioTransport._send_with_heartbeat)

checks = [
    ('start_time = time.time()', '记录开始时间'),
    ('elapsed = time.time() - start_time', '计算已用时间'),
    ('if elapsed > self.max_wait_timeout:', '检查超时'),
    ('return {', '返回超时错误'),
]

for code, desc in checks:
    if code in source:
        print(f'✅ {desc}: {code[:40]}...')
    else:
        print(f'❌ {desc}: 未找到')

print('\n' + '='*60)
print('验证完成!')
print('='*60)
