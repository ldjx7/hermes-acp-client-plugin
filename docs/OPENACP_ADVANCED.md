# OpenACP 高级配置

## 连接外部 OpenACP 实例

默认情况下，Hermes 会自动启动本地 OpenACP daemon。如果您已有独立的 OpenACP 实例或希望部署在远程服务器上：

### 方式 1: 环境变量

```bash
export OPENACP_DAEMON_URL=http://localhost:8080
```

### 方式 2: 配置文件

在 `~/.hermes/config.yaml` 中添加：

```yaml
acp:
  openacp:
    daemon_url: http://localhost:8080
```

### 方式 3: 代码指定

```python
from acp.openacp_bridge import OpenACPBridge

bridge = OpenACPBridge(base_url="http://localhost:8080")
result = bridge.dispatch("gemini", "写代码")
```

## 管理 OpenACP Daemon

### 手动启动

```bash
# 后台运行
openacp start --daemon

# 前台运行（调试用）
openacp --foreground

# 查看状态
openacp status

# 查看日志
openacp logs

# 停止
openacp stop
```

### 自动启动配置

Hermes 默认会自动启动 daemon，如需禁用：

```python
# 在代码中指定已运行的 daemon
from acp.openacp_bridge import OpenACPBridge

bridge = OpenACPBridge(base_url="http://localhost:3000")
# 不会自动启动，直接连接指定 URL
```

## 安装 Agent

### 查看可用 Agent

```bash
openacp agents
```

### 安装单个 Agent

```bash
openacp agents install gemini
openacp agents install claude
openacp agents install codex
```

### 批量安装

```bash
for agent in gemini claude codex qwen; do
    openacp agents install $agent
done
```

### 查看已安装 Agent

```bash
openacp agents --json
```

## 性能调优

### 调整超时时间

```python
acp_dispatch({
    "task": "复杂任务",
    "worker": "openacp:gemini",
    "timeout": 600  # 10 分钟
})
```

### 并发控制

OpenACP 支持并发请求，但建议限制同时进行的任务数：

```python
# 推荐：最多 3-5 个并发任务
import asyncio

semaphore = asyncio.Semaphore(3)

async def dispatch_task(task):
    async with semaphore:
        return await acp_dispatch_async(task)
```

## 监控和日志

### 启用详细日志

```python
import logging
logging.getLogger("acp.openacp_bridge").setLevel(logging.DEBUG)
```

### 查看 OpenACP 日志

```bash
# 实时查看
openacp logs -f

# 查看最后 100 行
openacp logs --lines 100
```

## 远端部署

### Docker 部署

```bash
docker run -d \
  --name openacp \
  -p 3000:3000 \
  -v ~/.openacp:/root/.openacp \
  ghcr.io/open-acp/openacp:latest
```

### 配置 Hermes 连接远端

```bash
export OPENACP_DAEMON_URL=http://your-server:3000
```

## 安全配置

### API 认证

如果 OpenACP 配置了 API 密钥：

```python
from acp.openacp_bridge import OpenACPBridge

bridge = OpenACPBridge(base_url="http://localhost:3000")
bridge.session.headers["Authorization"] = "Bearer YOUR_API_KEY"
```

### HTTPS 配置

```bash
# OpenACP 端配置 HTTPS
openacp config set server.https true
openacp config set server.cert /path/to/cert.pem
openacp config set server.key /path/to/key.pem
```

```python
# Hermes 端
export OPENACP_DAEMON_URL=https://your-server:3443
```

## 故障恢复

### 自动重启

配置 systemd 服务自动重启：

```ini
# /etc/systemd/system/openacp.service
[Unit]
Description=OpenACP Daemon
After=network.target

[Service]
Type=simple
User=youruser
ExecStart=/usr/bin/openacp start --daemon
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable openacp
systemctl start openacp
```

## 最佳实践

1. **生产环境**: 使用独立的 OpenACP 实例，不要依赖 Hermes 自动启动
2. **开发环境**: 使用 Hermes 自动启动，开箱即用
3. **监控**: 配置日志和告警
4. **备份**: 定期备份 `~/.openacp/` 配置目录
5. **更新**: 定期运行 `openacp update` 更新 OpenACP

## 相关文档

- [快速开始](./OPENACP_QUICKSTART.md)
- [支持的 Agent](./OPENACP_AGENTS.md)
- [故障排除](./OPENACP_TROUBLESHOOTING.md)
