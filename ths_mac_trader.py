#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同花顺 Mac 版自动化交易脚本
基于 PyAutoGUI 实现 GUI 自动化

使用前请先安装依赖：
pip3 install pyautogui pillow pyobjc-framework-Quartz

注意：
1. 首次运行需要在 系统偏好设置 -> 安全性与隐私 -> 隐私 -> 辅助功能 中授权终端/Python
2. 请先在模拟盘测试，确认坐标正确后再用于实盘
3. 坐标会因屏幕分辨率和窗口位置变化，需要根据实际情况调整
"""

import pyautogui
import time
import subprocess
import os
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# 安全设置：防止鼠标失控时可以快速移动到屏幕角落停止
pyautogui.FAILSAFE = True
# 每次操作后的延迟（秒）
pyautogui.PAUSE = 0.3


class TradeDirection(Enum):
    """交易方向"""
    BUY = "买入"
    SELL = "卖出"


@dataclass
class TradeOrder:
    """交易订单"""
    stock_code: str      # 股票代码
    price: float         # 价格
    quantity: int        # 数量
    direction: TradeDirection  # 买入/卖出


class THSMacTrader:
    """
    同花顺 Mac 版自动化交易类

    重要：使用前需要校准坐标！
    运行 calibrate() 方法获取你屏幕上的实际坐标
    """

    def __init__(self):
        # ============================================
        # 界面元素坐标配置（需要根据你的屏幕分辨率调整）
        # 使用 calibrate() 方法获取正确坐标
        # ============================================

        # 交易面板相对于窗口左上角的偏移量（已校准）
        # 注意：这些是相对坐标，会在使用时加上窗口位置
        self.coords_relative = {
            # 买入/卖出切换按钮
            'buy_button': (334, 92),      # "买入" 按钮
            'sell_button': (411, 94),     # "卖出" 按钮

            # 输入框
            'code_input': (323, 155),     # 代码输入框
            'price_input': (342, 202),    # 价格输入框
            'quantity_input': (349, 263), # 数量输入框

            # 确认按钮
            'confirm_button': (367, 309), # "确定买入" 或 "确定卖出" 按钮

            # 持仓列表区域（用于点击选择股票）
            'position_area': (400, 380),  # 持仓列表起始位置
        }

        # 绝对坐标模式（向后兼容）
        self.coords = self.coords_relative.copy()

        # 同花顺应用名称
        self.app_name = "同花顺"

        # 窗口位置缓存
        self.window_pos = None

        # 是否使用相对坐标模式（推荐）
        self.use_relative_coords = True

    def activate_ths_window(self) -> bool:
        """
        激活同花顺窗口到前台并更新窗口位置
        """
        script = f'''
        tell application "{self.app_name}"
            activate
        end tell
        '''
        try:
            subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
            time.sleep(0.5)  # 等待窗口激活

            # 更新窗口位置
            if self.use_relative_coords:
                self.window_pos = self.get_window_position()
                if self.window_pos:
                    print(f"  → 窗口位置: ({self.window_pos[0]}, {self.window_pos[1]}), 大小: ({self.window_pos[2]}x{self.window_pos[3]})")
                else:
                    print("  ⚠️  无法获取窗口位置，将使用绝对坐标")

            return True
        except subprocess.CalledProcessError:
            print(f"错误：无法激活 {self.app_name} 窗口，请确保应用已打开")
            return False

    def get_window_position(self) -> Optional[Tuple[int, int, int, int]]:
        """
        获取同花顺窗口位置和大小
        返回：(x, y, width, height) 或 None
        """
        script = f'''
        tell application "System Events"
            tell process "{self.app_name}"
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
            # 解析返回的坐标
            coords = result.stdout.strip().split(', ')
            return tuple(int(c) for c in coords)
        except Exception as e:
            print(f"获取窗口位置失败: {e}")
            return None

    def get_absolute_coords(self, relative_x: int, relative_y: int) -> Tuple[int, int]:
        """
        将相对坐标转换为绝对坐标
        """
        if not self.use_relative_coords:
            return (relative_x, relative_y)

        if self.window_pos is None:
            self.window_pos = self.get_window_position()

        if self.window_pos is None:
            print("警告：无法获取窗口位置，使用绝对坐标")
            return (relative_x, relative_y)

        win_x, win_y, _, _ = self.window_pos
        return (win_x + relative_x, win_y + relative_y)

    def click_at(self, x: int, y: int, clicks: int = 1):
        """
        在指定坐标点击
        如果启用相对坐标模式，会自动转换为绝对坐标
        """
        abs_x, abs_y = self.get_absolute_coords(x, y)
        print(f"  → 点击位置: ({abs_x}, {abs_y})")
        pyautogui.click(abs_x, abs_y, clicks=clicks)
        time.sleep(0.1)

    def clear_and_type(self, x: int, y: int, text: str):
        """
        点击输入框，清空内容，输入新文本
        处理同花顺自动填充的情况
        """
        # 单击输入框获取焦点
        self.click_at(x, y, clicks=1)
        time.sleep(0.3)  # 等待焦点切换和可能的自动填充

        # 多次尝试清空，确保清除自动填充的内容
        for attempt in range(3):  # 最多尝试3次
            # 全选
            pyautogui.hotkey('command', 'a')
            time.sleep(0.1)

            # 删除
            pyautogui.press('delete')
            time.sleep(0.1)

            # 再次删除（确保清空）
            pyautogui.press('backspace')
            time.sleep(0.1)

            if attempt < 2:  # 前两次尝试后再次全选删除
                pyautogui.hotkey('command', 'a')
                time.sleep(0.05)
                pyautogui.press('delete')
                time.sleep(0.1)

        # 最后一次确保清空
        pyautogui.hotkey('command', 'a')
        time.sleep(0.05)
        pyautogui.press('delete')
        time.sleep(0.15)

        # 输入文本（使用 typewrite 处理数字和字母）
        pyautogui.typewrite(text, interval=0.05)
        time.sleep(0.1)

    def input_text_via_clipboard(self, x: int, y: int, text: str):
        """
        通过剪贴板输入文本（支持中文）
        处理同花顺自动填充的情况
        """
        import subprocess

        # 单击输入框获取焦点
        self.click_at(x, y, clicks=1)
        time.sleep(0.3)  # 等待焦点切换和可能的自动填充

        # 多次清空以确保删除自动填充的内容
        for _ in range(2):
            pyautogui.hotkey('command', 'a')
            time.sleep(0.1)
            pyautogui.press('delete')
            time.sleep(0.1)

        # 最后一次清空
        pyautogui.hotkey('command', 'a')
        time.sleep(0.05)
        pyautogui.press('delete')
        time.sleep(0.15)

        # 将文本复制到剪贴板
        process = subprocess.Popen(
            ['pbcopy'],
            stdin=subprocess.PIPE
        )
        process.communicate(text.encode('utf-8'))

        # 粘贴
        pyautogui.hotkey('command', 'v')
        time.sleep(0.1)

    def switch_direction(self, direction: TradeDirection):
        """
        切换买入/卖出方向
        """
        if direction == TradeDirection.BUY:
            self.click_at(*self.coords['buy_button'])
        else:
            self.click_at(*self.coords['sell_button'])
        time.sleep(0.2)

    def input_stock_code(self, code: str):
        """
        输入股票代码
        """
        self.clear_and_type(*self.coords['code_input'], code)
        time.sleep(0.3)  # 等待行情加载

    def input_price(self, price: float):
        """
        输入价格
        """
        self.clear_and_type(*self.coords['price_input'], str(price))

    def input_quantity(self, quantity: int):
        """
        输入数量
        """
        self.clear_and_type(*self.coords['quantity_input'], str(quantity))

    def confirm_order(self):
        """
        点击确认下单按钮
        """
        self.click_at(*self.coords['confirm_button'])
        time.sleep(0.5)

    def place_order(self, order: TradeOrder, confirm: bool = False) -> bool:
        """
        执行下单操作

        参数：
            order: 交易订单
            confirm: 是否自动确认（谨慎使用！）

        返回：
            是否执行成功
        """
        print(f"\n{'='*50}")
        print(f"准备下单: {order.direction.value} {order.stock_code}")
        print(f"价格: {order.price}, 数量: {order.quantity}")
        print(f"{'='*50}")

        # 1. 激活同花顺窗口
        if not self.activate_ths_window():
            return False

        # 2. 切换买入/卖出方向
        print("切换交易方向...")
        self.switch_direction(order.direction)

        # 3. 输入股票代码
        print(f"输入股票代码: {order.stock_code}")
        self.input_stock_code(order.stock_code)

        # 4. 输入价格
        print(f"输入价格: {order.price}")
        self.input_price(order.price)

        # 5. 输入数量
        print(f"输入数量: {order.quantity}")
        self.input_quantity(order.quantity)

        # 6. 确认下单
        if confirm:
            print("⚠️  正在确认下单...")
            self.confirm_order()
            print("✅ 下单指令已发送")
        else:
            print("\n📋 订单已填写完毕，请手动点击确认按钮")
            print("   （设置 confirm=True 可自动确认）")

        return True

    def buy(self, code: str, price: float, quantity: int, confirm: bool = False) -> bool:
        """
        买入股票
        """
        order = TradeOrder(
            stock_code=code,
            price=price,
            quantity=quantity,
            direction=TradeDirection.BUY
        )
        return self.place_order(order, confirm)

    def sell(self, code: str, price: float, quantity: int, confirm: bool = False) -> bool:
        """
        卖出股票
        """
        order = TradeOrder(
            stock_code=code,
            price=price,
            quantity=quantity,
            direction=TradeDirection.SELL
        )
        return self.place_order(order, confirm)

    def calibrate(self):
        """
        坐标校准工具
        移动鼠标到目标位置，按 Enter 记录坐标
        按 q 退出校准
        """
        print("\n" + "="*60)
        print("🎯 坐标校准工具")
        print("="*60)
        print("使用方法：")
        print("1. 将鼠标移动到目标位置")
        print("2. 按下任意键（在终端中）记录当前坐标")
        print("3. 输入 'q' 退出校准")
        print("="*60 + "\n")

        positions = []
        labels = [
            "买入按钮",
            "卖出按钮",
            "代码输入框",
            "价格输入框",
            "数量输入框",
            "确认按钮"
        ]

        for label in labels:
            print(f"\n请将鼠标移动到【{label}】位置，然后在终端按 Enter...")
            user_input = input()
            if user_input.lower() == 'q':
                break

            x, y = pyautogui.position()
            positions.append((label, x, y))
            print(f"✅ {label}: ({x}, {y})")

        print("\n" + "="*60)
        print("📋 校准结果（请复制到代码中）：")
        print("="*60)
        print("self.coords = {")

        key_map = {
            "买入按钮": "buy_button",
            "卖出按钮": "sell_button",
            "代码输入框": "code_input",
            "价格输入框": "price_input",
            "数量输入框": "quantity_input",
            "确认按钮": "confirm_button"
        }

        for label, x, y in positions:
            key = key_map.get(label, label)
            print(f"    '{key}': ({x}, {y}),")
        print("}")

        return positions

    def get_mouse_position(self):
        """
        实时显示鼠标位置（用于调试）
        按 Ctrl+C 退出
        """
        print("实时鼠标位置追踪（按 Ctrl+C 退出）：")
        try:
            while True:
                x, y = pyautogui.position()
                print(f"\r当前位置: ({x}, {y})    ", end='', flush=True)
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n追踪已停止")


class ImageBasedTrader(THSMacTrader):
    """
    基于图像识别的增强版交易类
    更稳定，不受窗口位置变化影响
    """

    def __init__(self, images_dir: str = "./ths_images"):
        super().__init__()
        self.images_dir = images_dir

        # 确保图片目录存在
        os.makedirs(images_dir, exist_ok=True)

    def capture_button_images(self):
        """
        截取按钮图片用于后续识别
        """
        print("\n" + "="*60)
        print("🖼️  按钮图片截取工具")
        print("="*60)
        print("将在指定位置截取小块图片用于图像识别")

        buttons = [
            ("buy_button", "买入按钮"),
            ("sell_button", "卖出按钮"),
            ("confirm_buy", "确定买入按钮"),
            ("confirm_sell", "确定卖出按钮"),
        ]

        for filename, label in buttons:
            print(f"\n请将鼠标移动到【{label}】中心，按 Enter 截取...")
            input()
            x, y = pyautogui.position()

            # 截取按钮区域（50x30 像素）
            region = (x - 25, y - 15, 50, 30)
            screenshot = pyautogui.screenshot(region=region)

            filepath = os.path.join(self.images_dir, f"{filename}.png")
            screenshot.save(filepath)
            print(f"✅ 已保存: {filepath}")

    def find_and_click(self, image_name: str, confidence: float = 0.8) -> bool:
        """
        查找图片并点击
        """
        filepath = os.path.join(self.images_dir, f"{image_name}.png")
        if not os.path.exists(filepath):
            print(f"图片不存在: {filepath}")
            return False

        try:
            location = pyautogui.locateCenterOnScreen(
                filepath,
                confidence=confidence
            )
            if location:
                pyautogui.click(location)
                return True
        except Exception as e:
            print(f"图像识别失败: {e}")

        return False


# ============================================
# 使用示例
# ============================================

def main():
    """主函数 - 演示如何使用"""

    trader = THSMacTrader()

    print("""
╔══════════════════════════════════════════════════════════╗
║        同花顺 Mac 版自动化交易脚本                        ║
╠══════════════════════════════════════════════════════════╣
║  1. 校准坐标 (首次使用必须)                               ║
║  2. 实时鼠标位置                                          ║
║  3. 测试买入（不确认）                                    ║
║  4. 测试卖出（不确认）                                    ║
║  0. 退出                                                  ║
╚══════════════════════════════════════════════════════════╝
    """)

    while True:
        choice = input("\n请选择功能 [0-4]: ").strip()

        if choice == '0':
            print("再见！")
            break

        elif choice == '1':
            trader.calibrate()

        elif choice == '2':
            trader.get_mouse_position()

        elif choice == '3':
            code = input("请输入股票代码: ").strip()
            price = float(input("请输入价格: ").strip())
            quantity = int(input("请输入数量: ").strip())
            trader.buy(code, price, quantity, confirm=False)

        elif choice == '4':
            code = input("请输入股票代码: ").strip()
            price = float(input("请输入价格: ").strip())
            quantity = int(input("请输入数量: ").strip())
            trader.sell(code, price, quantity, confirm=False)

        else:
            print("无效选择，请重试")


if __name__ == "__main__":
    main()