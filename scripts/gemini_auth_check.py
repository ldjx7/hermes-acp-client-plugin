#!/usr/bin/env python3
"""
Gemini 认证诊断工具

检查认证状态、Token 有效期、并提供解决方案
"""

import os
import json
import sys
from datetime import datetime
from pathlib import Path

GEMINI_CONFIG_DIR = Path.home() / ".gemini"
HERMES_ENV = Path.home() / ".hermes" / ".env"

def check_api_key():
    """检查 API Key 配置"""
    print("=" * 60)
    print("1. 检查 API Key 配置")
    print("=" * 60)
    
    # 检查环境变量
    env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if env_key:
        print(f"✓ 环境变量已配置：GEMINI_API_KEY={env_key[:15]}...")
        return True
    
    # 检查 .env 文件
    if HERMES_ENV.exists():
        with open(HERMES_ENV) as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY=") or line.startswith("GOOGLE_API_KEY="):
                    key = line.strip().split("=")[1]
                    if key and not key.startswith("#"):
                        print(f"✓ .env 文件已配置：{key[:15]}...")
                        return True
    
    print("✗ 未找到 API Key 配置")
    print("\n解决方案:")
    print("  1. 访问 https://aistudio.google.com/app/apikey")
    print("  2. 创建 API Key")
    print("  3. 添加到 ~/.hermes/.env:")
    print("     GEMINI_API_KEY=AIzaSy...")
    return False


def check_oauth():
    """检查 OAuth 认证"""
    print("\n" + "=" * 60)
    print("2. 检查 OAuth 认证")
    print("=" * 60)
    
    oauth_file = GEMINI_CONFIG_DIR / "oauth_creds.json"
    backup_file = GEMINI_CONFIG_DIR / "oauth_creds.json.bak"
    accounts_file = GEMINI_CONFIG_DIR / "google_accounts.json"
    
    # 检查 OAuth 凭证
    if oauth_file.exists():
        print(f"✓ OAuth 凭证文件存在：{oauth_file}")
        try:
            stat = oauth_file.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)
            print(f"  最后修改时间：{mtime}")
            
            # 检查是否过期（超过 30 天）
            age = datetime.now() - mtime
            if age.days > 30:
                print(f"  ⚠ 凭证已使用 {age.days} 天，可能需要重新认证")
            else:
                print(f"  ✓ 凭证较新（{age.days} 天前）")
        except Exception as e:
            print(f"  ✗ 读取失败：{e}")
    elif backup_file.exists():
        print(f"⚠ OAuth 凭证已被备份：{backup_file}")
        print("  这可能是因为:")
        print("  - 手动删除了凭证")
        print("  - 认证过期被清理")
        print("  - 需要重新认证")
    else:
        print("✗ 未找到 OAuth 凭证")
    
    # 检查账号
    if accounts_file.exists():
        try:
            with open(accounts_file) as f:
                data = json.load(f)
                active = data.get("active", "Unknown")
                print(f"✓ 活跃账号：{active}")
        except Exception as e:
            print(f"✗ 读取账号失败：{e}")
    
    return oauth_file.exists()


def check_settings():
    """检查配置"""
    print("\n" + "=" * 60)
    print("3. 检查 Gemini 配置")
    print("=" * 60)
    
    settings_file = GEMINI_CONFIG_DIR / "settings.json"
    if settings_file.exists():
        try:
            with open(settings_file) as f:
                data = json.load(f)
                auth_type = data.get("security", {}).get("auth", {}).get("selectedType", "Unknown")
                print(f"✓ 认证方式：{auth_type}")
                
                if auth_type == "oauth-personal":
                    print("  ⚠ 使用 OAuth 认证（会过期）")
                    print("  💡 建议：改用 API Key 认证（永久有效）")
        except Exception as e:
            print(f"✗ 读取配置失败：{e}")
    else:
        print("✗ 未找到配置文件")


def check_gemini_cli():
    """检查 CLI 安装"""
    print("\n" + "=" * 60)
    print("4. 检查 Gemini CLI")
    print("=" * 60)
    
    import shutil
    gemini_path = shutil.which("gemini")
    if gemini_path:
        print(f"✓ Gemini CLI 已安装：{gemini_path}")
        
        import subprocess
        try:
            result = subprocess.run(["gemini", "--version"], capture_output=True, text=True, timeout=5)
            print(f"  版本：{result.stdout.strip()}")
        except Exception as e:
            print(f"  ✗ 检查版本失败：{e}")
    else:
        print("✗ Gemini CLI 未安装")


def main():
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "Gemini 认证诊断工具" + " " * 20 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    has_api_key = check_api_key()
    has_oauth = check_oauth()
    check_settings()
    check_gemini_cli()
    
    # 总结
    print("\n" + "=" * 60)
    print("诊断总结")
    print("=" * 60)
    
    if has_api_key:
        print("✅ API Key 已配置 - 推荐使用，不会过期")
    elif has_oauth:
        print("⚠️  仅 OAuth 认证 - 会定期过期，建议配置 API Key")
    else:
        print("❌ 未配置任何认证 - 需要立即配置")
    
    print("\n建议操作:")
    if not has_api_key:
        print("  1. 获取 API Key: https://aistudio.google.com/app/apikey")
        print("  2. 添加到 ~/.hermes/.env: GEMINI_API_KEY=AIzaSy...")
        print("  3. 重启 Hermes 使配置生效")
    else:
        print("  ✅ 配置正确，无需操作")
    
    print()


if __name__ == "__main__":
    main()
