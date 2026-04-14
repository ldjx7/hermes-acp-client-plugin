# 🔧 配置 Gemini API Key（永久认证）

---

## 📋 当前状态

- **认证方式**: OAuth（会过期）
- **过期频率**: 经常
- **原因**: OAuth Token 有效期限制

---

## ✅ 解决方案：使用 API Key

### 第 1 步：获取 API Key

访问：https://aistudio.google.com/app/apikey

1. 登录 Google 账号
2. 点击 **"Create API Key"**
3. 选择项目（或创建新项目）
4. 复制 API Key（格式：`AIzaSy...`）

---

### 第 2 步：配置到环境变量

```bash
# 编辑 .env 文件
nano ~/.hermes/.env

# 添加或修改这一行
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

或者执行：

```bash
echo "GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXX" >> ~/.hermes/.env
```

---

### 第 3 步：验证配置

```bash
# 检查是否生效
grep GEMINI_API_KEY ~/.hermes/.env

# 测试 Gemini CLI（应该不再需要 OAuth）
gemini --model gemini-2.5-flash "Hello"
```

---

## 🔄 两种认证方式对比

| 特性 | OAuth | API Key |
|------|-------|---------|
| **有效期** | 7-90 天 | 永久 |
| **配置复杂度** | 需要浏览器登录 | 复制粘贴即可 |
| **适合场景** | 个人交互使用 | 服务器/自动化 |
| **安全性** | 高（可撤销） | 中（需保护 Key） |
| **推荐度** | ⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 🛡️ API Key 安全提示

1. **不要分享**: 不要提交到 Git 或公开分享
2. **限制配额**: 在 Google Cloud Console 设置每日限额
3. **监控使用**: 定期检查使用量
4. **轮换**: 每 6-12 个月更换一次

---

## 🧪 测试配置

```bash
# 设置环境变量
export GEMINI_API_KEY=$(grep "^GEMINI_API_KEY=" ~/.hermes/.env | cut -d= -f2)

# 测试 API
curl "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('✓ API Key 有效!' if 'models' in d else '✗ 无效')"
```

---

## 📝 如果仍然过期

### 检查项：

1. **环境变量是否加载**
   ```bash
   echo $GEMINI_API_KEY
   ```

2. **Hermes 是否重启**
   ```bash
   # 重启 Hermes 以加载新配置
   exit
   hermes
   ```

3. **Gemini CLI 版本**
   ```bash
   gemini --version
   # 应该是最新版
   ```

---

**配置完成后，认证将不再过期！** ✅
