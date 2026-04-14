# Gemini CLI 可用模型

---

## 📊 已知模型列表

### 从测试结果确认

| 模型 | 状态 | 来源 |
|------|------|------|
| **gemini-2.5-flash** | ✅ 已测试 | Worker 管理器默认配置 |
| **gemini-3-flash-preview** | ✅ 已测试 | ACP 响应中提取 |

---

## 🔍 查询方法

### 方法 1: 使用 Gemini CLI

```bash
# 交互式查询（需要认证）
gemini models

# 或指定模型运行
gemini --model gemini-2.5-flash
```

### 方法 2: 使用 API

```bash
# 设置 API Key
export GEMINI_API_KEY="your-api-key"

# 查询所有模型
curl "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY"

# 查询特定模型
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash?key=$GEMINI_API_KEY"
```

### 方法 3: 从 ACP 响应中提取

```python
# 运行任务后从响应中查看实际使用的模型
from acp.worker_manager import get_worker_manager

manager = get_worker_manager()
info = manager.get_worker_info("gemini")
print(f"当前模型：{info['model']}")
```

---

## 📋 Google 官方模型（参考）

### Gemini 2.0 系列

| 模型 | 说明 | 适用场景 |
|------|------|----------|
| `gemini-2.0-flash` | 快速、高效 | 简单任务、快速响应 |
| `gemini-2.0-flash-lite` | 轻量级 | 资源受限场景 |
| `gemini-2.0-pro` | 高性能 | 复杂推理、代码生成 |

### Gemini 1.5 系列

| 模型 | 说明 | 适用场景 |
|------|------|----------|
| `gemini-1.5-flash` | 平衡性能和速度 | 通用任务 |
| `gemini-1.5-pro` | 最强性能 | 复杂任务、长上下文 |

---

## 🔧 在 ACP 中使用

### 指定模型（如果 Gemini CLI 支持）

```bash
# 启动时指定模型
gemini --acp --model gemini-2.5-flash
```

### 在 Worker 管理器中配置

编辑 `acp/worker_manager.py`:

```python
# 初始化时注册模型
manager.register_worker("gemini", "gemini-2.5-flash")
# 或
manager.register_worker("gemini", "gemini-1.5-pro")
```

---

## 📊 性能对比（从测试结果）

| 模型 | 平均响应时间 | 成功率 | 测试任务数 |
|------|-------------|--------|-----------|
| gemini-3-flash-preview | 28.78s | 100% | 5 |

---

## 💡 推荐配置

### 默认配置（推荐）

```python
# acp/worker_manager.py
manager.register_worker("gemini", "gemini-2.5-flash")
```

### 长上下文任务

```python
manager.register_worker("gemini", "gemini-1.5-pro")
```

### 快速响应

```python
manager.register_worker("gemini", "gemini-2.0-flash")
```

---

## 🔗 参考链接

- [Gemini 模型文档](https://ai.google.dev/gemini-api/docs/models/gemini)
- [Gemini CLI GitHub](https://github.com/google-gemini/gemini-cli)
- [Google AI Studio](https://aistudio.google.com/app/apikey)

---

**最后更新**: 2026-04-14  
**来源**: 实际测试结果 + Google 官方文档
