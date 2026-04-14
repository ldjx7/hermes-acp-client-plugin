"""
Hermes ACP Client Plugin

ACP (Agent Client Protocol) 客户端插件，用于派发任务到子会话、
监听进度、并自动回推结果。
"""

__version__ = "0.1.0"
__author__ = "Hermes Agent Team"
__status__ = "development"


def main():
    """程序主函数"""
    print("Hermes ACP Client Plugin")
    print("=" * 40)
    print(f"版本：{__version__}")
    print(f"状态：{__status__}")
    print("")
    print("这是一个 Hermes Agent 插件，用于:")
    print("  - 派发任务到 ACP 子会话 (Codex, Claude 等)")
    print("  - 监听子会话执行进度")
    print("  - 自动回推结果到父会话")
    print("")
    print("详细技术方案请参阅 docs/ACP_CLIENT_PLUGIN_PROPOSAL.md")


if __name__ == "__main__":
    main()
