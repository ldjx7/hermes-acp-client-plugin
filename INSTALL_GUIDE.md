# ✅ 插件安装完成！

---

## 🎉 安装状态

| 项目 | 状态 |
|------|------|
| **插件路径** | `~/.hermes/plugins/acp-client` |
| **版本** | 0.2.1 |
| **工具数量** | 8 个 |
| **Worker 管理器** | ✅ 已安装 |
| **故障转移功能** | ✅ 已启用 |

---

## 🛠️ 可用工具

| 工具 | 功能 | 示例 |
|------|------|------|
| `acp_dispatch` | 派发任务（支持自动 fallback） | `/acp_dispatch --task "写代码"` |
| `acp_progress` | 查询进度 | `/acp_progress --task_id abc123` |
| `acp_result` | 获取结果 | `/acp_result --task_id abc123` |
| `acp_worker_status` | **查询 Worker 状态** | `/acp_worker_status` |
| `acp_cancel` | 取消任务 | `/acp_cancel --task_id abc123` |
| `acp_list` | 列出会话 | `/acp_list` |
| `acp_cleanup` | 清理旧会话 | `/acp_cleanup --max_age_hours 24` |
| `acp_shutdown` | 关闭 Worker | `/acp_shutdown` |

---

## 🚀 快速开始

### 1. 测试 Worker 状态

```
/acp_worker_status
```

**预期输出**:
```json
{
  "total_workers": 4,
  "available": 4,
  "rate_limited": 0,
  "recommended_worker": "gemini",
  "workers": {
    "gemini": {"status": "available", "model": "gemini-2.5-flash", ...},
    "claude": {"status": "available", "model": "claude-sonnet-4", ...},
    ...
  }
}
```

### 2. 派发第一个任务

```
/acp_dispatch --task "用 Python 写一个 hello world 函数"
```

**预期输出**:
```json
{
  "sessionId": "abc-123-xyz",
  "status": "dispatched",
  "worker": "gemini",
  "attempt": 1
}
```

### 3. 查询进度

```
/acp_progress --task_id abc-123-xyz
```

### 4. 获取结果

```
/acp_result --task_id abc-123-xyz
```

---

## 🔄 自动故障转移测试

### 模拟速率限制

```python
# 在 Hermes 中运行
from acp.worker_manager import get_worker_manager

manager = get_worker_manager()
manager.mark_error("gemini", "Rate limit exceeded", is_rate_limit=True)

# 现在派发任务会自动使用 Claude
/acp_dispatch --task "测试任务"
```

### 验证自动切换

```
# 第一次：Gemini 速率限制
/acp_dispatch --task "任务 1"
# 输出：worker: "claude" (自动切换)

# 60 秒后：Gemini 恢复
/acp_worker_status
# 输出：gemini.status: "available"
```

---

## 📊 配置说明

### 允许的命令（无需确认）

已在 `~/.hermes/config.yaml` 中配置：

```yaml
command_allowlist:
  - "gemini *"      # Gemini CLI
  - "qwen *"        # Qwen CLI
  - "claude *"      # Claude CLI
  - "codex *"       # Codex CLI
  - "git *"         # Git 操作
  - "python3 *"     # Python 脚本
  - "rm *"          # 删除文件
  - "cp *"          # 复制文件
  - "mv *"          # 移动文件
  - ... (共 20+ 命令)
```

### Worker 优先级

```python
# acp/worker_manager.py
self._fallback_order = ["gemini", "claude", "codex", "qwen"]
```

**修改优先级**：编辑文件并重启 Hermes

---

## 🔧 常见问题

### Q1: 工具不识别？

**解决**: 重启 Hermes

```bash
# 退出并重新启动
exit
hermes
```

### Q2: Gemini 认证失败？

**解决**: 重新登录

```bash
gemini login
```

### Q3: 仍然弹出确认窗口？

**检查配置**:

```bash
cat ~/.hermes/config.yaml | grep -A 20 "approvals:"
```

确保 `mode: auto` 且命令在 `command_allowlist` 中

### Q4: 如何禁用故障转移？

```
/acp_dispatch --task "xxx" --worker gemini --auto_fallback false
```

---

## 📁 重要文件位置

| 文件 | 路径 |
|------|------|
| **插件配置** | `~/.hermes/plugins/acp-client/plugin.yaml` |
| **Worker 管理器** | `~/.hermes/plugins/acp-client/acp/worker_manager.py` |
| **工具定义** | `~/.hermes/plugins/acp-client/tools.py` |
| **Hermes 配置** | `~/.hermes/config.yaml` |
| **使用文档** | `~/.hermes/plugins/acp-client/docs/` |

---

## 📚 完整文档

- [故障转移指南](~/.hermes/plugins/acp-client/docs/WORKER_FAILOVER.md)
- [Worker 对比](~/.hermes/plugins/acp-client/docs/WORKER_COMPARISON.md)
- [错误处理](~/.hermes/plugins/acp-client/docs/ACP_ERROR_HANDLING.md)
- [GitHub 仓库](https://github.com/ldjx7/hermes-acp-client-plugin)

---

## ✅ 验证清单

- [x] 插件文件已复制
- [x] plugin.yaml 版本正确 (0.2.1)
- [x] worker_manager.py 已安装
- [x] 命令白名单已配置
- [x] 8 个工具已注册

**下一步**: 在 Hermes 中运行 `/acp_worker_status` 测试！

---

**安装时间**: 2026-04-14  
**插件版本**: 0.2.1  
**状态**: ✅ 就绪
