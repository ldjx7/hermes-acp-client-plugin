# 📤 推送到 GitHub 指南

## 方案一：使用 gh CLI（推荐）

### 1. 安装 gh（如果未安装）

```bash
# Ubuntu/Debian
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of /usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh -y

# 验证安装
gh --version
```

### 2. 认证 GitHub

```bash
gh auth login
# 选择：GitHub.com → HTTPS → 浏览器登录
```

### 3. 创建仓库并推送

```bash
cd /root/vibecoding/hermes-acp-client-plugin

# 创建公开仓库
gh repo create hermes-acp-client-plugin --public --source . --push

# 或者手动操作：
# git remote add origin https://github.com/YOUR_USERNAME/hermes-acp-client-plugin.git
# git branch -M main
# git push -u origin main
```

---

## 方案二：使用 Git + Personal Access Token

### 1. 创建 Personal Access Token

1. 访问：https://github.com/settings/tokens
2. 点击 **"Generate new token (classic)"**
3. 填写：
   - **Note**: `hermes-acp-client-plugin`
   - **Expiration**: `90 days`（或更长）
   - **Scopes**: 勾选 `repo`（完整仓库权限）
4. 点击 **"Generate token"**
5. **复制 Token**（只显示一次！）

### 2. 创建 GitHub 仓库

访问：https://github.com/new

- **Repository name**: `hermes-acp-client-plugin`
- **Description**: `Hermes Agent ACP (Agent Client Protocol) Client Plugin - 派发任务到独立 AI Agent 子会话`
- **Visibility**: ✅ Public
- ❌ 不要勾选 "Initialize with README"（我们已有代码）
- 点击 **"Create repository"**

### 3. 推送代码

```bash
cd /root/vibecoding/hermes-acp-client-plugin

# 重命名分支为 main
git branch -M main

# 添加远程仓库（替换 YOUR_USERNAME 为你的 GitHub 用户名）
git remote add origin https://github.com/YOUR_USERNAME/hermes-acp-client-plugin.git

# 推送（使用 Token 作为密码）
git push -u origin main
```

推送时会提示输入密码 → **粘贴你的 Personal Access Token**

---

## 验证推送

推送成功后，访问：

```
https://github.com/YOUR_USERNAME/hermes-acp-client-plugin
```

应该能看到完整的仓库内容。

---

## 后续操作

### 安装插件（给其他用户）

```bash
hermes plugins install https://github.com/YOUR_USERNAME/hermes-acp-client-plugin.git
```

### 启用 GitHub Actions（可选）

在仓库 Settings → Actions 中启用 CI/CD。

### 添加 Topics（增加曝光）

在仓库主页 → 设置 Topics：
- `hermes-agent`
- `ai-agent`
- `acp`
- `plugin`
- `gemini`
- `claude`
- `codex`

---

## 常见问题

### Q: `remote: Permission denied`
A: Token 权限不足，重新生成时确保勾选 `repo` scope。

### Q: `fatal: repository not found`
A: 检查仓库名称和用户名是否正确。

### Q: 推送时卡住
A: 可能是网络问题，尝试：
```bash
git config --global http.postBuffer 524288000
git push -u origin main
```

---

**需要我帮你执行具体步骤吗？** 请提供：
1. 你的 GitHub 用户名
2. 选择的方案（gh CLI 或 Token）
