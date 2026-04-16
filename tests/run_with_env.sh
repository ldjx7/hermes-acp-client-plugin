#!/bin/bash
# claude-cli 测试包装脚本
# 加载 .bashrc 中的环境变量

# 加载用户环境变量
source ~/.bashrc 2>/dev/null || true

# 验证环境变量
echo "环境变量检查:"
echo "  ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:0:10}..."
echo "  ANTHROPIC_BASE_URL: ${ANTHROPIC_BASE_URL}"
echo "  ANTHROPIC_MODEL: ${ANTHROPIC_MODEL}"
echo ""

# 运行测试
cd ~/.hermes/plugins/acp-client
python3 "$@"
