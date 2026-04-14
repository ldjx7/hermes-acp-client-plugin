# Hermes ACP Client Plugin - Phase 1 开发报告

## 完成日期
2026-04-13

## 执行摘要

Phase 1 基础框架开发已完成。Gemini CLI 成功创建了插件的核心文件结构，包括：
- 插件清单 (plugin.yaml)
- 工具注册 (__init__.py)
- Schema 定义 (schemas.py)
- 工具 Handler (tools.py)
- StdioTransport 实现 (acp/transport.py)

所有文件已安装到 `~/.hermes/plugins/acp-client/`。

---

## 已创建文件

### 1. plugin.yaml
**位置**: `~/.hermes/plugins/acp-client/plugin.yaml`

```yaml
name: acp-client
version: 0.1.0
description: ACP client for dispatching tasks to Gemini CLI worker
provides_tools: [acp_dispatch, acp_progress, acp_result]
requires_env:
  - name: GOOGLE_API_KEY
    description: Google API key for Gemini CLI
    url: https://aistudio.google.com/app/apikey
    secret: true
```

**状态**: ✅ 完成

---

### 2. __init__.py
**位置**: `~/.hermes/plugins/acp-client/__init__.py`

**功能**: 
- 实现 `register(ctx)` 函数
- 注册 3 个工具到 Hermes
- 包含 toolset 和 description

**状态**: ✅ 完成

---

### 3. schemas.py
**位置**: `~/.hermes/plugins/acp-client/schemas.py`

**定义**:
- `ACP_DISPATCH_SCHEMA` - acp_dispatch 工具参数
- `ACP_PROGRESS_SCHEMA` - acp_progress 工具参数
- `ACP_RESULT_SCHEMA` - acp_result 工具参数

**状态**: ✅ 完成

---

### 4. tools.py
**位置**: `~/.hermes/plugins/acp-client/tools.py`

**实现**:
- `acp_dispatch(task, context)` - 派发任务
- `acp_progress(task_id)` - 查询进度
- `acp_result(task_id)` - 获取结果
- 使用 StdioTransport 进行通信

**状态**: ✅ 完成（需完善 ACP 协议）

---

### 5. acp/transport.py
**位置**: `~/.hermes/plugins/acp-client/acp/transport.py`

**实现**:
- `StdioTransport` 类
- `start()` - 启动 gemini --acp-server 子进程
- `send_request()` - 发送 JSON-RPC 请求
- `stop()` - 停止子进程
- 错误日志线程

**状态**: ✅ 完成（需测试 Gemini CLI 兼容性）

---

### 6. acp/__init__.py
**位置**: `~/.hermes/plugins/acp-client/acp/__init__.py`

**功能**: 导出 StdioTransport 类

**状态**: ✅ 完成

---

## 文件验证

```
✓ acp module imported successfully
✓ schemas module imported successfully
✓ tools module imported successfully
```

所有 Python 模块可正常导入。

---

## 待完成事项

### 高优先级

1. **ACP 协议消息格式**
   - 实现 InitializeRequest/Response
   - 实现 NewSessionRequest/Response
   - 实现 PromptRequest/Response
   - 实现 SessionNotification

2. **Gemini CLI ACP 服务器测试**
   - 验证 `gemini --acp-server` 命令
   - 测试 JSON-RPC 2.0 通信
   - 处理错误和超时

3. **会话状态管理**
   - SessionState 类
   - 会话 ID 追踪
   - 请求 - 响应映射

### 中优先级

4. **错误处理**
   - 子进程崩溃恢复
   - 超时处理
   - 重试机制

5. **异步支持**
   - 后台进度监听
   - 事件队列
   - 回调机制

---

## Phase 2 计划

### 目标：进度监听

1. 实现 ACP SessionNotification 处理
2. 添加进度更新回调
3. 实现 acp_progress 工具的完整逻辑
4. 测试进度流

---

## 安装说明

### 前置要求

1. 安装 Gemini CLI:
   ```bash
   npm install -g @anthropic-ai/gemini-cli
   ```

2. 设置 API Key:
   ```bash
   export GOOGLE_API_KEY="your-api-key"
   ```

### 安装插件

插件已安装到 `~/.hermes/plugins/acp-client/`

### 验证安装

```bash
hermes plugins list
# 应该显示 acp-client
```

### 运行冒烟测试

```bash
cd /root/vibecoding/hermes-acp-client-plugin
python3 tests/test_smoke.py
```

---

## 技术决策

### 为什么选择 StdioTransport？

1. **简单** - 直接管理子进程，无需网络配置
2. **安全** - 本地通信，无网络暴露
3. **高效** - 低延迟，直接管道通信
4. **兼容** - Gemini CLI 支持 stdio 模式

### 为什么使用单例 Transport？

```python
_transport = None

def get_transport():
    global _transport
    if _transport is None:
        _transport = StdioTransport()
        _transport.start()
    return _transport
```

**原因**:
- 避免重复启动子进程
- 共享会话状态
- 减少资源消耗

---

## 风险与挑战

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Gemini CLI ACP 协议不兼容 | 高 | 提前测试协议格式 |
| 子进程管理复杂 | 中 | 实现健康检查 |
| 异步事件处理 | 中 | 使用事件队列 |
| API Key 安全 | 高 | 使用 Hermes requires_env |

---

## 下一步行动

1. **测试 Gemini CLI ACP 模式**
   ```bash
   gemini --acp-server --help
   ```

2. **实现 ACP 协议消息**
   - 参考 Hermes acp_adapter/server.py
   - 实现 Initialize 握手

3. **运行端到端测试**
   - 创建测试会话
   - 发送测试任务
   - 验证响应

---

*报告生成：2026-04-13*
*开发者：Gemini CLI (Autonomous Engineering Agent)*
