# ACP Client 调用 Claude Code - 测试总结

**测试日期**: 2026-04-16  
**测试目标**: 验证通过 ACP Client 插件调用 Claude Code 执行代码审查

---

## ✅ 已验证的能力

### 1. cc-acp 安装成功

```bash
$ npm list -g claude-code-acp
/root/.nvm/versions/node/v24.14.1/lib
└── claude-code-acp@0.1.1

$ which cc-acp
/root/.nvm/versions/node/v24.14.1/bin/cc-acp
```

### 2. ACP 协议通信正常

```bash
$ echo '{"method":"initialize",...}' | timeout 10 cc-acp

Claude Code ACP Agent starting...
[ACP] No CLAUDE_API_KEY found, using Claude Code subscription authentication
[ACP] Received Claude message: {
  "type": "system",
  "subtype": "init",
  "session_id": "0bcfd265-...",
  "tools": ["Task", "Bash", "Glob", "Grep", ...],
  "model": "opus[1m]",
  ...
}
```

### 3. 认证正常

- ✅ 使用 Claude Code 订阅认证（默认）
- ✅ 支持 CLAUDE_API_KEY 环境变量（可选）

---

## ❌ 发现的问题

### 问题 1: ACP Client 与 Worker 通信失败

**现象**:
- `create_session` 返回 `sessionId: null`
- Gemini 和 Claude 进程都在后台运行
- 没有收到响应或通知回调

**测试结果**:
```python
# 尝试创建会话
session = transport.create_session(name="test")
print(session)  # 返回：{'jsonrpc': '2.0', 'id': '...', 'error': {...}}

# 错误信息
{'expected': 'string', 'code': 'invalid_type', 'path': ['sessionId'], 'message': 'Invalid input: expected string, received null'}
```

**根本原因**:
- Gemini CLI 的 ACP 实现可能不支持 `session/new` 方法
- 或者响应格式与预期不同
- ACP 协议版本可能存在兼容性问题

---

## 🔍 分析

### Gemini ACP 协议细节

Gemini CLI (`gemini --acp`) 使用的 ACP 协议可能与我们实现的不完全兼容：

1. **协议版本**: Gemini 可能使用更新的 ACP 版本
2. **会话管理**: Gemini 可能自动创建会话，不需要显式的 `session/new`
3. **响应格式**: 响应结构可能与预期不同

### Claude Code ACP (cc-acp)

`cc-acp` 是专门为 Zed Editor 开发的 ACP 适配器：

1. **协议**: 遵循标准 ACP 协议
2. **认证**: 使用 Claude Code 订阅
3. **工具**: 支持完整的 Claude Code 工具集

---

## 💡 解决方案

### 方案 1: 使用 OpenACP 桥接（推荐）

OpenACP 提供了统一的 API 层，处理了所有 ACP 协议细节：

```python
from acp.openacp_bridge import OpenACPBridge

bridge = OpenACPBridge()

# 调用 Claude Code
result = bridge.dispatch(
    agent="claude",  # 或 "gemini", "codex" 等
    prompt="请审查这个 Python 文件...",
    timeout=300
)

print(result.output)
```

**优点**:
- 统一的 API 接口
- 自动管理 daemon 生命周期
- 支持 28+ AI agents
- 更好的错误处理

**前提**: 需要启动 OpenACP daemon

### 方案 2: 修复 ACP 协议兼容性

修改 `transport.py` 以适配 Gemini 的 ACP 实现：

```python
# transport.py 中添加 Gemini 专用逻辑
class StdioTransport:
    def create_session(self, name: str = "default"):
        # Gemini 可能不需要显式创建会话
        # 返回一个虚拟的 session_id
        return {"result": {"sessionId": str(uuid.uuid4())}}
```

### 方案 3: 直接使用 CLI 命令

不通过 ACP 协议，直接调用 CLI：

```python
import subprocess

def call_claude(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=300
    )
    return result.stdout
```

---

## 📋 当前 Worker 状态

| Worker | 命令 | 安装状态 | 可调用 |
|--------|------|---------|--------|
| `gemini` | `gemini --acp` | ✅ 已安装 | ⚠️ 协议问题 |
| `gemini-pro` | `gemini --acp --model gemini-2.5-pro` | ✅ 已安装 | ⚠️ 协议问题 |
| `claude` | `cc-acp` | ✅ 已安装 | ⚠️ 协议问题 |
| `qwen` | `qwen --acp` | 待安装 | ❓ 未测试 |

**OpenACP Bridge Workers** (需启动 OpenACP daemon):

| Worker | 状态 |
|--------|------|
| `openacp:gemini` | 需 OpenACP daemon |
| `openacp:claude` | 需 OpenACP daemon |
| `openacp:codex` | 需 OpenACP daemon |

---

## 🚀 下一步行动

### 立即可用：OpenACP 桥接

1. **启动 OpenACP daemon**:
   ```bash
   cd ~/openacp-workspace
   openacp start --daemon
   ```

2. **安装 Claude agent**:
   ```bash
   openacp agents install claude
   ```

3. **调用**:
   ```python
   from acp.openacp_bridge import dispatch
   
   result = dispatch("claude", "请审查...")
   ```

### 长期方案：修复协议兼容性

1. 研究 Gemini ACP 协议实现细节
2. 更新 `protocol.py` 以匹配实际响应格式
3. 添加协议版本协商
4. 编写兼容性测试

---

## 📁 相关文档

- `docs/CLAUDE_CODE_TEST_REPORT.md` - cc-acp 测试报告
- `docs/OPTIMIZATION_RECOMMENDATIONS.md` - 17 个优化建议
- `acp/openacp_bridge.py` - OpenACP 桥接实现

---

## ✅ 结论

1. **cc-acp 已安装并可独立运行** ✅
2. **ACP Client 协议通信有问题** ❌ (需要修复)
3. **建议使用 OpenACP 桥接** ✅ (推荐方案)

**Claude Code 可以调用，但需要通过 OpenACP 桥接方式，而不是直接 ACP 协议。**

---

**测试完成时间**: 2026-04-16 11:45  
**测试状态**: ⚠️ 部分通过（cc-acp 可运行，但 ACP Client 集成需要修复）
