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
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# 配置日志
logger = logging.getLogger(__name__)
if not logger.handlers:
    # 如果没有配置过，添加控制台处理器
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

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
    cost_price: float = 0.0  # 成本价（可选，默认为0）

    def calculate_position_value(self) -> float:
        """计算持仓市值"""
        return self.current_price * self.available_qty if self.current_price > 0 else 0.0

    def calculate_profit_loss(self) -> float:
        """计算盈亏金额"""
        if self.current_price > 0 and self.cost_price > 0:
            return (self.current_price - self.cost_price) * self.available_qty
        return 0.0

    def calculate_profit_loss_ratio(self) -> float:
        """计算盈亏比例"""
        if self.cost_price > 0 and self.current_price > 0:
            return (self.current_price - self.cost_price) / self.cost_price
        return 0.0


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

            # 登录相关坐标（需要校准）
            'captcha_image_region': (1194, 645, 66, 21),

            'login_button': (178, 265),
            'password_input': (1108, 578),
            'captcha_input': (1109, 670),
            'login_confirm_button': (1120, 700),

            # 状态检测相关坐标（用于自动恢复功能）
            # Tab相关
            'trade_tab': (70, 408),                      # 交易Tab点击位置（与buy_button同位置）
            'trade_tab_region': (250, 70, 200, 40),      # 交易Tab OCR识别区域（包含"买入"/"卖出"等文字）

            # 弹窗相关
            'popup_region': (923, 470, 254, 236),        # 弹窗内容区域（窗口中央）
            'popup_confirm_button': (975, 656),          # 弹窗确定按钮位置

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

    def get_ths_process_name(self) -> str:
        """
        获取同花顺进程的正确名称（支持多种可能的名称）

        返回:
            str: 找到的进程名称，如果都未找到则返回默认的"同花顺"
        """
        possible_names = [
            "同花顺",
            "同花顺Mac",
            "同花顺证券",
            "THS",
            "同花顺-Mac",
            "同花顺mac版",
        ]

        for name in possible_names:
            script = f'''
            tell application "System Events"
                return exists process "{name}"
            end tell
            '''
            try:
                result = subprocess.run(
                    ['osascript', '-e', script],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.stdout.strip() == "true":
                    print(f"  ✅ 找到进程: {name}")
                    return name
            except:
                continue

        print("  ⚠️  未找到同花顺进程（使用默认名称）")
        return "同花顺"  # 默认值

    def activate_ths_window(self, force_update_position: bool = False) -> bool:
        """
        激活同花顺窗口到前台并更新窗口位置

        Args:
            force_update_position: 是否强制更新窗口位置
                                  False: 只在 window_pos 为 None 时更新（默认，避免重复获取）
                                  True: 总是更新窗口位置
        """
        script = f'''
        tell application "{self.app_name}"
            activate
        end tell
        '''
        try:
            subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
            time.sleep(0.5)  # 等待窗口激活

            # 更新窗口位置（条件性）
            if self.use_relative_coords:
                # 只在需要时更新窗口位置，避免重复获取导致的问题
                should_update = force_update_position or (self.window_pos is None)

                if should_update:
                    logger.debug("  → 获取窗口位置...")
                    self.window_pos = self.get_window_position()
                    if self.window_pos:
                        logger.info(f"  → 窗口位置: ({self.window_pos[0]}, {self.window_pos[1]}), 大小: ({self.window_pos[2]}x{self.window_pos[3]})")
                    else:
                        logger.warning("  ⚠️  无法获取窗口位置，将使用绝对坐标")
                else:
                    logger.debug(f"  → 使用缓存的窗口位置: {self.window_pos}")

            return True
        except subprocess.CalledProcessError:
            logger.error(f"错误：无法激活 {self.app_name} 窗口，请确保应用已打开")
            return False

    def get_window_position(self) -> Optional[Tuple[int, int, int, int]]:
        """
        获取同花顺窗口位置和大小
        返回：(x, y, width, height) 或 None
        """
        # 使用更健壮的窗口获取方法：先获取所有窗口，再选择主窗口
        # 这样即使有弹窗也不会失败
        script = f'''
        tell application "System Events"
            tell process "{self.app_name}"
                set windowList to every window
                if (count of windowList) > 0 then
                    -- 找最大的窗口（通常是主窗口）
                    set maxArea to 0
                    set mainWindow to item 1 of windowList
                    repeat with w in windowList
                        set wSize to size of w
                        set wArea to (item 1 of wSize) * (item 2 of wSize)
                        if wArea > maxArea then
                            set maxArea to wArea
                            set mainWindow to w
                        end if
                    end repeat

                    set windowPosition to position of mainWindow
                    set windowSize to size of mainWindow
                    return {{item 1 of windowPosition, item 2 of windowPosition, item 1 of windowSize, item 2 of windowSize}}
                else
                    error "没有找到窗口"
                end if
            end tell
        end tell
        '''
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                check=True, capture_output=True, text=True,
                timeout=5
            )
            # 解析返回的坐标
            coords = result.stdout.strip().split(', ')
            return tuple(int(c) for c in coords)
        except subprocess.CalledProcessError as e:
            # AppleScript执行错误，输出详细错误信息
            error_msg = e.stderr if e.stderr else "未知错误"
            print(f"  ❌ AppleScript执行失败: {error_msg}")

            # 检查进程是否存在
            check_script = f'''
            tell application "System Events"
                set processList to name of every process
                return processList contains "{self.app_name}"
            end tell
            '''
            try:
                check_result = subprocess.run(
                    ['osascript', '-e', check_script],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                process_exists = check_result.stdout.strip()
                print(f"  → 进程 '{self.app_name}' 是否存在: {process_exists}")

                if process_exists == "false":
                    print(f"  💡 提示: 进程名称可能不正确，尝试使用 get_ths_process_name() 方法")
                    # 尝试自动检测进程名称
                    detected_name = self.get_ths_process_name()
                    if detected_name != self.app_name:
                        print(f"  🔄 自动切换进程名称: {self.app_name} -> {detected_name}")
                        self.app_name = detected_name
                        # 重试一次
                        return self.get_window_position()
            except Exception as check_error:
                print(f"  → 进程检查失败: {check_error}")

            return None
        except subprocess.TimeoutExpired:
            print(f"  ❌ AppleScript执行超时（可能进程无响应）")
            return None
        except Exception as e:
            print(f"  ❌ 获取窗口位置失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_absolute_coords(self, relative_x: int, relative_y: int) -> Tuple[int, int]:
        """
        将相对坐标转换为绝对坐标

        注意：必须先调用 activate_ths_window() 来初始化 window_pos

        参数：
            relative_x: 相对于窗口左上角的x坐标
            relative_y: 相对于窗口左上角的y坐标

        返回：
            (abs_x, abs_y): 屏幕绝对坐标

        异常：
            RuntimeError: 当启用相对坐标模式但窗口位置未初始化时
        """
        if not self.use_relative_coords:
            return (relative_x, relative_y)

        # 如果窗口位置未缓存，尝试获取一次
        # 注意：应该在activate_ths_window()时获取，这里只是fallback
        if self.window_pos is None:
            logger.warning("  ⚠️  窗口位置未初始化，尝试获取...")
            self.window_pos = self.get_window_position()

        # 如果仍然无法获取窗口位置，报错（不要永久关闭相对坐标模式）
        if self.window_pos is None:
            error_msg = (
                "❌ 无法获取窗口位置！相对坐标转换失败。\n"
                f"   相对坐标: ({relative_x}, {relative_y})\n"
                "   可能原因：\n"
                "   1. 未调用 activate_ths_window() 初始化窗口位置\n"
                "   2. 同花顺应用未打开或窗口不可见\n"
                "   3. 缺少辅助功能权限\n"
                "   建议：在调用任何操作前，先确保 activate_ths_window() 成功"
            )
            logger.error(error_msg)
            # 不要关闭相对坐标模式，而是抛出异常
            raise RuntimeError("窗口位置未初始化，无法转换坐标。请先调用 activate_ths_window()")

        win_x, win_y, _, _ = self.window_pos
        abs_x, abs_y = win_x + relative_x, win_y + relative_y

        # 调试日志（可选）
        if logger.level <= 10:  # DEBUG level
            logger.debug(f"坐标转换: 窗口({win_x}, {win_y}) + 相对({relative_x}, {relative_y}) = 绝对({abs_x}, {abs_y})")

        return (abs_x, abs_y)

    def click_at(self, x: int, y: int, clicks: int = 1, debug: bool = False):
        """
        在指定坐标点击
        如果启用相对坐标模式，会自动转换为绝对坐标
        """
        # 确保输入坐标是整数
        x, y = int(x), int(y)
        abs_x, abs_y = self.get_absolute_coords(x, y)

        if debug or self.use_relative_coords:
            logger.info(f"  → 点击位置: ({abs_x}, {abs_y})")
            if self.use_relative_coords and self.window_pos:
                logger.info(f"     (窗口位置: {self.window_pos[0]}, {self.window_pos[1]}, 相对坐标: {x}, {y})")

        pyautogui.click(int(abs_x), int(abs_y), clicks=clicks)
        time.sleep(0.1)

    def clear_and_type(self, x: int, y: int, text: str):
        """
        点击输入框，清空内容，输入新文本
        处理同花顺自动填充的情况
        """
        # 确保坐标是整数
        x, y = int(x), int(y)
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

    def input_text_via_clipboard(self, x: int, y: int, text: str, verify: bool = False):
        """
        通过剪贴板输入文本（支持中文）
        处理同花顺自动填充的情况

        参数:
            x: 输入框X坐标
            y: 输入框Y坐标
            text: 要输入的文本
            verify: 是否验证输入成功（通过截图OCR验证）
        """
        import subprocess

        # 确保坐标是整数
        x, y = int(x), int(y)

        # 增加重试次数
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # 单击输入框获取焦点
                self.click_at(x, y, clicks=1)
                time.sleep(0.5)  # 增加等待时间，确保焦点切换

                # 再次点击确保焦点
                self.click_at(x, y, clicks=1)
                time.sleep(0.3)

                # 多次清空以确保删除自动填充的内容
                for _ in range(3):  # 增加到3次
                    pyautogui.hotkey('command', 'a')
                    time.sleep(0.1)
                    pyautogui.press('delete')
                    time.sleep(0.1)

                # 最后一次清空
                pyautogui.hotkey('command', 'a')
                time.sleep(0.05)
                pyautogui.press('delete')
                time.sleep(0.2)  # 增加等待时间

                # 将文本复制到剪贴板
                process = subprocess.Popen(
                    ['pbcopy'],
                    stdin=subprocess.PIPE
                )
                process.communicate(text.encode('utf-8'))
                time.sleep(0.1)  # 等待剪贴板写入

                # 粘贴
                pyautogui.hotkey('command', 'v')
                time.sleep(0.3)  # 增加等待时间

                # 验证输入（可选）
                if verify:
                    # 通过截图验证输入是否成功
                    # 这里简化处理，假设成功
                    pass

                print(f"  ✅ 文本输入成功 (尝试 {attempt + 1}/{max_attempts})")
                return True

            except Exception as e:
                print(f"  ⚠️  文本输入失败 (尝试 {attempt + 1}/{max_attempts}): {e}")
                if attempt < max_attempts - 1:
                    time.sleep(0.5)
                    continue
                else:
                    print(f"  ❌ 文本输入最终失败")
                    return False

        return False

    def input_password(self, x: int, y: int, password: str, debug_mode: bool = False) -> bool:
        """
        输入密码（专用方法，增强可靠性）

        参数:
            x: 密码框X坐标
            y: 密码框Y坐标
            password: 密码
            debug_mode: 是否启用调试模式

        返回:
            是否输入成功
        """
        print("  → 正在输入密码...")

        # 确保坐标是整数
        x, y = int(x), int(y)

        # 截图密码框位置（调试用）
        if debug_mode:
            abs_x, abs_y = self.get_absolute_coords(x, y)
            self._debug_screenshot_click_position(
                abs_x, abs_y,
                "./debug_password_input_position.png"
            )

        success = False

        # 方法1：直接输入（对密码框更可靠）
        if password.isascii():
            print("  → 使用直接输入方式（推荐用于密码框）...")
            try:
                # 点击密码框，确保获取焦点
                print("  → 点击密码框...")
                self.click_at(x, y, clicks=1)
                time.sleep(0.2)

                # 再次点击确保焦点
                self.click_at(x, y, clicks=1)
                time.sleep(0.3)

                # 清空现有内容（简单处理）
                print("  → 清空密码框...")
                pyautogui.hotkey('command', 'a')
                time.sleep(0.2)
                pyautogui.press('delete')
                time.sleep(0.3)

                # 直接输入密码（字符间隔加大）
                print(f"  → 输入密码（{len(password)}位）...")
                pyautogui.typewrite(password, interval=0.15)  # 增加间隔到0.15秒
                time.sleep(0.5)  # 输入完成后等待

                print("  ✅ 密码输入成功（直接输入方式）")
                success = True

            except Exception as e:
                print(f"  ❌ 直接输入失败: {e}")
                success = False
        else:
            # 方法2：非ASCII密码使用剪贴板
            print("  → 密码包含非ASCII字符，使用剪贴板方式...")
            success = self.input_text_via_clipboard(x, y, password)

        # 成功后，移除密码框焦点，避免后续输入到密码框
        if success:
            print("  → 移除密码框焦点...")
            # 按 Tab 键移动到下一个输入框（通常是验证码框）
            pyautogui.press('tab')
            time.sleep(0.3)

        return success

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

        try:
            # 点击持仓标签
            if 'position_tab' in self.coords:
                self.click_at(*self.coords['position_tab'])
                time.sleep(0.5)  # 等待标签页切换
                print("✅ 已切换到持仓标签页")
            else:
                print("⚠️  未配置持仓标签坐标，跳过切换")
                print("   提示：运行校准工具添加 'position_tab' 坐标")
        except Exception as e:
            print(f"⚠️  切换标签页失败: {e}")
            print("   继续执行，可能界面已经在持仓页面")

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

    def place_order(self, order: TradeOrder, confirm: bool = True) -> bool:
        """
        执行下单操作

        参数：
            order: 交易订单
            confirm: 是否自动确认（谨慎使用！）

        返回：
            是否执行成功
        """
        logger.info(f"\n{'='*50}")
        logger.info(f"准备下单: {order.direction.value} {order.stock_code}")
        logger.info(f"价格: {order.price}, 数量: {order.quantity}")
        logger.info(f"{'='*50}")

        # 1. 激活同花顺窗口
        #    注意：force_update_position=False 表示如果 window_pos 已缓存，则不重新获取
        #    这避免了重复获取窗口位置可能导致的问题（如获取到弹窗而非主窗口）
        if not self.activate_ths_window(force_update_position=False):
            logger.error("❌ 无法激活同花顺窗口")
            return False

        # 2. 验证窗口位置已正确获取（防御性检查）
        if self.use_relative_coords and self.window_pos is None:
            logger.error("❌ 窗口位置未正确初始化，无法进行坐标转换")
            logger.error("   建议：检查同花顺应用是否正常打开，或尝试重启应用")
            return False

        logger.info(f"✅ 窗口位置: {self.window_pos}")

        # 3. 切换买入/卖出方向
        logger.info("切换交易方向...")
        self.switch_direction(order.direction)

        # 4. 输入股票代码
        logger.info(f"输入股票代码: {order.stock_code}")
        self.input_stock_code(order.stock_code)

        # 5. 输入价格
        logger.info(f"输入价格: {order.price}")
        self.input_price(order.price)

        # 6. 输入数量
        logger.info(f"输入数量: {order.quantity}")
        self.input_quantity(order.quantity)

        # 7. 确认下单
        if confirm:
            logger.info("⚠️  正在确认下单...")
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

    def sell(self, code: str, price: float, quantity: int, confirm: bool = True) -> bool:
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

    def check_login_status(self, auto_detect: bool = True) -> bool:
        """
        检查是否已登录交易账号

        检测策略：
        1. 如果未配置login_button坐标，假设已登录
        2. 截取登录按钮区域的截图
        3. 优先使用OCR识别截图中的文字
        4. 如果识别到"登录"、"login"等文字，说明未登录
        5. 如果OCR失败或auto_detect=False，降级到人工确认
        6. 返回 True（已登录）或 False（未登录）

        参数:
            auto_detect: 是否自动检测（使用OCR），False则人工确认

        返回:
            是否已登录
        """
        print("\n" + "="*70)
        print("🔍 检测登录状态")
        print("="*70)

        # 如果没有配置登录按钮坐标，假设已登录
        if self.coords.get('login_button') is None:
            print("⚠️  未配置登录按钮坐标，无法检测登录状态")
            print("   假设已登录，如需自动登录请先校准登录相关坐标")
            return True

        # 激活窗口
        print("步骤 1/3: 激活同花顺窗口...")
        if not self.activate_ths_window():
            print("❌ 无法激活同花顺窗口")
            return False

        try:
            # 获取登录按钮附近的小区域截图
            print("\n步骤 2/3: 截取登录按钮区域...")
            login_btn_x, login_btn_y = self.coords['login_button']
            abs_x, abs_y = self.get_absolute_coords(login_btn_x, login_btn_y)

            # 截取按钮区域（假设按钮大小约 100x40）
            region = (int(abs_x - 50), int(abs_y - 20), 150, 50)
            screenshot = pyautogui.screenshot(region=region)

            # 保存临时截图用于调试
            temp_screenshot_path = "/tmp/ths_login_button.png"
            screenshot.save(temp_screenshot_path)
            print(f"   ✅ 已保存截图: {temp_screenshot_path}")
            print(f"   截图区域: {region}")

            # 尝试OCR识别
            if auto_detect:
                print("\n步骤 3/3: 使用OCR识别按钮文字...")
                is_logged_in = self._detect_login_status_with_ocr(screenshot, temp_screenshot_path)

                if is_logged_in is not None:
                    # OCR识别成功
                    status = "已登录" if is_logged_in else "未登录"
                    print(f"✅ 登录状态检测完成: {status}")
                    return is_logged_in
                else:
                    # OCR识别失败，降级到人工确认
                    print("⚠️  OCR识别失败，降级到人工确认...")
                    return self._manual_login_status_check(temp_screenshot_path)
            else:
                # 不使用自动检测，直接人工确认
                print("\n步骤 3/3: 人工确认登录状态...")
                return self._manual_login_status_check(temp_screenshot_path)

        except Exception as e:
            print(f"\n❌ 登录状态检测失败: {e}")
            import traceback
            traceback.print_exc()
            print("   假设已登录")
            return True

    def _detect_login_button_by_color(self, screenshot) -> Optional[bool]:
        """
        通过颜色检测登录按钮（PRIMARY METHOD - 最可靠）

        原理：
        - 蓝色"立即登录"按钮 = 未登录
        - 灰色/无明显蓝色按钮 = 已登录

        参数:
            screenshot: PIL Image对象

        返回:
            True（已登录）、False（未登录）、None（检测失败）
        """
        try:
            import numpy as np
        except ImportError:
            # numpy未安装，静默返回None
            return None

        try:
            # Convert to numpy array
            img_array = np.array(screenshot.convert('RGB'))

            # ====================================================
            # 颜色范围校准说明
            # ====================================================
            # 通过 analyze_button_color.py 分析实际截图得到：
            #
            # 1. 无遮罩状态（正常蓝色按钮）：
            #    RGB(50, 140, 246) - 鲜艳的蓝色
            #
            # 2. 有半透明遮罩状态（实际测量）：
            #    主色调1: RGB(122, 158, 201) 占 34%
            #    主色调2: RGB(204, 204, 204) 占 50% (灰色背景)
            #
            # 3. 被遮罩覆盖的按钮特征：
            #    - R范围: 122-170
            #    - G范围: 158-185
            #    - B范围: 200-204
            #    - 整体偏浅蓝灰色
            # ====================================================

            # 范围1: 深蓝色 - 无遮罩的正常蓝色按钮
            blue_lower_dark = np.array([20, 100, 200])
            blue_upper_dark = np.array([100, 180, 255])

            # 范围2: 浅蓝色 - 有半透明遮罩的按钮
            # 根据实际测量 RGB(122, 158, 201) 设定范围
            blue_lower_light = np.array([100, 140, 195])   # 下界降低到包含 RGB(122, 158, 201)
            blue_upper_light = np.array([180, 200, 210])   # 上界调整到按钮实际颜色范围

            # 创建蓝色像素掩码 (两种蓝色范围的并集)
            mask_dark = np.all((img_array >= blue_lower_dark) & (img_array <= blue_upper_dark), axis=-1)
            mask_light = np.all((img_array >= blue_lower_light) & (img_array <= blue_upper_light), axis=-1)
            mask = mask_dark | mask_light

            # 计算蓝色像素占比
            blue_percentage = float(np.sum(mask)) / float(mask.size)
            dark_percentage = float(np.sum(mask_dark)) / float(mask.size)
            light_percentage = float(np.sum(mask_light)) / float(mask.size)

            print(f"   蓝色像素占比: {blue_percentage:.2%} (深蓝: {dark_percentage:.2%}, 浅蓝: {light_percentage:.2%})")

            # 阈值说明：
            # - 正常蓝色按钮约占 20-35%
            # - 有遮罩的按钮约占 25-40% (实测34%)
            # - 设置阈值为 15% 以确保检测到
            if blue_percentage > 0.15:
                print(f"   ✓ 检测到蓝色登录按钮，状态: 未登录")
                return False
            else:
                print(f"   ✓ 未检测到蓝色按钮，状态: 已登录")
                return True

        except Exception as e:
            print(f"   ⚠️  颜色检测失败: {e}")
            return None

    def _detect_login_by_template(self, screenshot_path: str) -> Optional[bool]:
        """
        使用OpenCV模板匹配检测登录按钮（SECONDARY METHOD）

        需要预先保存一个登录按钮模板图片到 templates/login_button.png

        参数:
            screenshot_path: 截图保存路径

        返回:
            True（已登录）、False（未登录）、None（检测失败或模板不存在）
        """
        try:
            import cv2
            import numpy as np
        except ImportError:
            # OpenCV是可选依赖，不打印警告
            return None

        try:
            # 模板路径
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'login_button.png')

            if not os.path.exists(template_path):
                # 模板不存在，静默返回None
                return None

            # 读取截图和模板
            img = cv2.imread(screenshot_path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            template = cv2.imread(template_path, 0)

            # 模板匹配
            result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            print(f"   模板匹配相似度: {max_val:.2f}")

            # 相似度阈值 70%
            if max_val > 0.7:
                print(f"   ✓ 检测到登录按钮，状态: 未登录")
                return False
            else:
                print(f"   ✓ 未检测到登录按钮，状态: 已登录")
                return True

        except Exception as e:
            print(f"   ⚠️  模板匹配失败: {e}")
            return None

    def _detect_login_status_with_ocr(self, screenshot, screenshot_path: str) -> Optional[bool]:
        """
        使用多种方法检测登录状态（CASCADE APPROACH）

        优先级顺序：
        1. 颜色检测（最快最可靠） - PRIMARY
        2. 模板匹配（需要OpenCV）- SECONDARY
        3. OCR识别（最后手段）- FALLBACK

        参数:
            screenshot: PIL Image对象
            screenshot_path: 截图保存路径

        返回:
            True（已登录）、False（未登录）、None（检测失败）
        """
        print(f"   使用多方法级联检测...")

        # ====== 方法1: 颜色检测（PRIMARY - 最可靠）======
        print(f"\n   → 方法1: 颜色检测...")
        color_result = self._detect_login_button_by_color(screenshot)
        if color_result is not None:
            print(f"   ✅ 颜色检测成功")
            return color_result

        # ====== 方法2: 模板匹配（SECONDARY）======
        print(f"\n   → 方法2: 模板匹配...")
        template_result = self._detect_login_by_template(screenshot_path)
        if template_result is not None:
            print(f"   ✅ 模板匹配成功")
            return template_result

        # ====== 方法3: OCR识别（FALLBACK）======
        print(f"\n   → 方法3: OCR识别...")

        try:
            import pytesseract
            from PIL import Image, ImageEnhance, ImageOps
        except ImportError:
            print("   ⚠️  未安装OCR依赖，无法自动检测")
            print("   提示: pip install pytesseract pillow")
            print("   提示: brew install tesseract tesseract-lang")
            return None

        try:
            # 登录关键词（扩展版 + 常见OCR误识别）
            login_keywords = [
                # 完整词组
                '登录', '登陆', '立即登录', '立即登陆',
                'login', 'sign in', 'signin', 'log in',
                # 单字（可能只识别出部分）
                '登', '录', '陆', '即', '立',
                # 常见OCR错误识别
                '党录', '党陆', '一一', '立党',  # "立即"的误识别
                '壹即', '壹', '即刻',  # "立即"的其他误识别
            ]

            # ====== 准备多种图像预处理策略 ======
            preprocessed_images = []

            # 策略1: 颜色反转 + 转灰度 + 放大（针对蓝底白字按钮）
            try:
                inverted = ImageOps.invert(screenshot.convert('RGB'))
                # 转换为灰度图（更适合OCR）
                inverted_gray = inverted.convert('L')
                if screenshot.width < 200 or screenshot.height < 60:
                    scale = 3
                    inverted_gray = inverted_gray.resize(
                        (screenshot.width * scale, screenshot.height * scale),
                        Image.Resampling.LANCZOS
                    )
                preprocessed_images.append(('inverted-gray-upscaled', inverted_gray))
                # 保存调试图像
                debug_path = screenshot_path.replace('.png', '_inverted.png')
                inverted_gray.save(debug_path)
            except Exception as e:
                print(f"   预处理策略1失败: {e}")

            # 策略2: 颜色反转 + 二值化 + 放大（针对蓝底白字 → 黑底白字）
            try:
                inverted = ImageOps.invert(screenshot.convert('RGB'))
                inverted_gray = inverted.convert('L')
                # 对反转后的图像进行二值化，保持白色文字
                threshold = 150  # 提取亮色部分（文字）
                binarized = inverted_gray.point(lambda x: 255 if x > threshold else 0, mode='L')
                if screenshot.width < 200 or screenshot.height < 60:
                    scale = 4  # 增大放大倍数
                    binarized = binarized.resize(
                        (screenshot.width * scale, screenshot.height * scale),
                        Image.Resampling.LANCZOS
                    )
                preprocessed_images.append(('inv-white-on-black', binarized))
                # 保存调试图像
                debug_path = screenshot_path.replace('.png', '_binary.png')
                binarized.save(debug_path)
            except Exception as e:
                print(f"   预处理策略2失败: {e}")

            # 策略2B: 颜色反转 + 反向二值化（黑底白字 → 白底黑字，最适合OCR）
            try:
                inverted = ImageOps.invert(screenshot.convert('RGB'))
                inverted_gray = inverted.convert('L')
                # 二值化并反转：白色文字变黑色，黑色背景变白色
                threshold = 150
                binarized = inverted_gray.point(lambda x: 0 if x > threshold else 255, mode='L')
                if screenshot.width < 200 or screenshot.height < 60:
                    scale = 4
                    binarized = binarized.resize(
                        (screenshot.width * scale, screenshot.height * scale),
                        Image.Resampling.LANCZOS
                    )
                preprocessed_images.append(('inv-black-on-white', binarized))
                # 保存调试图像
                debug_path = screenshot_path.replace('.png', '_binary2.png')
                binarized.save(debug_path)
            except Exception as e:
                print(f"   预处理策略2B失败: {e}")

            # 策略3: 直接二值化原图 + 放大（提取白色文字）
            try:
                gray = screenshot.convert('L')
                threshold = 180
                binarized_orig = gray.point(lambda x: 255 if x > threshold else 0, mode='1')
                if screenshot.width < 200 or screenshot.height < 60:
                    scale = 3
                    binarized_orig = binarized_orig.resize(
                        (screenshot.width * scale, screenshot.height * scale),
                        Image.Resampling.LANCZOS
                    )
                preprocessed_images.append(('orig-binary-upscaled', binarized_orig))
            except Exception as e:
                print(f"   预处理策略3失败: {e}")

            # 策略4: 对比度增强 + 放大（原有策略改进版）
            try:
                enhancer = ImageEnhance.Contrast(screenshot)
                enhanced = enhancer.enhance(2.5)  # 增强对比度
                if screenshot.width < 200 or screenshot.height < 60:
                    scale = 3
                    enhanced = enhanced.resize(
                        (screenshot.width * scale, screenshot.height * scale),
                        Image.Resampling.LANCZOS
                    )
                preprocessed_images.append(('enhanced-upscaled', enhanced))
                # 保存调试图像
                debug_path = screenshot_path.replace('.png', '_enhanced.png')
                enhanced.save(debug_path)
            except Exception as e:
                print(f"   预处理策略4失败: {e}")

            # 策略5: 仅放大原图
            try:
                if screenshot.width < 200 or screenshot.height < 60:
                    scale = 3
                    upscaled = screenshot.resize(
                        (screenshot.width * scale, screenshot.height * scale),
                        Image.Resampling.LANCZOS
                    )
                    preprocessed_images.append(('upscaled', upscaled))
            except Exception as e:
                print(f"   预处理策略5失败: {e}")

            # ====== 准备多种OCR配置 ======
            ocr_configs = [
                # 优先尝试纯中文识别（更准确）
                ('psm7-chi', r'--oem 3 --psm 7 -l chi_sim'),        # 单行文本 + 仅中文
                ('psm8-chi', r'--oem 3 --psm 8 -l chi_sim'),        # 单词模式 + 仅中文
                ('psm6-chi', r'--oem 3 --psm 6 -l chi_sim'),        # 统一文本块 + 仅中文
                # 中英混合识别
                ('psm7-mix', r'--oem 3 --psm 7 -l chi_sim+eng'),    # 单行文本 + 中英文
                ('psm8-mix', r'--oem 3 --psm 8 -l chi_sim+eng'),    # 单词模式 + 中英文
                ('psm6-mix', r'--oem 3 --psm 6 -l chi_sim+eng'),    # 统一文本块 + 中英文
                # LSTM引擎（备选）
                ('psm7-lstm', r'--oem 1 --psm 7 -l chi_sim'),       # 单行文本 + LSTM
            ]

            # ====== 尝试所有组合 ======
            print(f"   开始多策略OCR识别...")
            best_match = None
            best_text = ""

            for img_name, img in preprocessed_images:
                for config_name, config in ocr_configs:
                    try:
                        text = pytesseract.image_to_string(img, config=config)
                        text_cleaned = text.strip().lower()

                        # 打印识别结果
                        if text.strip():
                            print(f"   → {img_name:20s} + {config_name:12s}: '{text.strip()}'")

                        # 检查是否包含登录关键词
                        for keyword in login_keywords:
                            if keyword in text_cleaned:
                                print(f"   ✓ 匹配到关键词: '{keyword}'")
                                print(f"   → 检测到登录按钮文字，状态: 未登录")
                                return False  # 早期退出优化

                        # 记录最佳匹配（用于调试）
                        if len(text_cleaned) > len(best_text):
                            best_text = text_cleaned
                            best_match = f"{img_name} + {config_name}"

                    except Exception as e:
                        # 静默失败，继续尝试其他组合
                        continue

            # 所有策略都未检测到登录关键词
            print(f"   → 未检测到登录按钮文字，状态: 已登录")
            if best_match:
                print(f"   （最佳识别: {best_match} → '{best_text}'）")
            return True

        except Exception as e:
            print(f"   ⚠️  OCR识别出错: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _manual_login_status_check(self, screenshot_path: str) -> bool:
        """
        人工确认登录状态

        参数:
            screenshot_path: 截图路径

        返回:
            是否已登录
        """
        print("\n" + "─"*70)
        print("📸 请查看登录按钮截图并手动确认")
        print("─"*70)

        # 在Mac上打开截图
        try:
            import subprocess
            subprocess.run(['open', screenshot_path], check=False)
            print(f"已打开截图: {screenshot_path}")
        except Exception as e:
            print(f"⚠️  无法打开截图: {e}")
            print(f"请手动查看截图: {screenshot_path}")

        print("\n请查看截图:")
        print("  - 如果看到'登录'按钮，说明未登录")
        print("  - 如果按钮区域是空白或其他内容，说明已登录")
        print()

        while True:
            answer = input("是否已登录？(y=已登录, n=未登录): ").strip().lower()
            if answer in ['y', 'yes', '是', 'y']:
                return True
            elif answer in ['n', 'no', '否', 'n']:
                return False
            else:
                print("⚠️  无效输入，请输入 y 或 n")

    def capture_captcha_image(self, save_path: str = "./captcha.png") -> str:
        """
        截取验证码图片并保存（增强版）

        参数:
            save_path: 保存路径

        返回:
            保存的图片路径
        """
        if self.coords.get('captcha_image_region') is None:
            print("❌ 未配置验证码图片区域坐标")
            print("   请运行: python3 calibrate_captcha_region.py")
            return ""

        try:
            region = self.coords['captcha_image_region']

            print(f"  → 验证码区域配置: {region}")

            # 如果是相对坐标，转换为绝对坐标
            if self.use_relative_coords and len(region) == 4:
                x, y, width, height = region
                abs_x, abs_y = self.get_absolute_coords(int(x), int(y))
                # 确保所有值都是整数
                abs_region = (int(abs_x), int(abs_y), int(width), int(height))
                print(f"  → 转换为绝对坐标: {abs_region}")
            else:
                # 确保所有值都是整数
                abs_region = tuple(int(v) for v in region)
                print(f"  → 使用绝对坐标: {abs_region}")

            # 验证区域参数
            if len(abs_region) != 4:
                print(f"❌ 区域参数错误: {abs_region}")
                return ""

            # 截图
            screenshot = pyautogui.screenshot(region=abs_region)
            screenshot.save(save_path)

            print(f"✅ 验证码图片已保存: {save_path}")
            print(f"   区域: {abs_region}")
            print(f"   大小: {screenshot.size}")

            return save_path

        except Exception as e:
            print(f"❌ 截取验证码失败: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def handle_captcha(self, manual: bool = False, auto_ocr: bool = True,
                      auto_confirm: bool = True) -> str:
        """
        处理验证码（智能模式：OCR优先，失败则人工输入）

        参数:
            manual: 是否强制人工输入验证码（默认False）
            auto_ocr: 是否尝试OCR自动识别（默认True）
            auto_confirm: 是否自动确认OCR结果（默认True，不需要用户确认）

        返回:
            验证码字符串
        """
        # 强制人工输入
        if manual:
            return self._manual_captcha_input()

        # 智能模式：先尝试OCR，失败则降级到人工输入
        if auto_ocr:
            print("\n" + "─"*50)
            print("🤖 验证码自动识别 (OCR)")
            print("─"*50)

            # 尝试OCR识别
            captcha = self._ocr_captcha()

            if captcha and len(captcha) >= 4:  # 验证码通常至少4位
                print(f"✅ OCR识别成功: {captcha}")

                # 自动确认模式：直接使用OCR结果
                if auto_confirm:
                    print(f"  → 自动使用OCR识别结果")
                    return captcha

                # 手动确认模式：让用户确认是否正确
                else:
                    confirm = input(f"\nOCR识别结果为: {captcha}, 是否正确? (y/n, 直接回车=是): ").strip().lower()

                    if confirm == '' or confirm == 'y':
                        return captcha
                    else:
                        print("OCR识别错误，切换到人工输入...")
                        return self._manual_captcha_input()
            else:
                print("⚠️  OCR识别失败或结果不可靠")
                print("   切换到人工输入模式...")
                return self._manual_captcha_input()

        # 默认人工输入
        return self._manual_captcha_input()

    def _manual_captcha_input(self) -> str:
        """
        人工输入验证码

        返回:
            验证码字符串
        """
        print("\n" + "─"*50)
        print("📸 验证码处理 (人工输入)")
        print("─"*50)

        # 截取验证码图片
        captcha_path = self.capture_captcha_image()
        if captcha_path:
            print(f"验证码图片已保存到: {captcha_path}")
            print("请查看图片后输入验证码")

            # 在macOS上自动打开图片
            try:
                import subprocess
                subprocess.run(['open', captcha_path], check=False)
            except:
                pass

        captcha = input("请输入验证码: ").strip()
        return captcha

    def _ocr_captcha(self) -> str:
        """
        使用OCR识别验证码

        返回:
            识别出的验证码字符串，失败返回空字符串
        """
        try:
            # 检查OCR库
            try:
                import pytesseract
                from PIL import Image, ImageEnhance, ImageFilter
            except ImportError:
                print("❌ 未安装OCR库 (pytesseract)")
                print("   安装方法: pip install pytesseract pillow")
                print("           brew install tesseract tesseract-lang")
                return ""

            # 1. 截取验证码图片
            captcha_path = self.capture_captcha_image()
            if not captcha_path:
                print("❌ 无法截取验证码图片")
                return ""

            print(f"  → 验证码图片: {captcha_path}")

            # 2. 打开图片并预处理
            image = Image.open(captcha_path)

            print(f"  → 原始图片大小: {image.size}")

            # 放大图片（提高识别率）
            # 验证码通常很小，放大4倍可以显著提高OCR准确率
            scale_factor = 4
            new_size = (image.size[0] * scale_factor, image.size[1] * scale_factor)
            image = image.resize(new_size, Image.Resampling.LANCZOS)  # 使用高质量插值
            print(f"  → 放大后大小: {image.size} (放大{scale_factor}倍)")

            # 转换为灰度图
            image = image.convert('L')

            # 增强锐度（使文字边缘更清晰）
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)

            # 增强对比度（提高识别率）
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(3.0)  # 对比度增强3.0倍

            # 自适应二值化处理（更好地处理不同亮度）
            # 使用Otsu方法自动计算最佳阈值
            import numpy as np
            img_array = np.array(image)
            threshold = np.mean(img_array)  # 使用均值作为阈值
            image = image.point(lambda x: 255 if x > threshold else 0)

            # 去除边框（关键修复）
            # 验证码外围有边框线，会干扰OCR识别
            # 策略：内缩固定边距，去除外围的边框线
            img_array = np.array(image)
            h, w = img_array.shape

            # 简单内缩法：去除外围5%的区域（通常是边框）
            # 这比检测更稳定，因为验证码尺寸相对固定
            margin_percent = 0.06  # 内缩6%
            top_crop = int(h * margin_percent)
            bottom_crop = h - int(h * margin_percent)
            left_crop = int(w * margin_percent)
            right_crop = w - int(w * margin_percent)

            # 确保裁剪后还有足够的内容
            if bottom_crop > top_crop + 20 and right_crop > left_crop + 40:
                print(f"  → 内缩去除边框: {margin_percent*100:.0f}% (上下各{top_crop}px, 左右各{int(w * margin_percent)}px)")
                img_array_cropped = img_array[top_crop:bottom_crop, left_crop:right_crop]
                image = Image.fromarray(img_array_cropped)
                print(f"  → 去除边框后大小: {image.size} (原始: {w}x{h})")

            # 去噪：去除小的噪点（可选，目前注释掉）
            # image = image.filter(ImageFilter.MedianFilter(size=3))

            # 保存预处理后的图片（调试用）
            preprocessed_path = captcha_path.replace('.png', '_preprocessed.png')
            image.save(preprocessed_path)
            print(f"  → 预处理图片: {preprocessed_path}")

            # 3. OCR识别 - 尝试多种配置和预处理
            # 存储所有原始结果（用于调试和投票）
            all_raw_results = []

            # 尝试多种预处理+OCR配置组合
            # 策略A: 当前预处理（高对比度）
            image_high_contrast = image.copy()

            # 策略B: 降低对比度预处理（避免过度增强产生噪点）
            image_low_contrast = Image.open(captcha_path)
            image_low_contrast = image_low_contrast.resize(new_size, Image.Resampling.LANCZOS)
            image_low_contrast = image_low_contrast.convert('L')
            enhancer = ImageEnhance.Sharpness(image_low_contrast)
            image_low_contrast = enhancer.enhance(1.5)  # 降低锐度
            enhancer = ImageEnhance.Contrast(image_low_contrast)
            image_low_contrast = enhancer.enhance(2.0)  # 降低对比度
            img_array_low = np.array(image_low_contrast)
            threshold_low = np.mean(img_array_low)
            image_low_contrast = image_low_contrast.point(lambda x: 255 if x > threshold_low else 0)

            # 存储有效结果（长度符合要求）
            results = []

            # 配置1：纯数字 + 高对比度预处理
            config_digits = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'
            result1a = pytesseract.image_to_string(image_high_contrast, config=config_digits).strip()
            result1a_clean = ''.join(c for c in result1a if c.isdigit())
            all_raw_results.append(result1a_clean)
            print(f"  → 尝试1a (纯数字+高对比度): '{result1a_clean}'")

            # 配置1b：纯数字 + 低对比度预处理
            result1b = pytesseract.image_to_string(image_low_contrast, config=config_digits).strip()
            result1b_clean = ''.join(c for c in result1b if c.isdigit())
            all_raw_results.append(result1b_clean)
            print(f"  → 尝试1b (纯数字+低对比度): '{result1b_clean}'")

            # 配置2：数字+字母
            config_alnum = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
            result2 = pytesseract.image_to_string(image_high_contrast, config=config_alnum).strip()
            result2_clean = ''.join(c for c in result2 if c.isalnum())
            all_raw_results.append(result2_clean)
            print(f"  → 尝试2 (数字+字母): '{result2_clean}'")

            # 配置3：单词模式
            config_word = r'--oem 3 --psm 8'
            result3 = pytesseract.image_to_string(image_high_contrast, config=config_word).strip()
            result3_clean = ''.join(c for c in result3 if c.isalnum())
            all_raw_results.append(result3_clean)
            print(f"  → 尝试3 (单词模式): '{result3_clean}'")

            # 配置4：PSM 13 (单行原始文本，无OSD)
            config_raw = r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789'
            result4 = pytesseract.image_to_string(image_low_contrast, config=config_raw).strip()
            result4_clean = ''.join(c for c in result4 if c.isdigit())
            all_raw_results.append(result4_clean)
            print(f"  → 尝试4 (原始行模式): '{result4_clean}'")

            # 配置5：PSM 6 (统一文本块) + 低对比度
            config_block = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789'
            result5 = pytesseract.image_to_string(image_low_contrast, config=config_block).strip()
            result5_clean = ''.join(c for c in result5 if c.isdigit())
            all_raw_results.append(result5_clean)
            print(f"  → 尝试5 (文本块模式): '{result5_clean}'")

            # 配置6：只使用LSTM (OEM 1) + 低对比度
            config_lstm = r'--oem 1 --psm 7 -c tessedit_char_whitelist=0123456789'
            result6 = pytesseract.image_to_string(image_low_contrast, config=config_lstm).strip()
            result6_clean = ''.join(c for c in result6 if c.isdigit())
            all_raw_results.append(result6_clean)
            print(f"  → 尝试6 (LSTM模式): '{result6_clean}'")

            # 配置7：只使用Legacy (OEM 0) + 低对比度
            try:
                config_legacy = r'--oem 0 --psm 7 -c tessedit_char_whitelist=0123456789'
                result7 = pytesseract.image_to_string(image_low_contrast, config=config_legacy).strip()
                result7_clean = ''.join(c for c in result7 if c.isdigit())
                all_raw_results.append(result7_clean)
                print(f"  → 尝试7 (Legacy模式): '{result7_clean}'")
            except Exception as e:
                # Legacy引擎可能不可用（缺少训练数据）
                print(f"  → 尝试7 (Legacy模式): 跳过（引擎不可用）")
                all_raw_results.append('')  # 添加空结果保持索引一致

            # 过滤长度并添加到候选结果
            config_names = ['digits-high', 'digits-low', 'alnum', 'word', 'raw', 'block', 'lstm', 'legacy']
            for idx, raw_result in enumerate(all_raw_results):
                if raw_result and 4 <= len(raw_result) <= 6:
                    config_name = config_names[idx] if idx < len(config_names) else f'config{idx}'
                    results.append((config_name, raw_result, len(raw_result)))

            # 加权投票机制：提取前5位进行投票
            print(f"  → 有效结果数: {len(results)}")
            if len(results) >= 2:
                # 统计每个位置上各数字出现的频率
                from collections import Counter

                # 找到最常见的长度
                length_counter = Counter([r[2] for r in results])
                most_common_length = 5#length_counter.most_common(1)[0][0]
                print(f"  → 最常见长度: {most_common_length}位")

                # 只保留最常见长度的结果
                same_length_results = [r for r in results if r[2] == most_common_length]

                if len(same_length_results) >= 2:
                    # 配置权重（基于实测准确率和算法特性）
                    config_weights = {
                        'lstm': 2.5,         # LSTM神经网络最准确（但较慢）
                        'legacy': 2.2,       # Legacy引擎准确率也很高
                        'digits-low': 2.0,   # 低对比度纯数字配置（较少噪点）
                        'raw': 1.8,          # 原始行模式
                        'block': 1.6,        # 文本块模式
                        'word': 1.5,         # 单词模式
                        'digits-high': 1.0,  # 高对比度纯数字配置基准权重
                        'alnum': 1.0,        # 数字+字母配置基准权重
                    }

                    # 加权投票
                    voted_text = ""
                    vote_details = []
                    for pos in range(most_common_length):
                        # 收集该位置的字符和配置
                        chars_with_config = []
                        for config_name, text, _ in same_length_results:
                            if pos < len(text):
                                chars_with_config.append((text[pos], config_name))

                        if chars_with_config:
                            # 加权计数
                            weighted_counter = {}
                            for char, config in chars_with_config:
                                weight = config_weights.get(config, 1.0)
                                weighted_counter[char] = weighted_counter.get(char, 0.0) + weight

                            # 选择加权得分最高的字符
                            most_common_char = max(weighted_counter.items(), key=lambda x: x[1])[0]
                            voted_text += most_common_char

                            # 记录投票详情（调试用）
                            vote_details.append({
                                'pos': pos,
                                'votes': dict(weighted_counter),
                                'winner': most_common_char
                            })

                    print(f"  → 加权投票结果: '{voted_text}'")

                    # 显示投票详情（如果有争议的位置）
                    for detail in vote_details:
                        if len(detail['votes']) > 1:
                            # 有多个候选字符，显示投票详情
                            votes_str = ', '.join([f"'{k}':{v:.1f}" for k, v in sorted(detail['votes'].items(), key=lambda x: -x[1])])
                            print(f"     位置{detail['pos']}: {votes_str} → '{detail['winner']}'")

                    results.insert(0, ('voted', voted_text, len(voted_text)))

            # 智能选择最佳结果
            captcha_text = ""
            if results:
                # 策略1: 优先使用投票结果
                voted_results = [r for r in results if r[0] == 'voted']
                if voted_results:
                    captcha_text = voted_results[0][1]
                    print(f"  → 选择策略: 使用投票结果")
                # 策略2: 优先使用纯数字配置的5位结果
                elif any(r[0].startswith('digits') and r[2] == 5 for r in results):
                    five_digit_results = [r for r in results if r[0].startswith('digits') and r[2] == 5]
                    captcha_text = five_digit_results[0][1]
                    print(f"  → 选择策略: 优先5位纯数字结果")
                # 策略3: 如果纯数字配置有结果，优先使用
                else:
                    digits_results = [r for r in results if r[0].startswith('digits')]
                    if digits_results:
                        # 优先选择5位，其次4位，最后6位
                        five_digit = [r for r in digits_results if r[2] == 5]
                        four_digit = [r for r in digits_results if r[2] == 4]
                        six_digit = [r for r in digits_results if r[2] == 6]

                        if five_digit:
                            captcha_text = five_digit[0][1]
                        elif four_digit:
                            captcha_text = four_digit[0][1]
                        elif six_digit:
                            captcha_text = six_digit[0][1]
                        else:
                            captcha_text = digits_results[0][1]
                        print(f"  → 选择策略: 优先使用纯数字结果")
                    else:
                        # 策略4: 优先选择纯数字的结果（即使来自其他配置）
                        numeric_results = [r for r in results if r[1].isdigit()]
                        if numeric_results:
                            # 优先5位
                            five_digit = [r for r in numeric_results if r[2] == 5]
                            if five_digit:
                                captcha_text = five_digit[0][1]
                            else:
                                captcha_text = max(numeric_results, key=lambda x: x[2])[1]
                            print(f"  → 选择策略: 优先选择纯数字内容")
                        else:
                            # 策略5: 选择最长的结果
                            captcha_text = max(results, key=lambda x: x[2])[1]
                            print(f"  → 选择策略: 选择最长结果")

            # 4. 清理结果
            captcha_text = captcha_text.strip()
            # 移除空格和特殊字符
            captcha_text = ''.join(c for c in captcha_text if c.isalnum())

            print(f"  → OCR识别结果: '{captcha_text}'")

            return captcha_text

        except Exception as e:
            print(f"❌ OCR识别异常: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _debug_screenshot_click_position(self, x: int, y: int, save_path: str):
        """
        截图并标记将要点击的位置（调试用）

        参数:
            x: 绝对X坐标
            y: 绝对Y坐标
            save_path: 保存路径
        """
        try:
            # 截取全屏
            screenshot = pyautogui.screenshot()

            # 在截图上标记点击位置
            from PIL import ImageDraw
            draw = ImageDraw.Draw(screenshot)

            # 绘制红色十字准线
            cross_size = 30
            draw.line([(x - cross_size, y), (x + cross_size, y)], fill='red', width=3)
            draw.line([(x, y - cross_size), (x, y + cross_size)], fill='red', width=3)

            # 绘制圆圈
            circle_radius = 20
            draw.ellipse(
                [(x - circle_radius, y - circle_radius),
                 (x + circle_radius, y + circle_radius)],
                outline='red', width=3
            )

            # 保存
            screenshot.save(save_path)
            print(f"  → 调试截图已保存: {save_path}")
            print(f"     (红色标记显示将要点击的位置)")

        except Exception as e:
            print(f"  ⚠️  调试截图失败: {e}")

    def _verify_login_dialog_opened(self) -> bool:
        """
        验证登录弹窗是否已打开

        返回:
            是否检测到登录弹窗
        """
        try:
            # 检查密码输入框是否可见
            # 如果配置了密码输入框坐标，尝试截图该区域
            if self.coords.get('password_input'):
                pwd_coords = self.coords['password_input']
                abs_x, abs_y = self.get_absolute_coords(*pwd_coords)

                # 截取密码框区域
                region = (abs_x - 50, abs_y - 20, 100, 40)
                screenshot = pyautogui.screenshot(region=region)

                # 简单判断：如果区域不是纯黑/纯白，可能是弹窗
                # 这里返回True表示可能存在，用户需要人工确认
                return True
            else:
                # 没有配置密码框坐标，无法验证
                return False

        except Exception as e:
            print(f"  ⚠️  弹窗验证失败: {e}")
            return False

    def auto_login(self, account: str = None, password: str = None,
                   captcha: str = None, manual_captcha: bool = False,
                   debug_mode: bool = True) -> bool:
        """
        自动登录流程

        参数:
            account: 账号（如果为None则不输入账号，适用于记住账号的情况）
            password: 密码（必需）
            captcha: 验证码（如果提供则自动填入）
            manual_captcha: 是否强制人工输入验证码（默认False，优先使用OCR自动识别）
            debug_mode: 是否启用调试模式（保存截图、详细日志）

        流程:
            1. 点击登录按钮
            2. 等待登录弹窗出现
            3. 如果提供account，输入账号
            4. 输入密码
            5. 处理验证码（人工输入或自动识别）
            6. 点击确认登录按钮
            7. 等待登录完成并验证

        返回:
            是否登录成功
        """
        print("\n" + "="*70)
        print("🔐 自动登录流程")
        if debug_mode:
            print("   [调试模式已启用 - 将保存截图和详细日志]")
        print("="*70)

        # 检查必需的坐标配置
        required_coords = ['login_button', 'password_input', 'login_confirm_button']
        for coord_name in required_coords:
            if self.coords.get(coord_name) is None:
                print(f"❌ 未配置坐标: {coord_name}")
                print("   请先运行校准工具配置登录相关坐标")
                return False

        # 检查密码
        if password is None or password == "":
            print("❌ 未提供密码，无法登录")
            return False

        try:
            # 1. 激活窗口
            print("\n步骤 1/7: 激活同花顺窗口...")
            if not self.activate_ths_window():
                print("❌ 激活窗口失败")
                return False

            # 2. 点击登录按钮
            print("\n步骤 2/7: 点击登录按钮...")

            # 显示详细的坐标信息
            login_btn_coords = self.coords['login_button']
            print(f"  → 登录按钮相对坐标: {login_btn_coords}")
            abs_coords = self.get_absolute_coords(*login_btn_coords)
            print(f"  → 登录按钮绝对坐标: {abs_coords}")

            # 调试模式：截图当前屏幕，标记即将点击的位置
            if debug_mode:
                self._debug_screenshot_click_position(
                    abs_coords[0], abs_coords[1],
                    "./debug_login_button_click.png"
                )

            # 增加点击前的额外等待
            time.sleep(0.5)

            # 点击登录按钮（可能需要多次点击）
            self.click_at(*login_btn_coords)
            time.sleep(0.3)  # 短暂等待
            self.click_at(*login_btn_coords)  # 再次点击确保生效

            # 增加等待时间，确保弹窗有足够时间出现
            time.sleep(2.5)  # 从1.5秒增加到2.5秒

            # 验证弹窗是否出现
            if self._verify_login_dialog_opened():
                print("✅ 登录弹窗已打开")
            else:
                print("⚠️  登录弹窗未检测到，但继续执行...")
                print("   提示: 请检查登录按钮坐标是否正确")
                # 截图当前状态供用户检查
                if debug_mode:
                    pyautogui.screenshot("./debug_after_login_click.png")
                    print(f"   已保存截图: ./debug_after_login_click.png")

                    # 在macOS上打开截图
                    try:
                        subprocess.run(['open', './debug_after_login_click.png'], check=False)
                    except Exception:
                        pass

                    # 询问用户
                    user_input = input("\n请查看截图，登录弹窗是否已打开？(y/n): ").strip().lower()

                    if user_input != 'y':
                        print("❌ 登录弹窗未打开，中止登录流程")
                        print("\n💡 故障排查建议：")
                        print("1. 检查登录按钮坐标是否正确（运行校准工具）")
                        print("2. 确认当前确实处于未登录状态")
                        print("3. 检查是否有其他窗口遮挡")
                        print("4. 手动点击登录按钮，观察弹窗位置")
                        return False

            # 3. 输入账号（如果提供）
            if account is not None and account != "":
                if self.coords.get('account_input') is not None:
                    print(f"\n步骤 3/7: 输入账号...")
                    acc_coords = self.coords['account_input']
                    self.input_text_via_clipboard(int(acc_coords[0]), int(acc_coords[1]), account)
                    print(f"✅ 账号已输入")
                else:
                    print("\n步骤 3/7: 跳过（未配置账号输入框坐标）")
            else:
                print("\n步骤 3/7: 跳过（使用记住的账号）")

            # 4. 输入密码
            print(f"\n步骤 4/7: 输入密码...")
            pwd_coords = self.coords['password_input']

            # 使用专用密码输入方法
            success = self.input_password(
                int(pwd_coords[0]),
                int(pwd_coords[1]),
                password,
                debug_mode=debug_mode
            )

            if not success:
                print("❌ 密码输入失败")
                print("\n💡 故障排查建议：")
                print("1. 检查密码输入框坐标是否正确")
                print("2. 确认登录弹窗已完全加载")
                print("3. 手动点击密码框，确认可以输入")
                print("4. 查看调试截图: debug_password_input_position.png")

                user_choice = input("\n继续执行？(y/n): ").strip().lower()
                if user_choice != 'y':
                    return False
            else:
                print("✅ 密码已输入")

            # 5. 处理验证码
            print(f"\n步骤 5/7: 处理验证码...")

            # 检查是否有验证码输入框
            if self.coords.get('captcha_input') is not None:
                if captcha is None or captcha == "":
                    # 需要获取验证码
                    if manual_captcha:
                        captcha = self.handle_captcha(manual=True)
                    else:
                        captcha = self.handle_captcha(manual=False)

                if captcha and captcha != "":
                    print("  → 正在输入验证码...")
                    captcha_coords = self.coords['captcha_input']

                    # 明确点击验证码输入框，确保焦点正确
                    print("  → 点击验证码输入框...")
                    self.click_at(int(captcha_coords[0]), int(captcha_coords[1]), clicks=1)
                    time.sleep(0.5)  # 等待焦点切换

                    # 再次点击确保焦点
                    self.click_at(int(captcha_coords[0]), int(captcha_coords[1]), clicks=1)
                    time.sleep(0.3)

                    # 使用 clear_and_type 输入验证码
                    self.clear_and_type(int(captcha_coords[0]), int(captcha_coords[1]), captcha)
                    print(f"✅ 验证码已输入: {captcha}")
                else:
                    print("⚠️  未输入验证码，登录可能失败")
            else:
                print("✅ 无需验证码（或未配置验证码坐标）")

            # 6. 点击确认登录按钮并检测错误
            print(f"\n步骤 6/7: 点击确认登录...")
            max_captcha_retries = 30
            captcha_retry_count = 0

            while captcha_retry_count < max_captcha_retries:
                # 点击确认登录
                self.click_at(*self.coords['login_confirm_button'])
                time.sleep(2)  # 等待响应

                # 检测是否有验证码错误弹窗
                captcha_error = self.check_captcha_error_popup()

                if captcha_error is True:
                    # 检测到验证码错误
                    captcha_retry_count += 1
                    print(f"   ❌ 验证码错误 (尝试 {captcha_retry_count}/{max_captcha_retries})")

                    if captcha_retry_count >= max_captcha_retries:
                        print(f"   ❌ 验证码重试次数已达上限")
                        return False

                    # 关闭错误弹窗
                    if not self.handle_captcha_error_popup():
                        print(f"   ❌ 无法关闭错误弹窗")
                        return False

                    print(f"\n🔄 重新获取验证码（第 {captcha_retry_count + 1} 次）...")

                    # 重新处理验证码
                    if manual_captcha:
                        captcha = self.handle_captcha(manual=True)
                    else:
                        captcha = self.handle_captcha(manual=False, auto_confirm=True)

                    if not captcha:
                        print("   ❌ 未能获取新验证码")
                        return False

                    # 输入新验证码
                    print("  → 输入新验证码...")
                    captcha_coords = self.coords['captcha_input']
                    self.click_at(int(captcha_coords[0]), int(captcha_coords[1]), clicks=1)
                    time.sleep(0.5)

                    # 清空旧验证码
                    pyautogui.hotkey('command', 'a')
                    time.sleep(0.2)
                    pyautogui.press('backspace')
                    time.sleep(0.3)

                    # 输入新验证码
                    self.clear_and_type(int(captcha_coords[0]), int(captcha_coords[1]), captcha)
                    print(f"  ✅ 新验证码已输入: {captcha}")

                    # 继续下一次尝试（会重新点击确认按钮）
                    continue

                elif captcha_error is False:
                    # 没有错误弹窗，登录成功或需要等待
                    print("✅ 登录请求已提交（无验证码错误）")
                    break

                else:  # captcha_error is None
                    # 无法检测，假设成功
                    print("⚠️  无法检测验证码错误状态，假设成功")
                    break

            # 7. 验证登录结果
            print(f"\n步骤 7/7: 验证登录状态...")
            time.sleep(1)  # 额外等待

            # 简单验证：检查登录按钮是否消失
            # 实际使用中可以用更可靠的方法验证
            print("✅ 登录流程完成")
            print("\n" + "="*70)
            print("💡 提示: 请人工确认是否成功登录")
            print("="*70)

            return True

        except Exception as e:
            print(f"\n❌ 登录过程出错: {e}")
            import traceback
            traceback.print_exc()
            return False

    def ensure_logged_in(self, auto_login_enabled: bool = False,
                        account: str = None, password: str = None,
                        manual_captcha: bool = False) -> bool:
        """
        确保已登录，如果未登录则提示或自动登录

        参数:
            auto_login_enabled: 是否启用自动登录
            account: 登录账号
            password: 登录密码
            manual_captcha: 是否强制人工输入验证码（默认False，优先使用OCR）

        返回:
            是否成功登录
        """
        print("\n" + "─"*70)
        print("🔍 检查登录状态...")
        print("─"*70)

        if self.check_login_status():
            print("✅ 已登录")
            return True

        print("⚠️  检测到未登录")

        if auto_login_enabled:
            print("正在自动登录...")
            return self.auto_login(account, password, manual_captcha=manual_captcha)
        else:
            print("\n💡 请选择操作：")
            print("1. 手动登录（在同花顺界面登录）")
            print("2. 自动登录（需要提供账号密码）")
            print("3. 取消")

            choice = input("\n请选择 [1-3]: ").strip()

            if choice == "1":
                print("\n请在同花顺界面手动登录...")
                input("登录完成后按 Enter 继续...")
                return self.check_login_status()
            elif choice == "2":
                if account is None:
                    account = input("请输入账号（直接回车跳过）: ").strip() or None
                if password is None:
                    import getpass
                    password = getpass.getpass("请输入密码: ").strip()

                if password:
                    return self.auto_login(account, password, manual_captcha=manual_captcha)
                else:
                    print("❌ 未提供密码，无法登录")
                    return False
            else:
                print("已取消")
                return False

    # ============================================
    # 状态检测与自动恢复功能
    # ============================================

    def check_window_active(self) -> bool:
        """
        检测同花顺窗口是否在最前端

        使用AppleScript检查窗口状态

        返回:
            True: 窗口已激活
            False: 窗口未激活
        """
        script = '''
        tell application "System Events"
            set frontApp to name of first application process whose frontmost is true
            return (frontApp is "同花顺")
        end tell
        '''
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                check=True
            )
            is_active = result.stdout.strip() == "true"
            if not is_active:
                print("   ⚠️  同花顺未在最前端")
            return is_active
        except Exception as e:
            print(f"   ❌ 窗口状态检测失败: {e}")
            return False

    def check_trading_tab(self) -> bool:
        """
        检测是否在交易Tab（已简化）

        注意：此方法已简化，不再使用OCR识别
        直接切换到交易Tab，确保在正确的界面

        返回:
            True: 成功切换到交易Tab
            False: 切换失败

        废弃说明：
            - 旧版本通过OCR识别Tab区域文字判断是否在交易Tab
            - 新版本直接点击交易Tab坐标，更简单可靠
            - 保留此方法以保证向后兼容
        """
        print("   → 确保在交易Tab（直接切换）...")
        return self.switch_to_trading_tab()

    def switch_to_trading_tab(self) -> bool:
        """
        切换到交易Tab

        直接点击交易Tab位置，不再使用OCR验证
        简化逻辑，提高可靠性

        返回:
            True: 切换成功
            False: 切换失败
        """
        print("   🔄 切换到交易Tab...")

        try:
            # 获取交易Tab坐标
            trade_tab_coords = self.coords.get('trade_tab')
            if not trade_tab_coords:
                print("   ❌ 未配置trade_tab坐标")
                return False

            # 点击交易Tab
            self.click_at(*trade_tab_coords)
            time.sleep(1)

            print("   ✅ 已切换到交易Tab")
            return True

        except Exception as e:
            print(f"   ❌ 切换Tab失败: {e}")
            return False

    def check_timeout_popup(self) -> bool:
        """
        检测是否有登录超时弹窗

        使用多种方式检测：
        1. OCR识别弹窗内容
        2. AppleScript检查弹窗窗口名称

        返回:
            True: 检测到超时弹窗
            False: 无超时弹窗
            None: 检测失败（未安装OCR或截图失败）
        """
        print("  → 检测登录超时弹窗...")

        # ========================================
        # 方法1: OCR识别弹窗内容
        # ========================================
        try:
            # 获取弹窗区域坐标（相对坐标或绝对坐标）
            popup_region_coords = None
            if self.use_relative_coords and 'popup_region' in self.coords_relative:
                popup_region_coords = self.coords_relative.get('popup_region')
            else:
                popup_region_coords = self.coords.get('popup_region')

            if not popup_region_coords:
                print("     ⚠️  未配置popup_region坐标")
            else:
                # 转换为绝对坐标
                if len(popup_region_coords) == 4:
                    x, y, w, h = popup_region_coords
                    if self.use_relative_coords and self.window_pos:
                        abs_x = self.window_pos[0] + x
                        abs_y = self.window_pos[1] + y
                    else:
                        abs_x, abs_y = x, y

                    region = (int(abs_x), int(abs_y), w, h)
                    print(f"     → 截取弹窗区域: {region}")

                    # 截图弹窗区域
                    screenshot = pyautogui.screenshot(region=region)

                    # 保存截图供调试
                    debug_path = '/tmp/ths_popup_check.png'
                    screenshot.save(debug_path)
                    print(f"     → 已保存截图: {debug_path}")

                    # OCR识别
                    try:
                        import pytesseract
                        from PIL import ImageEnhance

                        # 增强对比度
                        enhancer = ImageEnhance.Contrast(screenshot)
                        enhanced_img = enhancer.enhance(2.0)

                        # OCR识别中文和英文
                        custom_config = r'--oem 3 --psm 6 -l chi_sim+eng'
                        text = pytesseract.image_to_string(enhanced_img, config=custom_config)
                        text_cleaned = text.strip().replace(' ', '').replace('\n', '')

                        print(f"     → OCR识别到的文字: '{text_cleaned}'")

                        # ====================================================
                        # 关键逻辑区分：超时弹窗 vs 登录表单
                        # ====================================================
                        #
                        # 1. 超时弹窗（Timeout Popup）- 需要关闭
                        #    - 运行中会话过期显示的提示框
                        #    - 内容：提示文字如"登录超时，请重新登录"
                        #    - 有"确定"按钮需要点击关闭
                        #    - 这个方法应该返回 True
                        #
                        # 2. 登录表单（Login Form Dialog）- 不需要关闭
                        #    - 未登录状态或超时后的正常登录界面
                        #    - 内容：表单字段（站点列表、账户、密码、验证码）
                        #    - 这是正常界面，不是需要"关闭"的弹窗
                        #    - 这个方法应该返回 False
                        #
                        # ====================================================

                        # 只检查真正的超时提示关键字
                        timeout_keywords = [
                            '登录超时', '会话超时', '超时',
                            '会话过期', '登录过期', '过期',
                            '重新登录', '请重新登录',
                            '连接超时', '网络超时',
                            '登录失效', '会话失效',
                            'timeout', 'expired', 'sessionexpired',
                            '确定', '确认', '关闭'  # 超时弹窗通常有这些按钮
                        ]

                        # 检查超时关键字
                        for keyword in timeout_keywords:
                            if keyword in text_cleaned.lower():
                                print(f"     ✅ 检测到超时弹窗（关键字: {keyword}）")
                                return True

                        # 登录表单不是"超时弹窗"，不应该返回True
                        # 这里移除了登录表单检测逻辑

                        # 如果识别到了较长文字，但没有匹配关键字，输出以供调试
                        if len(text_cleaned) > 5:
                            print(f"     ⚠️  识别到文字但无关键字匹配: {text_cleaned}")

                    except ImportError:
                        print("     ⚠️  未安装pytesseract，无法使用OCR检测")
                    except Exception as ocr_error:
                        print(f"     ⚠️  OCR识别出错: {ocr_error}")

        except Exception as e:
            print(f"     ❌ OCR方法失败: {e}")

        # ========================================
        # 方法2: AppleScript检查弹窗窗口名称
        # ========================================
        try:
            check_popup_script = f'''
            tell application "System Events"
                tell process "{self.app_name}"
                    set windowCount to count of windows
                    if windowCount > 0 then
                        set frontWindow to front window
                        set windowName to name of frontWindow
                        return windowName
                    else
                        return ""
                    end if
                end tell
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', check_popup_script],
                capture_output=True,
                text=True,
                timeout=5
            )
            window_name = result.stdout.strip()
            print(f"     → 当前窗口名称: '{window_name}'")

            # 检查窗口名称是否包含弹窗特征
            popup_window_keywords = ['超时', '过期', '提示', '警告', '错误', 'timeout', 'expired', 'error']
            for keyword in popup_window_keywords:
                if keyword in window_name.lower():
                    print(f"     ✅ 检测到弹窗窗口（关键字: {keyword}）")
                    return True

        except Exception as window_error:
            print(f"     ⚠️  窗口名称检查失败: {window_error}")

        # ========================================
        # 方法3: 检查是否有模态对话框
        # ========================================
        try:
            check_dialog_script = f'''
            tell application "System Events"
                tell process "{self.app_name}"
                    if exists sheet 1 of window 1 then
                        return "sheet"
                    else if exists window 2 then
                        return "dialog"
                    else
                        return "none"
                    end if
                end tell
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', check_dialog_script],
                capture_output=True,
                text=True,
                timeout=5
            )
            dialog_type = result.stdout.strip()
            print(f"     → 对话框类型: {dialog_type}")

            if dialog_type in ['sheet', 'dialog']:
                print(f"     ⚠️  检测到模态对话框，可能是超时弹窗")
                # 这里不直接返回True，因为可能是其他对话框
                # 但输出警告供用户判断

        except Exception as dialog_error:
            print(f"     ⚠️  对话框检查失败: {dialog_error}")

        print("     → 未检测到超时弹窗")
        return False

    def handle_timeout_popup(self) -> bool:
        """
        处理登录超时弹窗

        点击弹窗的确定按钮，然后验证弹窗是否关闭
        支持多种策略：点击按钮、回车键、ESC键

        返回:
            True: 处理成功（弹窗已关闭）
            False: 处理失败（弹窗仍存在）
        """
        print("   🔄 处理超时弹窗...")

        try:
            # 获取弹窗确定按钮坐标（优先使用相对坐标）
            if self.use_relative_coords and 'popup_confirm_button' in self.coords_relative:
                confirm_button_coords = self.coords_relative.get('popup_confirm_button')
                print(f"   → 使用相对坐标: {confirm_button_coords}")
            else:
                confirm_button_coords = self.coords.get('popup_confirm_button')
                print(f"   → 使用绝对坐标: {confirm_button_coords}")

            if not confirm_button_coords:
                print("   ❌ 未配置popup_confirm_button坐标")
                return False

            # 策略1: 多次点击确定按钮（有时第一次点击不生效）
            print("   → 策略1: 点击确定按钮")
            for attempt in range(3):
                print(f"   → 第 {attempt + 1} 次点击...")
                self.click_at(*confirm_button_coords)
                time.sleep(0.8)

                # 每次点击后检查弹窗是否关闭
                result = self.check_timeout_popup()
                if not result:
                    print("   ✅ 超时弹窗已关闭（点击按钮成功）")
                    return True

            print("   ⚠️  点击按钮未能关闭弹窗，尝试其他策略...")

            # 策略2: 尝试按回车键
            print("   → 策略2: 按回车键")
            for attempt in range(2):
                pyautogui.press('return')
                time.sleep(0.8)

                result = self.check_timeout_popup()
                if not result:
                    print("   ✅ 超时弹窗已关闭（回车键成功）")
                    return True

            # 策略3: 尝试按ESC键
            print("   → 策略3: 按ESC键")
            for attempt in range(2):
                pyautogui.press('escape')
                time.sleep(0.8)

                result = self.check_timeout_popup()
                if not result:
                    print("   ✅ 超时弹窗已关闭（ESC键成功）")
                    return True

            # 所有策略都失败
            print("   ❌ 所有策略均未能关闭弹窗")
            print("   💡 提示: 请检查popup_confirm_button坐标是否正确")
            print(f"   💡 当前使用{'相对' if self.use_relative_coords else '绝对'}坐标模式")
            return False

        except Exception as e:
            print(f"   ❌ 处理弹窗失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def check_captcha_error_popup(self) -> bool:
        """
        检测验证码错误弹窗

        类似于 check_timeout_popup()，使用 OCR 识别弹窗文字

        返回:
            True: 检测到验证码错误弹窗
            False: 无验证码错误弹窗
            None: 检测失败
        """
        print("  → 检测验证码错误弹窗...")

        try:
            import pytesseract
            from PIL import ImageEnhance
        except ImportError:
            print("     ⚠️  未安装pytesseract，无法使用OCR检测")
            return None

        try:
            # 使用相同的 popup_region 坐标
            popup_region_coords = None
            if self.use_relative_coords and 'popup_region' in self.coords_relative:
                popup_region_coords = self.coords_relative.get('popup_region')
            else:
                popup_region_coords = self.coords.get('popup_region')

            if not popup_region_coords:
                print("     ⚠️  未配置popup_region坐标")
                return None

            # 截取弹窗区域
            if len(popup_region_coords) == 4:
                x, y, w, h = popup_region_coords
                if self.use_relative_coords and self.window_pos:
                    abs_x = self.window_pos[0] + x
                    abs_y = self.window_pos[1] + y
                else:
                    abs_x, abs_y = x, y

                region = (int(abs_x), int(abs_y), w, h)
                screenshot = pyautogui.screenshot(region=region)

                # 保存调试截图
                debug_path = '/tmp/ths_captcha_error_check.png'
                screenshot.save(debug_path)
                print(f"     → 已保存截图: {debug_path}")

                # OCR识别
                enhancer = ImageEnhance.Contrast(screenshot)
                enhanced_img = enhancer.enhance(2.0)

                custom_config = r'--oem 3 --psm 6 -l chi_sim+eng'
                text = pytesseract.image_to_string(enhanced_img, config=custom_config)
                text_cleaned = text.strip().replace(' ', '').replace('\n', '')

                print(f"     → OCR识别到的文字: '{text_cleaned}'")

                # ====================================================
                # 验证码错误/提示的多种表达方式
                # ====================================================
                # 1. 明确的错误提示
                # 2. 要求输入验证码的提示（说明之前输入的无效或未输入）
                # ====================================================

                error_keywords = [
                    # 明确的错误提示
                    '验证码错误', '验证码不正确', '验证码有误',
                    '验证码输入错误', '验证码不对',
                    'captchaerror', 'captchaincorrect', 'wrongcaptcha',
                    '请重新输入', '输入错误', '验证失败',

                    # 要求输入验证码的提示（关键！）
                    '请输入验证码', '请输入', '输入验证码',
                    '验证码不能为空', '验证码为空',
                    '请填写验证码', '填写验证码',
                    'pleaseinput', 'entercaptcha', 'inputcaptcha',

                    # 提示类弹窗
                    '提示', 'tip', 'hint', 'notice'
                ]

                # 检查关键字
                matched_keywords = []
                for keyword in error_keywords:
                    if keyword in text_cleaned.lower():
                        matched_keywords.append(keyword)

                if matched_keywords:
                    print(f"     ✅ 检测到验证码错误弹窗（匹配关键字: {matched_keywords[:3]}）")
                    return True

                print(f"     → 未检测到验证码错误弹窗")
                return False

        except Exception as e:
            print(f"     ❌ OCR检测失败: {e}")
            return None

        return False

    def handle_captcha_error_popup(self) -> bool:
        """
        处理验证码错误弹窗（多策略方式）

        使用多种策略关闭弹窗：
        1. 多次点击确定按钮（有时第一次点击不生效）
        2. 按回车键
        3. 按ESC键

        返回:
            True: 成功关闭弹窗
            False: 关闭失败
        """
        print("   🔄 处理验证码错误弹窗...")

        try:
            # 获取弹窗确定按钮坐标（优先使用相对坐标）
            if self.use_relative_coords and 'popup_confirm_button' in self.coords_relative:
                confirm_button_coords = self.coords_relative.get('popup_confirm_button')
                print(f"   → 使用相对坐标: {confirm_button_coords}")
            else:
                confirm_button_coords = self.coords.get('popup_confirm_button')
                print(f"   → 使用绝对坐标: {confirm_button_coords}")

            if not confirm_button_coords:
                print("   ⚠️  未配置popup_confirm_button坐标")
                # 跳过策略1，直接使用策略2和3
            else:
                # 策略1: 多次点击确定按钮（有时第一次点击不生效）
                print("   → 策略1: 点击确定按钮")
                for attempt in range(3):
                    print(f"   → 第 {attempt + 1} 次点击...")
                    self.click_at(*confirm_button_coords)
                    time.sleep(0.8)

                    # 每次点击后检查弹窗是否关闭
                    result = self.check_captcha_error_popup()
                    if not result:
                        print("   ✅ 验证码错误弹窗已关闭（点击按钮成功）")
                        return True

                print("   ⚠️  点击按钮未能关闭弹窗，尝试其他策略...")

            # 策略2: 尝试按回车键
            print("   → 策略2: 按回车键")
            for attempt in range(2):
                pyautogui.press('return')
                time.sleep(0.8)

                result = self.check_captcha_error_popup()
                if not result:
                    print("   ✅ 验证码错误弹窗已关闭（回车键成功）")
                    return True

            # 策略3: 尝试按ESC键
            print("   → 策略3: 按ESC键")
            for attempt in range(2):
                pyautogui.press('escape')
                time.sleep(0.8)

                result = self.check_captcha_error_popup()
                if not result:
                    print("   ✅ 验证码错误弹窗已关闭（ESC键成功）")
                    return True

            # 所有策略都失败
            print("   ❌ 所有策略均未能关闭弹窗")
            print("   💡 提示: 请检查popup_confirm_button坐标是否正确")
            print(f"   💡 当前使用{'相对' if self.use_relative_coords else '绝对'}坐标模式")
            return False

        except Exception as e:
            print(f"   ❌ 处理弹窗失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def ensure_ready_for_trading(self, password: str = None, max_retries: int = 3) -> bool:
        """
        确保系统准备就绪，可以开始交易

        自动检测并恢复以下状态：
        1. 窗口是否在最前端
        2. 是否有登录超时弹窗
        3. 是否已登录
        4. 是否在交易Tab

        参数:
            password: 登录密码（如需自动登录）
            max_retries: 最大重试次数（默认3次）

        返回:
            True: 系统准备就绪
            False: 恢复失败
        """
        print("\n" + "="*70)
        print("🔧 自动状态检测与恢复")
        print("="*70)

        # ============================
        # 系统诊断
        # ============================
        print("\n📊 系统诊断:")

        # 1. 检查进程
        print("\n1. 进程检查:")
        detected_process_name = self.get_ths_process_name()
        if detected_process_name != self.app_name:
            print(f"  → 自动更新进程名称: {self.app_name} -> {detected_process_name}")
            self.app_name = detected_process_name

        # 2. 检查窗口位置
        print("\n2. 窗口位置检查:")
        window_pos = self.get_window_position()
        if window_pos:
            print(f"  ✅ 窗口位置: ({window_pos[0]}, {window_pos[1]}), 大小: {window_pos[2]}x{window_pos[3]}")
            self.window_pos = window_pos
        else:
            print(f"  ⚠️  无法获取窗口位置（将使用绝对坐标）")
            if self.use_relative_coords:
                print(f"  💡 建议: 切换到绝对坐标模式或检查窗口权限")

        # 3. 检查坐标模式
        print("\n3. 坐标模式:")
        print(f"  → 使用相对坐标: {self.use_relative_coords}")
        if self.use_relative_coords and not self.window_pos:
            print(f"  ⚠️  相对坐标模式需要窗口位置，但获取失败")
            print(f"  ⚠️  警告：后续坐标操作可能失败")
            print(f"  💡 建议：检查同花顺窗口是否可见，或授予辅助功能权限")
            # ❌ 不要永久关闭相对坐标模式！这会导致后续所有操作使用错误的坐标
            # 之前的代码： self.use_relative_coords = False  (这行导致了 bug)

        print("\n" + "="*70)

        for retry in range(max_retries):
            if retry > 0:
                print(f"\n⏳ 第 {retry + 1} 次尝试...")
                time.sleep(2)

            # ============================
            # 检查1: 窗口是否在最前端
            # ============================
            print("\n检查 1/4: 窗口是否在最前端?")
            if not self.check_window_active():
                print("   🔄 激活窗口...")
                if not self.activate_ths_window():
                    print("   ❌ 窗口激活失败")
                    continue
                print("   ✅ 窗口已激活")
                time.sleep(1)
            else:
                print("   ✅ 窗口已在最前端")

            # ============================
            # 检查2: 是否有登录超时弹窗
            # ============================
            print("\n检查 2/4: 是否有登录超时弹窗?")
            popup_result = self.check_timeout_popup()

            if popup_result:
                # 检测到超时弹窗，处理它
                if not self.handle_timeout_popup():
                    print("   ❌ 超时弹窗处理失败")
                    continue
                print("   ✅ 超时弹窗已处理")
                time.sleep(1)
            elif popup_result is False:
                print("   ✅ 无超时弹窗")
            else:  # popup_result is None
                print("   ⚠️  无法检测弹窗状态（跳过）")

            # ============================
            # 检查3: 是否已登录
            # ============================
            print("\n检查 3/4: 是否已登录?")
            if not self.check_login_status(auto_detect=True):
                print("   🔄 执行自动登录...")

                # 如果没有提供密码，尝试从环境变量或配置文件读取
                if not password:
                    password = "824532" #os.environ.get('THS_PASSWORD')

                if not password:
                    print("   ❌ 未提供密码，无法自动登录")
                    print("   提示: 请在调用时提供password参数，或设置THS_PASSWORD环境变量")
                    return False

                if not self.auto_login(password=password):
                    print("   ❌ 自动登录失败")
                    continue
                print("   ✅ 登录成功")
                time.sleep(2)
            else:
                print("   ✅ 已登录")

            # ============================
            # 检查4: 是否在交易Tab
            # ============================
            print("\n检查 4/4: 是否在交易Tab?")
            # 直接切换到交易Tab，不需要先检测
            if not self.switch_to_trading_tab():
                print("   ❌ 切换到交易Tab失败")
                continue
            print("   ✅ 已在交易Tab")

            # ============================
            # 所有检查通过
            # ============================
            print("\n" + "="*70)
            print("✅ 系统准备就绪，可以开始交易")
            print("="*70)
            return True

        # 达到最大重试次数
        print("\n" + "="*70)
        print(f"❌ 自动恢复失败（已重试 {max_retries} 次）")
        print("="*70)
        return False

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
            "模态对话框确认按钮",
            "登录按钮（可选）",
            "账号输入框（可选）",
            "密码输入框（可选）",
            "验证码输入框（可选）",
            "验证码图片区域-左上角（可选）",
            "验证码图片区域-右下角（可选）",
            "登录确认按钮（可选）",
            "交易Tab按钮（可选）",
            "交易Tab区域-左上角（可选）",
            "交易Tab区域-右下角（可选）",
            "登录超时弹窗确认按钮（可选）",
            "弹窗内容区域-左上角（可选）",
            "弹窗内容区域-右下角（可选）"
        ]

        # 用于存储各个区域的两个点
        captcha_region_p1 = None
        captcha_region_p2 = None
        trade_tab_region_p1 = None
        trade_tab_region_p2 = None
        popup_region_p1 = None
        popup_region_p2 = None

        for label in labels:
            print(f"\n请将鼠标移动到【{label}】位置，然后在终端按 Enter...")

            # 添加提示信息
            if label == "模态对话框确认按钮":
                print("   提示：需要先点击'确认按钮'让对话框弹出，然后移动鼠标到对话框的确认按钮")
            elif label == "登录按钮（可选）":
                print("   提示：如需自动登录功能，请先登出账号，然后指向主界面的登录按钮")
            elif label == "账号输入框（可选）":
                print("   提示：点击登录按钮后，在弹出的登录窗口中指向账号输入框")
            elif label == "密码输入框（可选）":
                print("   提示：在登录窗口中指向密码输入框")
            elif label == "验证码输入框（可选）":
                print("   提示：如果登录需要验证码，指向验证码输入框")
            elif label == "验证码图片区域-左上角（可选）":
                print("   提示：如需OCR识别验证码，请移动到验证码图片的左上角")
                print("   说明：验证码图片区域需要两个点来定义矩形区域")
            elif label == "验证码图片区域-右下角（可选）":
                print("   提示：移动到验证码图片的右下角")
                if captcha_region_p1:
                    print(f"   左上角已记录: {captcha_region_p1}")
            elif label == "登录确认按钮（可选）":
                print("   提示：在登录窗口中指向确认登录的按钮")
            elif label == "交易Tab按钮（可选）":
                print("   提示：点击可以切换到交易界面的Tab按钮")
            elif label == "交易Tab区域-左上角（可选）":
                print("   提示：用于OCR识别交易Tab状态，请移动到包含'交易'文字区域的左上角")
                print("   说明：交易Tab区域需要两个点来定义矩形区域")
            elif label == "交易Tab区域-右下角（可选）":
                print("   提示：移动到包含'交易'文字区域的右下角")
                if trade_tab_region_p1:
                    print(f"   左上角已记录: {trade_tab_region_p1}")
            elif label == "登录超时弹窗确认按钮（可选）":
                print("   提示：登录超时弹窗中的确认/确定按钮")
            elif label == "弹窗内容区域-左上角（可选）":
                print("   提示：用于OCR识别弹窗内容，请移动到弹窗文字区域的左上角")
                print("   说明：弹窗内容区域需要两个点来定义矩形区域")
            elif label == "弹窗内容区域-右下角（可选）":
                print("   提示：移动到弹窗文字区域的右下角")
                if popup_region_p1:
                    print(f"   左上角已记录: {popup_region_p1}")

            print("   （输入 's' 跳过此项，'q' 退出校准）")
            user_input = input()

            if user_input.lower() == 'q':
                break
            elif user_input.lower() == 's':
                print(f"⏭️  已跳过 {label}")

                # 如果跳过左上角，也标记右下角为跳过
                if label == "验证码图片区域-左上角（可选）":
                    captcha_region_p1 = None
                elif label == "交易Tab区域-左上角（可选）":
                    trade_tab_region_p1 = None
                elif label == "弹窗内容区域-左上角（可选）":
                    popup_region_p1 = None

                continue

            x, y = pyautogui.position()

            # 特殊处理验证码图片区域
            if label == "验证码图片区域-左上角（可选）":
                captcha_region_p1 = (x, y)
                print(f"✅ {label}: ({x}, {y})")
            elif label == "验证码图片区域-右下角（可选）":
                if captcha_region_p1 is None:
                    print(f"⚠️  未记录左上角，跳过验证码图片区域")
                else:
                    captcha_region_p2 = (x, y)
                    print(f"✅ {label}: ({x}, {y})")

                    # 计算区域 (x, y, width, height)
                    x1, y1 = captcha_region_p1
                    x2, y2 = captcha_region_p2
                    region_x = min(x1, x2)
                    region_y = min(y1, y2)
                    region_width = abs(x2 - x1)
                    region_height = abs(y2 - y1)

                    positions.append((
                        "验证码图片区域",
                        region_x,
                        region_y,
                        region_width,
                        region_height
                    ))
                    print(f"✅ 验证码图片区域: ({region_x}, {region_y}, {region_width}, {region_height})")
            elif label == "交易Tab区域-左上角（可选）":
                trade_tab_region_p1 = (x, y)
                print(f"✅ {label}: ({x}, {y})")
            elif label == "交易Tab区域-右下角（可选）":
                if trade_tab_region_p1 is None:
                    print(f"⚠️  未记录左上角，跳过交易Tab区域")
                else:
                    trade_tab_region_p2 = (x, y)
                    print(f"✅ {label}: ({x}, {y})")

                    # 计算区域 (x, y, width, height)
                    x1, y1 = trade_tab_region_p1
                    x2, y2 = trade_tab_region_p2
                    region_x = min(x1, x2)
                    region_y = min(y1, y2)
                    region_width = abs(x2 - x1)
                    region_height = abs(y2 - y1)

                    positions.append((
                        "交易Tab区域",
                        region_x,
                        region_y,
                        region_width,
                        region_height
                    ))
                    print(f"✅ 交易Tab区域: ({region_x}, {region_y}, {region_width}, {region_height})")
            elif label == "弹窗内容区域-左上角（可选）":
                popup_region_p1 = (x, y)
                print(f"✅ {label}: ({x}, {y})")
            elif label == "弹窗内容区域-右下角（可选）":
                if popup_region_p1 is None:
                    print(f"⚠️  未记录左上角，跳过弹窗内容区域")
                else:
                    popup_region_p2 = (x, y)
                    print(f"✅ {label}: ({x}, {y})")

                    # 计算区域 (x, y, width, height)
                    x1, y1 = popup_region_p1
                    x2, y2 = popup_region_p2
                    region_x = min(x1, x2)
                    region_y = min(y1, y2)
                    region_width = abs(x2 - x1)
                    region_height = abs(y2 - y1)

                    positions.append((
                        "弹窗内容区域",
                        region_x,
                        region_y,
                        region_width,
                        region_height
                    ))
                    print(f"✅ 弹窗内容区域: ({region_x}, {region_y}, {region_width}, {region_height})")
            else:
                # 普通坐标点
                positions.append((label, x, y))
                print(f"✅ {label}: ({x}, {y})")

        # 输出校准结果
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
            "模态对话框确认按钮": "modal_confirm_button",
            "登录按钮（可选）": "login_button",
            "账号输入框（可选）": "account_input",
            "密码输入框（可选）": "password_input",
            "验证码输入框（可选）": "captcha_input",
            "验证码图片区域": "captcha_image_region",
            "登录确认按钮（可选）": "login_confirm_button",
            "交易Tab按钮（可选）": "trade_tab",
            "交易Tab区域": "trade_tab_region",
            "登录超时弹窗确认按钮（可选）": "popup_confirm_button",
            "弹窗内容区域": "popup_region"
        }

        for item in positions:
            label = item[0]
            key = key_map.get(label, label)

            if label == "验证码图片区域":
                # 验证码区域是4个值：(x, y, width, height)
                x, y, width, height = item[1], item[2], item[3], item[4]
                print(f"    '{key}': ({x}, {y}, {width}, {height}),")
            else:
                # 普通坐标是2个值：(x, y)
                x, y = item[1], item[2]
                print(f"    '{key}': ({x}, {y}),")

        print("}")
        print("\n" + "="*60)
        print("💡 提示：")
        print("1. 将上述配置复制到 ths_mac_trader.py 的 self.coords_relative 字典中")
        print("2. 区域坐标格式为 (x, y, width, height)，用于OCR识别或截图")
        print("3. 新增的校准项说明：")
        print("   - trade_tab: 交易Tab按钮，用于切换到交易界面")
        print("   - trade_tab_region: 交易Tab区域，用于OCR识别当前是否在交易界面")
        print("   - popup_confirm_button: 登录超时弹窗的确认按钮")
        print("   - popup_region: 弹窗内容区域，用于OCR识别弹窗文字")
        print("4. 可选项可以跳过，不影响基本交易功能")
        print("="*60)

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
║  8. 校准验证码区域 🆕                                     ║
║  9. 测试验证码截图 🆕                                     ║
║  10. 检查登录状态                                         ║
║  11. 自动登录 🔐                                          ║
║  0. 退出                                                  ║
╚══════════════════════════════════════════════════════════╝
    """)

    while True:
        choice = input("\n请选择功能 [0-11]: ").strip()

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
            # 注意：smart_sell 内部可能需要登录，但目前不支持 manual_captcha 参数
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

        elif choice == '8':
            # 校准验证码区域
            subprocess.run(['python3', 'calibrate_captcha_region.py'], check=False)

        elif choice == '9':
            # 测试验证码截图
            print("\n请确保登录弹窗已打开且显示验证码")
            input("按 Enter 继续...")

            captcha_path = trader.capture_captcha_image()
            if captcha_path:
                try:
                    subprocess.run(['open', captcha_path], check=False)
                    print(f"✅ 已打开验证码图片: {captcha_path}")
                except Exception as e:
                    print(f"⚠️  无法自动打开图片: {e}")
                    print(f"   请手动查看: {captcha_path}")

        elif choice == '10':
            # 检查登录状态
            trader.check_login_status()

        elif choice == '11':
            # 自动登录
            print("\n" + "="*60)
            print("🔐 自动登录")
            print("="*60)

            # 提示用户输入账号密码
            account = None

            # 使用 getpass 隐藏密码输入
            import getpass
            password = "824532"

            # 询问是否使用OCR识别验证码
            # use_ocr = input("是否使用OCR自动识别验证码？(y/n, 默认y): ").strip().lower()
            manual_captcha = False #(use_ocr == 'n')  # n表示不用OCR，即手动输入

            if password:
                success = trader.auto_login(account=account, password=password, manual_captcha=manual_captcha)
                if success:
                    print("\n✅ 登录流程执行完成，请检查同花顺界面确认是否成功")
                else:
                    print("\n❌ 登录失败")
            else:
                print("\n❌ 密码不能为空")

        else:
            print("无效选择，请重试")


if __name__ == "__main__":
    main()