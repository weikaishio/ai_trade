#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证码区域可视化校准工具
"""

import pyautogui
import time
import subprocess
from PIL import Image, ImageDraw, ImageFont

def get_ths_window_position():
    """
    获取同花顺窗口位置
    返回: (x, y, width, height) 或 None
    """
    app_name = "同花顺"
    script = f'''
    tell application "System Events"
        tell process "{app_name}"
            set frontWindow to front window
            set windowPosition to position of frontWindow
            set windowSize to size of frontWindow
            return {{item 1 of windowPosition, item 2 of windowPosition, item 1 of windowSize, item 2 of windowSize}}
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
        print(f"⚠️  无法获取窗口位置: {e}")
        return None

def calibrate_captcha_region():
    """
    交互式校准验证码图片区域
    """
    print("="*70)
    print("🎯 验证码区域可视化校准工具")
    print("="*70)
    print("\n使用方法：")
    print("1. 确保同花顺登录弹窗已打开且显示验证码")
    print("2. 按照提示点击验证码图片的左上角和右下角")
    print("3. 工具会生成带框标记的预览图")
    print("4. 确认无误后，坐标会自动保存（相对坐标和绝对坐标）")
    print("="*70)

    input("\n准备就绪后按 Enter 开始...")

    # 获取窗口位置
    print("\n正在获取同花顺窗口位置...")
    window_pos = get_ths_window_position()

    if window_pos:
        win_x, win_y, win_w, win_h = window_pos
        print(f"✅ 窗口位置: ({win_x}, {win_y}), 大小: ({win_w}x{win_h})")
        use_relative = True
    else:
        print("⚠️  无法获取窗口位置，将使用绝对坐标")
        use_relative = False

    # 第一步：点击左上角
    print("\n步骤 1/2: 移动鼠标到验证码图片的【左上角】，然后按 Enter...")
    input()
    x1, y1 = pyautogui.position()
    print(f"✅ 左上角坐标: ({x1}, {y1})")

    # 第二步：点击右下角
    print("\n步骤 2/2: 移动鼠标到验证码图片的【右下角】，然后按 Enter...")
    input()
    x2, y2 = pyautogui.position()
    print(f"✅ 右下角坐标: ({x2}, {y2})")

    # 计算区域（绝对坐标）
    abs_x = min(x1, x2)
    abs_y = min(y1, y2)
    width = abs(x2 - x1)
    height = abs(y2 - y1)

    print(f"\n📐 绝对坐标区域:")
    print(f"   X: {abs_x}, Y: {abs_y}")
    print(f"   宽度: {width}, 高度: {height}")
    print(f"   格式: ({abs_x}, {abs_y}, {width}, {height})")

    # 计算相对坐标
    if use_relative:
        rel_x = abs_x - win_x
        rel_y = abs_y - win_y
        print(f"\n📐 相对坐标区域（推荐使用）:")
        print(f"   X: {rel_x}, Y: {rel_y}")
        print(f"   宽度: {width}, 高度: {height}")
        print(f"   格式: ({rel_x}, {rel_y}, {width}, {height})")
    else:
        rel_x, rel_y = abs_x, abs_y

    # 预览截图
    print("\n📸 正在截取预览图...")
    screenshot = pyautogui.screenshot(region=(abs_x, abs_y, width, height))

    # 保存原始截图
    preview_path = "./captcha_region_preview.png"
    screenshot.save(preview_path)
    print(f"✅ 预览图已保存: {preview_path}")

    # 生成带框标记的全屏截图
    print("\n🖼️  正在生成标记图...")
    full_screenshot = pyautogui.screenshot()
    draw = ImageDraw.Draw(full_screenshot)

    # 绘制红色矩形框
    draw.rectangle([(abs_x, abs_y), (abs_x + width, abs_y + height)], outline='red', width=5)

    # 添加文字标签
    try:
        draw.text((abs_x, abs_y - 25), "CAPTCHA REGION", fill='red')
    except:
        pass

    marked_path = "./captcha_region_marked.png"
    full_screenshot.save(marked_path)
    print(f"✅ 标记图已保存: {marked_path}")

    # 自动打开图片
    try:
        subprocess.run(['open', preview_path], check=False)
        subprocess.run(['open', marked_path], check=False)
    except:
        pass

    # 确认
    print("\n" + "="*70)
    print("请检查预览图和标记图，确认区域是否正确")
    print("="*70)

    confirm = input("\n区域正确？(y/n): ").strip().lower()

    if confirm == 'y':
        # 保存到配置
        if use_relative:
            config_str_relative = f"'captcha_image_region': ({rel_x}, {rel_y}, {width}, {height}),"
            config_str_absolute = f"# 绝对坐标（仅供参考）: ({abs_x}, {abs_y}, {width}, {height})"

            print("\n" + "="*70)
            print("✅ 校准完成！请将以下配置复制到 ths_mac_trader.py:")
            print("="*70)
            print("推荐使用相对坐标（适应窗口移动）：")
            print(config_str_relative)
            print(config_str_absolute)
            print("="*70)

            # 保存到文件
            with open("captcha_region_config.txt", "w") as f:
                f.write("# 相对坐标（推荐）\n")
                f.write(config_str_relative + "\n\n")
                f.write(config_str_absolute + "\n")
        else:
            config_str = f"'captcha_image_region': ({abs_x}, {abs_y}, {width}, {height}),"

            print("\n" + "="*70)
            print("✅ 校准完成！请将以下配置复制到 ths_mac_trader.py:")
            print("="*70)
            print(config_str)
            print("="*70)

            # 保存到文件
            with open("captcha_region_config.txt", "w") as f:
                f.write(config_str)

        print("\n配置已保存到: captcha_region_config.txt")

        if use_relative:
            return (rel_x, rel_y, width, height)
        else:
            return (abs_x, abs_y, width, height)
    else:
        print("\n重新校准...")
        return calibrate_captcha_region()

if __name__ == "__main__":
    calibrate_captcha_region()
