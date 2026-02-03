#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同花顺坐标校准辅助工具
帮助用户快速校准交易面板的坐标
"""

import pyautogui
import time
import subprocess

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


def get_ths_window_position():
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
        return False


def calibrate_with_visual_feedback():
    """带可视化反馈的校准工具"""
    print("\n" + "="*70)
    print("🎯 同花顺坐标校准工具 - 可视化模式")
    print("="*70)
    print("\n使用说明：")
    print("1. 确保同花顺交易面板已打开")
    print("2. 将鼠标移动到目标位置")
    print("3. 按 Enter 记录当前坐标")
    print("4. 完成所有坐标校准后，自动生成配置代码")
    print("\n提示：按 Ctrl+C 随时退出")
    print("="*70 + "\n")

    # 激活窗口
    if not activate_ths():
        print("⚠️  警告：无法激活同花顺窗口，请手动打开")

    time.sleep(1)

    # 获取窗口位置
    window_pos = get_ths_window_position()
    if window_pos:
        win_x, win_y, win_w, win_h = window_pos
        print(f"✅ 检测到同花顺窗口:")
        print(f"   位置: ({win_x}, {win_y})")
        print(f"   大小: {win_w} x {win_h}\n")
        print("⚠️  请确保在校准过程中不要移动窗口！\n")
    else:
        print("⚠️  无法自动检测窗口位置，将使用绝对坐标模式\n")
        win_x, win_y = 0, 0

    # 校准目标
    targets = [
        ("buy_button", "【买入】按钮"),
        ("sell_button", "【卖出】按钮"),
        ("code_input", "【股票代码输入框】"),
        ("price_input", "【价格输入框】"),
        ("quantity_input", "【数量输入框】"),
        ("confirm_button", "【确定买入/卖出】按钮"),
        ("trade_tab", "【交易Tab】按钮（用于切换到交易Tab）"),
        ("popup_confirm_button", "【弹窗确认】按钮（登录超时弹窗的确认按钮）"),
    ]

    results = []
    region_results = []

    try:
        # 第一步：校准点坐标
        for key, label in targets:
            print(f"\n{'─'*70}")
            print(f"📍 请将鼠标移动到 {label}")
            print(f"   (在终端中按 Enter 确认)")
            input()

            # 获取当前鼠标位置
            mouse_x, mouse_y = pyautogui.position()

            # 计算相对坐标
            rel_x = mouse_x - win_x
            rel_y = mouse_y - win_y

            results.append({
                'key': key,
                'label': label,
                'abs_x': mouse_x,
                'abs_y': mouse_y,
                'rel_x': rel_x,
                'rel_y': rel_y
            })

            print(f"   ✅ 记录成功！")
            print(f"      绝对坐标: ({mouse_x}, {mouse_y})")
            print(f"      相对坐标: ({rel_x}, {rel_y})")

            # 可视化确认 - 移动鼠标并点击一次
            pyautogui.moveTo(mouse_x, mouse_y)
            time.sleep(0.3)

        # 第二步：校准区域坐标
        print(f"\n{'='*70}")
        print("📐 现在开始校准区域（用于OCR识别）")
        print("="*70)

        region_targets = [
            ("trade_tab_region", "【交易Tab区域】（包含\"交易\"文字的矩形区域）"),
            ("popup_region", "【弹窗内容区域】（登录超时弹窗的文字内容区域）"),
        ]

        for key, label in region_targets:
            print(f"\n{'─'*70}")
            print(f"📍 请校准 {label}")
            print(f"   步骤1: 将鼠标移动到区域的 【左上角】，然后按 Enter")
            input()

            # 获取左上角坐标
            x1, y1 = pyautogui.position()
            print(f"   ✅ 左上角: ({x1}, {y1})")

            print(f"   步骤2: 将鼠标移动到区域的 【右下角】，然后按 Enter")
            input()

            # 获取右下角坐标
            x2, y2 = pyautogui.position()
            print(f"   ✅ 右下角: ({x2}, {y2})")

            # 计算区域参数
            abs_x = x1
            abs_y = y1
            width = x2 - x1
            height = y2 - y1

            # 计算相对坐标
            rel_x = abs_x - win_x
            rel_y = abs_y - win_y

            region_results.append({
                'key': key,
                'label': label,
                'abs_x': abs_x,
                'abs_y': abs_y,
                'width': width,
                'height': height,
                'rel_x': rel_x,
                'rel_y': rel_y
            })

            print(f"   ✅ 区域记录成功！")
            print(f"      绝对坐标: ({abs_x}, {abs_y}, {width}, {height})")
            print(f"      相对坐标: ({rel_x}, {rel_y}, {width}, {height})")

            # 可视化确认 - 移动鼠标到区域中心
            center_x = abs_x + width // 2
            center_y = abs_y + height // 2
            pyautogui.moveTo(center_x, center_y)
            time.sleep(0.3)

    except KeyboardInterrupt:
        print("\n\n⚠️  校准已取消")
        return

    # 生成配置代码
    print("\n" + "="*70)
    print("📋 校准完成！请将以下代码复制到您的配置中：")
    print("="*70 + "\n")

    print("# 方法1: 使用相对坐标（推荐 - 窗口位置变化时仍然有效）")
    print("-" * 70)
    print("self.coords_relative = {")
    print("    # 点坐标（x, y）")
    for r in results:
        print(f"    '{r['key']}': ({r['rel_x']}, {r['rel_y']}),  # {r['label']}")
    print()
    print("    # 区域坐标（x, y, width, height）")
    for r in region_results:
        print(f"    '{r['key']}': ({r['rel_x']}, {r['rel_y']}, {r['width']}, {r['height']}),  # {r['label']}")
    print("}")
    print("\n# 在初始化时设置：")
    print("self.use_relative_coords = True")

    print("\n\n# 方法2: 使用绝对坐标（仅当窗口位置固定时使用）")
    print("-" * 70)
    print("self.coords = {")
    print("    # 点坐标（x, y）")
    for r in results:
        print(f"    '{r['key']}': ({r['abs_x']}, {r['abs_y']}),  # {r['label']}")
    print()
    print("    # 区域坐标（x, y, width, height）")
    for r in region_results:
        print(f"    '{r['key']}': ({r['abs_x']}, {r['abs_y']}, {r['width']}, {r['height']}),  # {r['label']}")
    print("}")
    print("\n# 在初始化时设置：")
    print("self.use_relative_coords = False")

    print("\n" + "="*70)
    print("💡 建议：使用方法1（相对坐标），这样即使移动窗口也能正常工作")
    print("="*70 + "\n")


def test_coordinates():
    """测试坐标是否准确"""
    print("\n" + "="*70)
    print("🧪 坐标测试工具")
    print("="*70)
    print("\n请输入要测试的坐标（格式: x,y）")
    print("例如: 280,140")
    print("输入 'q' 退出\n")

    activate_ths()

    while True:
        try:
            user_input = input("坐标 (x,y): ").strip()
            if user_input.lower() == 'q':
                break

            x, y = map(int, user_input.split(','))

            print(f"→ 移动鼠标到 ({x}, {y})")
            pyautogui.moveTo(x, y)
            time.sleep(0.5)

            print("→ 点击该位置...")
            pyautogui.click(x, y)

            print("✅ 测试完成\n")

        except ValueError:
            print("❌ 格式错误，请使用 x,y 格式\n")
        except KeyboardInterrupt:
            print("\n退出测试")
            break


def main():
    """主菜单"""
    while True:
        print("\n" + "="*70)
        print("🔧 同花顺坐标校准工具")
        print("="*70)
        print("\n1. 开始校准（推荐）")
        print("2. 测试坐标")
        print("3. 实时鼠标位置")
        print("0. 退出")
        print("\n" + "="*70)

        choice = input("\n请选择 [0-3]: ").strip()

        if choice == '0':
            print("\n再见！")
            break
        elif choice == '1':
            calibrate_with_visual_feedback()
        elif choice == '2':
            test_coordinates()
        elif choice == '3':
            print("\n实时鼠标位置（按 Ctrl+C 退出）：")
            try:
                while True:
                    x, y = pyautogui.position()
                    print(f"\r当前位置: ({x:4d}, {y:4d})    ", end='', flush=True)
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n")
        else:
            print("\n❌ 无效选择，请重试")


if __name__ == "__main__":
    main()
