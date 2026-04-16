#!/usr/bin/env python3
"""
Test Heartbeat Monitor for ACP Transport
"""

import sys
import os
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from acp.heartbeat_monitor import heartbeat_monitor, HeartbeatMonitor

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')


def test_basic():
    """基本心跳测试"""
    print("\n测试 1: 基本心跳功能")
    
    monitor = HeartbeatMonitor(
        first_response_timeout=5.0,
        heartbeat_timeout=10.0,
        max_total_time=30.0
    )
    
    timeout_called = False
    progress_count = [0]
    
    def on_timeout(reason):
        nonlocal timeout_called
        timeout_called = True
        print(f"  Timeout: {reason}")
    
    def on_progress(request_id, progress, message):
        progress_count[0] += 1
        print(f"  Progress: {progress*100:.0f}% - {message}")
    
    monitor.start()
    time.sleep(0.1)
    
    monitor.register_request("test-1", "session-1", on_timeout, on_progress)
    
    # 模拟心跳
    monitor.heartbeat("test-1", "running", 0.0, "Starting...")
    monitor.heartbeat("test-1", "running", 0.5, "Processing...")
    monitor.heartbeat("test-1", "completed", 1.0, "Done!")
    
    time.sleep(0.5)
    monitor.stop()
    
    assert not timeout_called, "不应该超时"
    assert progress_count[0] >= 2, f"应该有进度更新"
    print("  ✅ 通过")
    return True


def test_timeout():
    """心跳超时测试"""
    print("\n测试 2: 心跳超时检测")
    
    monitor = HeartbeatMonitor(
        first_response_timeout=5.0,
        heartbeat_timeout=2.0,
        max_total_time=30.0
    )
    
    timeout_reason = [None]
    
    def on_timeout(reason):
        timeout_reason[0] = reason
        print(f"  Timeout: {reason}")
    
    monitor.start()
    time.sleep(0.1)
    
    monitor.register_request("test-2", "session-2", on_timeout, None)
    monitor.heartbeat("test-2", "running", 0.0, "Starting...")
    
    # 等待超时
    print("  等待超时...")
    for i in range(5):
        time.sleep(1)
        if timeout_reason[0]:
            break
    
    monitor.stop()
    
    assert timeout_reason[0] is not None, "应该超时"
    print("  ✅ 通过")
    return True


def test_status():
    """状态查询测试"""
    print("\n测试 3: 状态查询")
    
    monitor = HeartbeatMonitor()
    monitor.start()
    time.sleep(0.1)
    
    monitor.register_request("test-3", "session-3", lambda r: None, None)
    monitor.heartbeat("test-3", "running", 0.5, "Processing...")
    
    status = monitor.get_status("test-3")
    print(f"  状态：state={status['current_state']}, progress={status['last_progress']}")
    
    assert status['current_state'] == "running"
    assert status['last_progress'] == 0.5
    
    monitor.heartbeat("test-3", "completed", 1.0, "Done")
    monitor.stop()
    
    print("  ✅ 通过")
    return True


if __name__ == "__main__":
    print("="*50)
    print("ACP Heartbeat Monitor 测试")
    print("="*50)
    
    tests = [
        test_basic,
        test_timeout,
        test_status,
    ]
    
    passed = failed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  ❌ 失败：{e}")
            failed += 1
    
    print(f"\n结果：{passed} 通过，{failed} 失败")
    sys.exit(0 if failed == 0 else 1)
