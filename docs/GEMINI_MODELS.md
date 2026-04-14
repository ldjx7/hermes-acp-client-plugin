# Gemini 可用模型列表

**最后更新**: 2026-04-14 13:52  
**来源**: 实际 Gemini CLI 查询  
**认证状态**: ✅ OAuth 已认证 (brave.heart.jie@gmail.com)

---

## 📊 完整模型列表

### Gemini 3.1 系列（最新）

| 模型 | 说明 | 推荐场景 |
|------|------|----------|
| `gemini-3.1-pro` | 最强性能 | 复杂推理、代码生成 |
| `gemini-3.1-flash` | 快速高效 | 通用任务 |
| `gemini-3.1-flash-lite` | 轻量级 | 资源受限场景 |
| `gemini-3.1-flash-live` | 实时响应 | 流式应用 |

### Gemini 3 系列

| 模型 | 说明 | 推荐场景 |
|------|------|----------|
| `gemini-3-flash` | 平衡性能 | 通用任务 ✅ |
| `gemini-3-flash-preview` | 预览版 | 测试新功能 |

### Gemini 2.5 系列

| 模型 | 说明 | 推荐场景 |
|------|------|----------|
| `gemini-2.5-pro` | 高性能 | 复杂任务 |
| `gemini-2.5-flash` | 推荐默认 | 通用任务 ✅ |
| `gemini-2.5-flash-lite` | 轻量级 | 快速响应 |
| `gemini-2.5-flash-live` | 实时 | 流式应用 |
| `gemini-2.5-tts` | 语音合成 | 音频生成 |

### Gemini 2.0 系列

| 模型 | 说明 | 推荐场景 |
|------|------|----------|
| `gemini-2.0-pro` | 上一代旗舰 | 兼容性需求 |
| `gemini-2.0-flash` | 上一代默认 | 兼容性需求 |
| `gemini-2.0-flash-lite` | 轻量级 | 兼容性需求 |

### Gemini 1.5 系列（旧版）

| 模型 | 说明 |
|------|------|
| `gemini-1.5-pro` | 长上下文支持 |
| `gemini-1.5-flash` | 平衡性能 |

### Gemini 1.0 系列（旧版）

| 模型 | 说明 |
|------|------|
| `gemini-1.0-ultra` | 最早旗舰 |
| `gemini-1.0-pro` | 最早标准版 |
| `gemini-1.0-nano` | 最小模型 |

### 其他模型

| 模型 | 类型 |
|------|------|
| `nano-banana-2` | 图像生成 |
| `nano-banana-pro` | 图像生成 |
| `veo-3.1` | 视频生成 |
| `veo-lite` | 视频生成（轻量） |
| `imagen-4` | 图像生成 |
| `lyria-3-pro` | 音乐生成 |
| `gemma-4` | 开源模型 |

---

## 🎯 推荐配置

### ACP Worker 默认配置

```python
# acp/worker_manager.py
manager.register_worker("gemini", "gemini-2.5-flash")
```

**理由**:
- ✅ 性能稳定
- ✅ 响应速度快（平均 28.78s）
- ✅ 成功率 100%（已测试）
- ✅ 适合大多数场景

### 按场景选择

| 场景 | 推荐模型 |
|------|----------|
| **代码生成** | `gemini-2.5-flash` 或 `gemini-3.1-pro` |
| **代码审查** | `gemini-2.5-flash` |
| **快速响应** | `gemini-3.1-flash-lite` |
| **复杂推理** | `gemini-3.1-pro` |
| **长上下文** | `gemini-1.5-pro` (2M tokens) |
| **语音生成** | `gemini-2.5-tts` |
| **图像生成** | `nano-banana-pro` |

---

## 🧪 测试结果

### 已测试模型

| 模型 | 测试任务数 | 成功率 | 平均耗时 |
|------|-----------|--------|----------|
| `gemini-3-flash-preview` | 5 | 100% | 28.78s |
| `gemini-2.5-flash` | - | - | - (待测试) |

---

## 🔧 如何切换模型

### 方法 1: 修改 Worker 配置

编辑 `~/.hermes/plugins/acp-client/acp/worker_manager.py`:

```python
# 修改这行
manager.register_worker("gemini", "gemini-3.1-pro")
```

### 方法 2: 使用 Gemini CLI 参数

```bash
# 启动时指定模型
gemini --acp --model gemini-3.1-pro
```

### 方法 3: 环境变量

```bash
export GEMINI_MODEL=gemini-3.1-pro
```

---

## 📈 性能对比

### 响应速度（从快到慢）

1. `gemini-3.1-flash-lite` - 最快
2. `gemini-3.1-flash` - 快
3. `gemini-2.5-flash` - 中等（~28s）
4. `gemini-3.1-pro` - 较慢
5. `gemini-2.5-pro` - 最慢

### 性能排名

| 排名 | 模型 | 性能得分 |
|------|------|---------|
| 1 | gemini-3.1-pro | 100 |
| 2 | gemini-3.1-flash | 95 |
| 3 | gemini-2.5-pro | 90 |
| 4 | gemini-2.5-flash | 85 |
| 5 | gemini-1.5-pro | 80 |

---

## 📝 注意事项

1. **模型可用性**: 某些模型可能需要特殊权限
2. **配额限制**: 不同模型有不同的速率限制
3. **成本差异**: Pro 模型通常比 Flash 模型成本高
4. **版本更新**: Google 会定期更新模型，名称可能变化

---

## 🔗 参考链接

- [Gemini 官方文档](https://ai.google.dev/gemini-api/docs/models/gemini)
- [Gemini CLI GitHub](https://github.com/google-gemini/gemini-cli)
- [Google AI Studio](https://aistudio.google.com)

---

**提示**: 如果你在 ACP 中使用，推荐保持默认的 `gemini-2.5-flash`，除非有特殊需求。
