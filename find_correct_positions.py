#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式坐标识别工具
帮助快速找到正确的输入框位置
"""

import pyautogui
import time
import subprocess

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


def activate_ths():
    """激活同花顺窗口"""
    script = '''
    tell application "同花顺"
        activate
    end tell
    '''
    try:
        subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
        time.sleep(0.5)
        return True
    except:
        print("⚠️  无法激活同花顺窗口")
        return False


def get_window_position():
    """获取同花顺窗口位置"""
    script = '''
    tell application "System Events"
        tell process "同花顺"
            set frontWindow to front window
            set windowPosition to position of frontWindow
            set windowSize to size of frontWindow
            return {item 1 of windowPosition, item 2 of windowPosition, item 1 of windowSize, item 2 of windowSize}
        end tell
    end tell
    '''
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            check=True, capture_output=True, text=True
        )
        coords = result.stdout.strip().split(', ')
        return tuple(int(c) for c in coords)
    except Exception as e:
        print(f"获取窗口位置失败: {e}")
        return None


def visual_coordinate_finder():
    """可视化坐标查找工具"""
    print("\n" + "="*80)
    print("🎯 交互式坐标识别工具")
    print("="*80)
    print("\n这个工具会帮你找到正确的输入框位置")
    print("\n步骤：")
    print("1. 确保同花顺交易面板已打开并可见")
    print("2. 对于每个UI元素，将鼠标移动到其中心位置")
    print("3. 在终端按 Enter 记录坐标")
    print("4. 程序会立即移动鼠标到该位置并点击，验证是否正确")
    print("\n提示：如果点击位置不对，按 'r' 重新标记该位置")
    print("="*80 + "\n")

    # 激活窗口
    if not activate_ths():
        print("请手动激活同花顺窗口后继续...")

    time.sleep(1)

    # 获取窗口位置
    window_pos = get_window_position()
    if window_pos:
        win_x, win_y, win_w, win_h = window_pos
        print(f"✅ 检测到窗口:")
        print(f"   位置: ({win_x}, {win_y})")
        print(f"   大小: {win_w} x {win_h}\n")
    else:
        print("⚠️  无法检测窗口位置\n")
        win_x, win_y = 0, 0

    # 要标记的位置
    targets = [
        ("buy_button", "【买入】按钮"),
        ("sell_button", "【卖出】按钮"),
        ("code_input", "【股票代码输入框】(交易面板中的，不是顶部搜索框！)"),
        ("price_input", "【价格输入框】"),
        ("quantity_input", "【数量输入框】"),
        ("confirm_button", "【确定买入/卖出】按钮"),
    ]

    results = []

    for key, label in targets:
        while True:
            print(f"\n{'─'*80}")
            print(f"📍 请将鼠标移动到 {label} 的中心")
            print(f"   提示：这是交易面板中的输入框，不是窗口顶部的搜索框！")
            print(f"   (按 Enter 确认，输入 's' 跳过)")

            user_input = input("   >> ").strip().lower()

            if user_input == 's':
                print("   ⏭️  已跳过")
                break

            # 获取鼠标位置
            mouse_x, mouse_y = pyautogui.position()

            # 计算相对坐标
            rel_x = mouse_x - win_x
            rel_y = mouse_y - win_y

            print(f"\n   记录的坐标:")
            print(f"   - 绝对坐标 (屏幕): ({mouse_x}, {mouse_y})")
            print(f"   - 相对坐标 (窗口): ({rel_x}, {rel_y})")

            # 验证 - 移动鼠标到该位置
            print(f"\n   🔍 验证：移动鼠标到记录位置...")
            time.sleep(0.5)
            pyautogui.moveTo(mouse_x, mouse_y)
            time.sleep(0.3)

            print(f"   ❓ 鼠标现在是否在正确位置？")
            confirm = input("   (按 Enter 确认正确, 输入 'r' 重新标记): ").strip().lower()

            if confirm != 'r':
                # 点击测试
                print(f"   → 点击该位置进行测试...")
                pyautogui.click(mouse_x, mouse_y)
                time.sleep(0.3)

                print(f"\n   ❓ 点击是否在正确的位置？")
                final_confirm = input("   (按 Enter 确认, 输入 'r' 重新标记): ").strip().lower()

                if final_confirm != 'r':
                    results.append({
                        'key': key,
                        'label': label,
                        'abs_x': mouse_x,
                        'abs_y': mouse_y,
                        'rel_x': rel_x,
                        'rel_y': rel_y
                    })
                    print(f"   ✅ 已确认！")
                    break
                else:
                    print(f"   🔄 重新标记...")
            else:
                print(f"   🔄 重新标记...")

    # 生成配置代码
    print("\n\n" + "="*80)
    print("✅ 校准完成！以下是正确的坐标配置：")
    print("="*80 + "\n")

    print("# 相对坐标模式（推荐）")
    print("# 将以下代码复制到 ths_mac_trader.py 的 __init__ 方法中")
    print("-" * 80)
    print("self.coords_relative = {")
    for r in results:
        print(f"    '{r['key']}': ({r['rel_x']}, {r['rel_y']}),  # {r['label']}")
    print("}")
    print("\nself.coords = self.coords_relative.copy()")
    print("self.use_relative_coords = True")

    print("\n\n# 绝对坐标模式（备选）")
    print("-" * 80)
    print("self.coords = {")
    for r in results:
        print(f"    '{r['key']}': ({r['abs_x']}, {r['abs_y']}),  # {r['label']}")
    print("}")
    print("\nself.use_relative_coords = False")

    print("\n" + "="*80)
    print("💾 配置已生成！请复制上面的代码到 ths_mac_trader.py")
    print("="*80 + "\n")

    # 保存到文件
    with open('coordinates_config.txt', 'w', encoding='utf-8') as f:
        f.write("# 相对坐标配置\n")
        f.write("self.coords_relative = {\n")
        for r in results:
            f.write(f"    '{r['key']}': ({r['rel_x']}, {r['rel_y']}),  # {r['label']}\n")
        f.write("}\n\n")

        f.write("# 绝对坐标配置\n")
        f.write("self.coords = {\n")
        for r in results:
            f.write(f"    '{r['key']}': ({r['abs_x']}, {r['abs_y']}),  # {r['label']}\n")
        f.write("}\n")

    print("💾 配置也已保存到 coordinates_config.txt 文件")


def main():
    """主函数"""
    print("\n欢迎使用交互式坐标识别工具！")
    print("\n重要提示：")
    print("1. 确保同花顺已打开并登录")
    print("2. 确保交易面板可见")
    print("3. 鼠标要移动到输入框的中心位置")
    print("4. 注意区分【交易面板的输入框】和【顶部搜索框】\n")

    input("准备好后按 Enter 开始...")

    visual_coordinate_finder()


if __name__ == "__main__":
    main()
