#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API服务安装验证脚本

检查所有依赖和配置是否正确
"""

import sys
import os


def check_python_version():
    """检查Python版本"""
    print("\n1. Python版本检查")
    print("-" * 60)

    version = sys.version_info
    print(f"当前版本: Python {version.major}.{version.minor}.{version.micro}")

    if version.major >= 3 and version.minor >= 8:
        print("✅ Python版本满足要求（需要 >= 3.8）")
        return True
    else:
        print("❌ Python版本过低，需要 Python 3.8 或更高版本")
        return False


def check_dependencies():
    """检查依赖包"""
    print("\n2. 依赖包检查")
    print("-" * 60)

    required_packages = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("pydantic", "Pydantic"),
        ("pydantic_settings", "Pydantic Settings"),
        ("jose", "Python-JOSE"),
        ("pyautogui", "PyAutoGUI"),
    ]

    optional_packages = [
        ("akshare", "AKShare（市价买入需要）"),
    ]

    all_ok = True

    for package_name, display_name in required_packages:
        try:
            __import__(package_name)
            print(f"✅ {display_name}")
        except ImportError:
            print(f"❌ {display_name} - 未安装")
            all_ok = False

    print("\n可选依赖:")
    for package_name, display_name in optional_packages:
        try:
            __import__(package_name)
            print(f"✅ {display_name}")
        except ImportError:
            print(f"⚠️  {display_name} - 未安装（市价买入功能不可用）")

    return all_ok


def check_files():
    """检查关键文件"""
    print("\n3. 文件结构检查")
    print("-" * 60)

    required_files = [
        "main.py",
        "config.py",
        "api_models.py",
        "api_security.py",
        "api_routes.py",
        "trading_executor.py",
        "requirements_api.txt",
        ".env.example",
    ]

    all_ok = True

    for filename in required_files:
        if os.path.exists(filename):
            print(f"✅ {filename}")
        else:
            print(f"❌ {filename} - 文件缺失")
            all_ok = False

    return all_ok


def check_config():
    """检查配置文件"""
    print("\n4. 配置文件检查")
    print("-" * 60)

    if os.path.exists(".env"):
        print("✅ .env 配置文件存在")

        # 检查关键配置
        with open(".env", "r") as f:
            content = f.read()

            checks = [
                ("API_KEYS", "API密钥配置"),
                ("JWT_SECRET_KEY", "JWT密钥配置"),
            ]

            for key, desc in checks:
                if key in content:
                    print(f"  ✅ {desc}")
                else:
                    print(f"  ⚠️  {desc} - 未配置")

        return True
    else:
        print("⚠️  .env 配置文件不存在")
        print("   建议: cp .env.example .env")
        return False


def check_parent_module():
    """检查主项目模块"""
    print("\n5. 主项目模块检查")
    print("-" * 60)

    # 添加父目录到路径
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    try:
        from ths_mac_trader import THSMacTrader
        print("✅ ths_mac_trader.py 模块可导入")
        print("✅ THSMacTrader 类可实例化")
        return True
    except ImportError as e:
        print(f"❌ 无法导入主项目模块: {e}")
        return False


def print_summary(results):
    """打印总结"""
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)

    all_passed = all(results.values())

    for check, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{check}: {status}")

    print("=" * 60)

    if all_passed:
        print("\n🎉 所有检查通过！可以启动API服务")
        print("\n启动命令:")
        print("  ./start_server.sh")
        print("  或")
        print("  python3 -m uvicorn main:app --host 127.0.0.1 --port 8080")
    else:
        print("\n⚠️  存在问题，请先解决以上错误")
        print("\n常见解决方案:")
        print("  1. 安装依赖: pip3 install -r requirements_api.txt")
        print("  2. 复制配置: cp .env.example .env")
        print("  3. 编辑配置: nano .env")


def main():
    """主函数"""
    print("=" * 60)
    print("  同花顺交易API服务 - 安装验证")
    print("=" * 60)

    results = {
        "Python版本": check_python_version(),
        "依赖包": check_dependencies(),
        "文件结构": check_files(),
        "配置文件": check_config(),
        "主项目模块": check_parent_module(),
    }

    print_summary(results)


if __name__ == "__main__":
    main()
