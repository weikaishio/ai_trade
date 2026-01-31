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


@dataclass
class Position:
    """持仓信息"""
    stock_code: str      # 股票代码
    stock_name: str      # 股票名称
    available_qty: int   # 可用数量
    current_price: float # 当前价格（可选）


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

            # 模态确认对话框按钮（点击confirm_button后弹出的对话框）
            'modal_confirm_button': (1068, 705),  # 对话框中的"确定"按钮，需要校准

            # 持仓列表区域（用于点击选择股票）
            'position_area': (400, 380),  # 持仓列表起始位置

            # 持仓标签页按钮（用于切换到持仓界面）
            'position_tab': (304, 351),    # "持仓" 标签按钮，需要校准

            # 委托标签页按钮（用于切换到委托界面）
            'order_tab': (360, 352),       # "委托" 标签按钮，需要校准

            # 持仓列表截图区域 (x, y, width, height) - 用于OCR识别
            # 需要包含完整的持仓表格，从表头到最后一行
            'position_list_region': (259, 378, 1102, 689),  # 默认区域，需要校准

            # 委托列表截图区域 (x, y, width, height) - 用于OCR识别
            # 需要包含完整的委托表格，从表头到最后一行
            'order_list_region': (259, 378, 1102, 689),     # 默认区域，需要校准
        }

        # 绝对坐标模式（向后兼容）
        self.coords = self.coords_relative.copy()
        # self.coords = {
        #     'buy_button': (387, 117),
        #     'sell_button': (455, 117),
        #     'code_input': (376, 180),
        #     'price_input': (396, 228),
        #     'quantity_input': (388, 289),
        #     'confirm_button': (420, 335),
        #     'modal_confirm_button': (1098, 735),
        #     'position_area': (400, 380),  # 持仓列表起始位置
        #     'position_tab': (304, 351),    # "持仓" 标签按钮，需要校准
        #     'position_list_region': (259, 378, 1102, 689),  # 默认区域，需要校准
        # }


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

    def switch_to_position_tab(self):
        """
        切换到持仓标签页
        确保在OCR识别持仓前显示的是持仓界面
        """
        print("正在切换到持仓标签页...")

        # 点击持仓标签
        if 'position_tab' in self.coords:
            self.click_at(*self.coords['position_tab'])
            time.sleep(0.5)  # 等待标签页切换
            print("✅ 已切换到持仓标签页")
        else:
            print("⚠️  未配置持仓标签坐标，跳过切换")
            print("   提示：运行校准工具添加 'position_tab' 坐标")

    def switch_to_order_tab(self):
        """
        切换到委托标签页
        确保在OCR识别委托前显示的是委托界面
        """
        print("正在切换到委托标签页...")

        # 点击委托标签
        if 'order_tab' in self.coords:
            self.click_at(*self.coords['order_tab'])
            time.sleep(0.5)  # 等待标签页切换
            print("✅ 已切换到委托标签页")
        else:
            print("⚠️  未配置委托标签坐标，跳过切换")
            print("   提示：运行校准工具添加 'order_tab' 坐标")

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
        包括两步：
        1. 点击表单上的"确定买入/卖出"按钮
        2. 点击弹出对话框上的"确定"按钮（真正提交）
        """
        # 第一步：点击表单确认按钮
        print("  → 点击确认按钮...")
        self.click_at(*self.coords['confirm_button'])
        time.sleep(0.8)  # 等待对话框弹出

        # 第二步：点击模态对话框的确认按钮
        if 'modal_confirm_button' in self.coords:
            print("  → 点击对话框确认按钮...")
            self.click_at(*self.coords['modal_confirm_button'])
            time.sleep(0.5)  # 等待订单提交
            print("  ✅ 订单已提交")
        else:
            print("  ⚠️  未配置模态确认按钮坐标")
            print("     请手动点击对话框确认按钮，或运行校准工具添加坐标")
            time.sleep(2)  # 给用户时间手动点击

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

    def get_positions_from_input(self) -> list:
        """
        从用户输入获取持仓列表
        用户需要手动提供持仓信息

        返回: Position 对象列表
        """
        print("\n" + "="*60)
        print("📊 输入持仓信息")
        print("="*60)
        print("请输入你的持仓信息（每行一个，格式：股票代码,可用数量,卖出价格）")
        print("例如: 603993,100,24.5")
        print("输入完成后，输入空行结束")
        print("="*60 + "\n")

        positions = []
        while True:
            line = input("持仓 (或按 Enter 结束): ").strip()
            if not line:
                break

            try:
                parts = line.split(',')
                if len(parts) >= 2:
                    code = parts[0].strip()
                    qty = int(parts[1].strip())
                    price = float(parts[2].strip()) if len(parts) >= 3 else 0.0

                    position = Position(
                        stock_code=code,
                        stock_name="",  # 名称可选
                        available_qty=qty,
                        current_price=price
                    )
                    positions.append(position)
                    print(f"  ✅ 已添加: {code} - {qty}股 @ {price if price > 0 else '市价'}")
                else:
                    print("  ❌ 格式错误，请重新输入")
            except ValueError as e:
                print(f"  ❌ 输入错误: {e}，请重新输入")

        print(f"\n共添加 {len(positions)} 个持仓")
        return positions

    def get_positions_from_ocr(self, quick_mode: bool = True) -> list:
        """
        使用OCR从截图获取持仓列表
        需要 ocr_positions.py 模块

        参数:
            quick_mode: 是否使用快速模式（固定坐标）

        返回: Position 对象列表
        """
        try:
            from ocr_positions import PositionOCR

            print("\n" + "="*60)
            print("📸 OCR持仓识别")
            print("="*60)

            ocr = PositionOCR()

            if quick_mode:
                # 快速模式：直接使用固定坐标截图
                screenshot_path = ocr.capture_position_area(use_calibrated_region=True)
                if screenshot_path:
                    positions = ocr.extract_positions_with_ocr(screenshot_path)
                    if positions:
                        return positions
                    else:
                        print("\n⚠️  OCR识别失败，切换到交互式模式")

            # 交互式模式
            positions = ocr.get_positions_interactive()
            return positions

        except ImportError:
            print("❌ 无法导入OCR模块，切换到手动输入")
            return self.get_positions_from_input()
        except Exception as e:
            print(f"❌ OCR识别失败: {e}")
            print("切换到手动输入...")
            return self.get_positions_from_input()

    def get_orders_from_ocr(self, quick_mode: bool = True) -> list:
        """
        使用OCR从截图获取委托列表
        需要 ocr_orders.py 模块

        参数:
            quick_mode: 是否使用快速模式（固定坐标）

        返回: Order 对象列表
        """
        try:
            from ocr_orders import OrderOCR

            print("\n" + "="*60)
            print("📸 OCR委托识别")
            print("="*60)

            ocr = OrderOCR()

            if quick_mode:
                # 快速模式：直接使用固定坐标截图
                screenshot_path = ocr.capture_order_area(use_calibrated_region=True)
                if screenshot_path:
                    orders = ocr.extract_orders_with_ocr(screenshot_path)
                    if orders:
                        return orders
                    else:
                        print("\n⚠️  OCR识别失败，切换到交互式模式")

            # 交互式模式
            orders = ocr.get_orders_interactive()
            return orders

        except ImportError:
            print("❌ 无法导入OCR模块")
            return []
        except Exception as e:
            print(f"❌ OCR识别失败: {e}")
            return []

    def smart_sell(self, confirm: bool = False) -> bool:
        """
        智能卖出功能 - 自动识别持仓并让用户选择卖出

        参数:
            confirm: 是否自动确认订单（谨慎使用！）

        返回:
            是否执行成功
        """
        print("\n" + "="*70)
        print("🎯 智能卖出 - OCR识别持仓")
        print("="*70)

        # 1. 获取持仓列表
        print("\n正在识别当前持仓...")
        positions = self.get_positions_from_ocr(quick_mode=True)

        if not positions:
            print("\n❌ 未获取到持仓信息")
            return False

        # 2. 显示持仓列表
        print("\n" + "="*70)
        print("📊 当前持仓列表")
        print("="*70)
        for i, pos in enumerate(positions, 1):
            print(f"{i}. {pos.stock_code} ({pos.stock_name or '未知'})")
            print(f"   可用数量: {pos.available_qty}股")
            print(f"   当前价格: {pos.current_price}")
            print()
        print("="*70)

        # 3. 让用户选择要卖出的股票
        print("\n请选择要卖出的股票：")
        print("提示: 输入序号，或输入 'a' 全部卖出，'q' 取消")

        choice = input("\n请选择 [1-{}, a, q]: ".format(len(positions))).strip().lower()

        if choice == 'q':
            print("已取消")
            return False

        selected_positions = []

        if choice == 'a':
            # 全部卖出
            selected_positions = positions
            print(f"\n已选择全部卖出 ({len(positions)} 只股票)")
        else:
            # 单个卖出
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(positions):
                    selected_positions = [positions[idx]]
                    print(f"\n已选择: {positions[idx].stock_code}")
                else:
                    print("❌ 无效的序号")
                    return False
            except ValueError:
                print("❌ 无效的输入")
                return False

        # 4. 对每个选中的股票，询问卖出数量和价格
        for pos in selected_positions:
            print("\n" + "─"*70)
            print(f"📤 准备卖出: {pos.stock_code} ({pos.stock_name or '未知'})")
            print(f"   可用数量: {pos.available_qty}股")
            print(f"   当前价格: {pos.current_price}")
            print("─"*70)

            # 询问卖出数量
            qty_input = input(f"\n卖出数量 (按 Enter 全部卖出 {pos.available_qty}股): ").strip()
            if qty_input:
                try:
                    quantity = int(qty_input)
                    if quantity <= 0 or quantity > pos.available_qty:
                        print(f"❌ 数量无效，必须在 1-{pos.available_qty} 之间")
                        continue
                except ValueError:
                    print("❌ 数量格式错误")
                    continue
            else:
                quantity = pos.available_qty

            # 询问卖出价格
            price_input = input(f"卖出价格 (按 Enter 使用当前价 {pos.current_price}): ").strip()
            if price_input:
                try:
                    price = float(price_input)
                except ValueError:
                    print("❌ 价格格式错误")
                    continue
            else:
                price = pos.current_price

            # 确认信息
            print("\n✅ 卖出信息确认:")
            print(f"   股票代码: {pos.stock_code}")
            print(f"   卖出数量: {quantity}股")
            print(f"   卖出价格: {price}")

            if not confirm:
                confirm_input = input("\n确认卖出？(y/n): ").strip().lower()
                if confirm_input != 'y':
                    print("已跳过")
                    continue

            # 执行卖出
            print(f"\n正在卖出 {pos.stock_code}...")
            success = self.sell(pos.stock_code, price, quantity, confirm=confirm)

            if success:
                print(f"✅ {pos.stock_code} 卖出成功")
            else:
                print(f"❌ {pos.stock_code} 卖出失败")

            # 暂停一下，避免操作太快
            time.sleep(1)

        print("\n" + "="*70)
        print("✅ 智能卖出操作完成")
        print("="*70)

        return True

    def clear_all_positions(self, positions: list = None, confirm: bool = False,
                           use_market_price: bool = False, use_ocr: bool = False) -> bool:
        """
        清仓操作 - 卖出所有持仓股票

        参数:
            positions: Position 对象列表，如果为 None 则从用户输入/OCR获取
            confirm: 是否自动确认每笔订单（谨慎使用！）
            use_market_price: 是否使用市价（当前价的某个偏移）
            use_ocr: 是否使用OCR识别持仓（需要截图）

        返回:
            是否全部执行成功
        """
        print("\n" + "="*70)
        print("⚠️  清仓操作")
        print("="*70)

        # 如果没有提供持仓列表，从用户输入或OCR获取
        if positions is None:
            if use_ocr:
                positions = self.get_positions_from_ocr()
            else:
                # 询问用户选择输入方式
                print("\n选择持仓信息输入方式：")
                print("1. 手动输入")
                print("2. OCR识别（从截图）")
                choice = input("请选择 [1-2] (默认1): ").strip() or "1"

                if choice == "2":
                    positions = self.get_positions_from_ocr()
                else:
                    positions = self.get_positions_from_input()

        if not positions:
            print("没有持仓信息，操作取消")
            return False

        # 显示清仓计划
        print("\n" + "="*70)
        print("📋 清仓计划：")
        print("="*70)
        for i, pos in enumerate(positions, 1):
            price_str = f"{pos.current_price}" if pos.current_price > 0 else "市价"
            print(f"{i}. {pos.stock_code} - 卖出 {pos.available_qty} 股 @ {price_str}")
        print("="*70)

        # 二次确认
        if not confirm:
            confirm_input = input("\n⚠️  确认要清仓吗？(输入 'YES' 继续): ").strip()
            if confirm_input != 'YES':
                print("操作已取消")
                return False

        # 执行清仓
        print("\n开始执行清仓操作...")
        success_count = 0
        failed_count = 0

        for i, pos in enumerate(positions, 1):
            print(f"\n[{i}/{len(positions)}] 处理 {pos.stock_code}...")

            # 确定卖出价格
            if use_market_price or pos.current_price <= 0:
                # 这里可以接入行情接口获取当前价
                # 暂时使用一个占位价格，用户需要在界面确认
                sell_price = 0.01  # 占位价格，实际会被同花顺自动填充
                print(f"  → 使用自动价格（同花顺会自动填充当前价）")
            else:
                sell_price = pos.current_price

            try:
                # 执行卖出
                success = self.sell(
                    code=pos.stock_code,
                    price=sell_price,
                    quantity=pos.available_qty,
                    confirm=confirm
                )

                if success:
                    success_count += 1
                    print(f"  ✅ {pos.stock_code} 卖出指令已发送")
                else:
                    failed_count += 1
                    print(f"  ❌ {pos.stock_code} 卖出失败")

                # 每笔订单之间间隔
                if i < len(positions):
                    time.sleep(2)  # 间隔2秒

            except Exception as e:
                failed_count += 1
                print(f"  ❌ {pos.stock_code} 异常: {e}")

        # 总结
        print("\n" + "="*70)
        print("📊 清仓操作完成")
        print("="*70)
        print(f"成功: {success_count} 笔")
        print(f"失败: {failed_count} 笔")
        print(f"总计: {len(positions)} 笔")
        print("="*70)

        return failed_count == 0

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
            "确认按钮",
            "模态对话框确认按钮"  # 新增
        ]

        for label in labels:
            print(f"\n请将鼠标移动到【{label}】位置，然后在终端按 Enter...")
            if label == "模态对话框确认按钮":
                print("   提示：需要先点击'确认按钮'让对话框弹出，然后移动鼠标到对话框的确认按钮")
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
            "确认按钮": "confirm_button",
            "模态对话框确认按钮": "modal_confirm_button"  # 新增
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
║  5. 智能卖出（OCR识别持仓）⭐                              ║
║  6. 批量清仓                                              ║
║  7. 查看委托（OCR识别）⭐                                  ║
║  0. 退出                                                  ║
╚══════════════════════════════════════════════════════════╝
    """)

    while True:
        choice = input("\n请选择功能 [0-7]: ").strip()

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

        elif choice == '5':
            # 智能卖出 - OCR识别持仓后选择卖出
            trader.smart_sell(confirm=True)

        elif choice == '6':
            # 批量清仓
            trader.clear_all_positions(confirm=True)

        elif choice == '7':
            # 查看委托列表 - OCR识别
            orders = trader.get_orders_from_ocr(quick_mode=True)
            if orders:
                print("\n" + "="*70)
                print("📋 当前委托列表")
                print("="*70)
                for i, order in enumerate(orders, 1):
                    print(f"{i}. {order.stock_code} {order.direction}")
                    print(f"   价格: {order.price}  数量: {order.quantity}")
                    print(f"   已成交: {order.traded_quantity}  状态: {order.status}")
                    print()
                print("="*70)
            else:
                print("\n暂无委托或识别失败")

        else:
            print("无效选择，请重试")


if __name__ == "__main__":
    main()