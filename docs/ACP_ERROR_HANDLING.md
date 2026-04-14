# ACP 错误处理改进

## 问题发现

通过 `test_acp_debug.py` 诊断工具，发现 Qwen ACP 的错误处理问题：

### 1. 错误在 stderr 中返回

Qwen ACP 在遇到错误时，会在 stderr 输出 JSON 格式的错误信息：

```
Error handling request {
  jsonrpc: '2.0',
  id: 'prompt_2',
  method: 'session/prompt',
  params: {...}
} {
  code: -32603,
  message: 'Internal error',
  data: [...]
}
```

### 2. prompt 格式要求

Qwen 期望 `prompt` 参数是数组格式：
```json
{
  "prompt": [
    {"type": "text", "text": "Hello"}
  ]
}
```

而不是字符串：
```json
{
  "prompt": "Hello"  // ❌ 错误
}
```

---

## 解决方案

### 1. stderr JSON 错误解析

在 `transport.py` 中增强 `_read_errors()` 方法：

```python
def _read_errors(self):
    """Read stderr and parse JSON errors."""
    error_buffer = ""
    for line in self.process.stderr:
        error_line = line.strip()
        
        # Buffer and parse JSON errors
        error_buffer += error_line
        if error_buffer.endswith('}'):
            try:
                error_data = json.loads(error_buffer)
                if "error" in error_data or "code" in error_data:
                    self._last_stderr_error = error_data
                error_buffer = ""
            except json.JSONDecodeError:
                pass
```

### 2. 错误返回

在 `send()` 方法中检查 stderr 错误：

```python
def send(self, message, timeout):
    try:
        return self._send_with_retry(...)
    except RequestTimeoutError:
        # Check stderr for errors
        if self._last_stderr_error:
            return {"error": self._last_stderr_error}
        raise
```

---

## 诊断工具

创建 `test_acp_debug.py` 实时监控：

- ✅ stdout 响应
- ✅ stderr 错误
- ✅ 通知消息
- ✅ 流式内容

输出示例：
```
✅ 响应：init_1 - {...}
📢 通知：session/update - agent_message_chunk
   内容：Hello! How can I help you?
❌ 错误：{"code": -32603, "message": "Internal error"}
⚠️  STDERR: Error handling request {...}
```

---

## 错误类型

| 错误码 | 说明 | 原因 |
|--------|------|------|
| -32603 | Internal error | 服务器内部错误 |
| -32600 | Invalid Request | JSON-RPC 格式错误 |
| -32601 | Method not found | 方法不存在 |
| -32602 | Invalid params | 参数格式错误 |

---

## 最佳实践

### 1. 始终使用正确的 prompt 格式

```python
# ✅ 正确
PromptRequest.create(session_id, "Hello")
# 内部转换为：[{"type": "text", "text": "Hello"}]

# ❌ 错误
{"prompt": "Hello"}  # 字符串格式
```

### 2. 捕获并记录错误

```python
try:
    resp = transport.send(prompt_req, timeout=60)
    if resp and "error" in resp:
        logger.error(f"ACP Error: {resp['error']}")
except TransportError as e:
    logger.error(f"Transport error: {e}")
```

### 3. 使用诊断工具调试

```bash
python3 tests/test_acp_debug.py
```

---

## 文件修改

| 文件 | 修改内容 |
|------|---------|
| `acp/transport.py` | 增强 `_read_errors()` 解析 JSON 错误 |
| `acp/transport.py` | 添加 `_last_stderr_error` 跟踪 |
| `acp/transport.py` | `send()` 检查 stderr 错误 |
| `tests/test_acp_debug.py` | 新增诊断工具 |

---

## 下一步

1. ✅ 实现 stderr JSON 错误解析
2. ✅ 添加错误跟踪变量
3. ✅ 在 send() 中检查错误
4. ⏳ 添加错误重试策略（针对特定错误类型）
5. ⏳ 实现错误分类和处理建议

---

*文档生成：2026-04-14*  
*插件版本：0.2.2*
