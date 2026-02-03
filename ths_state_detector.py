"""
同花顺状态检测器
负责检测和识别同花顺应用的各种状态
"""

import time
import subprocess
import pyautogui
from PIL import Image, ImageGrab
import cv2
import numpy as np
from typing import Optional, Dict, Tuple, List
from enum import Enum
from dataclasses import dataclass
import logging
import os
import hashlib

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class THSState(Enum):
    """同花顺应用状态枚举"""
    # 窗口状态
    WINDOW_NOT_FOUND = "window_not_found"          # 应用未启动
    WINDOW_BACKGROUND = "window_background"        # 应用在后台
    WINDOW_FOREGROUND = "window_foreground"        # 应用在前台

    # Tab页状态
    TAB_UNKNOWN = "tab_unknown"                    # 无法识别当前Tab
    TAB_TRADE = "tab_trade"                        # 在交易Tab
    TAB_MARKET = "tab_market"                      # 在行情Tab
    TAB_NEWS = "tab_news"                          # 在资讯Tab
    TAB_PORTFOLIO = "tab_portfolio"                # 在自选Tab

    # 登录状态
    LOGIN_UNKNOWN = "login_unknown"                # 登录状态未知
    LOGIN_SUCCESS = "login_success"                # 已登录
    LOGIN_REQUIRED = "login_required"              # 需要登录
    LOGIN_TIMEOUT = "login_timeout"                # 登录超时
    LOGIN_ERROR = "login_error"                    # 登录错误

    # 交易状态
    TRADE_READY = "trade_ready"                    # 交易就绪
    TRADE_LOCKED = "trade_locked"                  # 交易锁定（非交易时间）
    TRADE_CONFIRMING = "trade_confirming"          # 等待确认


@dataclass
class StateCheckResult:
    """状态检测结果"""
    window_state: THSState
    tab_state: THSState
    login_state: THSState
    trade_state: THSState
    timestamp: float
    details: Dict = None
    screenshot: Optional[np.ndarray] = None

    def is_ready_for_trading(self) -> bool:
        """判断是否可以进行交易"""
        return (
            self.window_state == THSState.WINDOW_FOREGROUND and
            self.tab_state == THSState.TAB_TRADE and
            self.login_state == THSState.LOGIN_SUCCESS and
            self.trade_state == THSState.TRADE_READY
        )


class THSStateDetector:
    """同花顺状态检测器"""

    def __init__(self, image_templates_dir: str = "templates"):
        """
        初始化状态检测器

        Args:
            image_templates_dir: 图像模板目录
        """
        self.templates_dir = image_templates_dir
        self.templates_cache = {}
        self.last_check_result = None
        self.window_bounds = None

        # 创建模板目录
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir)
            logger.info(f"Created templates directory: {self.templates_dir}")

        # 加载已有模板
        self._load_templates()

    def _load_templates(self):
        """加载图像识别模板"""
        template_files = {
            'tab_trade': 'tab_trade.png',
            'tab_market': 'tab_market.png',
            'tab_news': 'tab_news.png',
            'tab_portfolio': 'tab_portfolio.png',
            'login_button': 'login_button.png',
            'login_timeout_dialog': 'login_timeout.png',
            'trade_panel': 'trade_panel.png',
            'logout_button': 'logout_button.png',
            'confirm_button': 'confirm_button.png'
        }

        for key, filename in template_files.items():
            path = os.path.join(self.templates_dir, filename)
            if os.path.exists(path):
                self.templates_cache[key] = cv2.imread(path)
                logger.info(f"Loaded template: {key}")
            else:
                logger.warning(f"Template not found: {path}")

    def check_all_states(self) -> StateCheckResult:
        """
        检测所有状态

        Returns:
            StateCheckResult: 综合状态检测结果
        """
        logger.info("Starting comprehensive state check...")

        # 1. 检测窗口状态
        window_state = self._check_window_state()

        # 如果窗口不在前台，其他检测可能不准确
        if window_state != THSState.WINDOW_FOREGROUND:
            return StateCheckResult(
                window_state=window_state,
                tab_state=THSState.TAB_UNKNOWN,
                login_state=THSState.LOGIN_UNKNOWN,
                trade_state=THSState.TRADE_LOCKED,
                timestamp=time.time(),
                details={'reason': 'Window not in foreground'}
            )

        # 2. 截取当前屏幕
        screenshot = self._capture_window_screenshot()

        # 3. 检测Tab状态
        tab_state = self._check_tab_state(screenshot)

        # 4. 检测登录状态
        login_state = self._check_login_state(screenshot)

        # 5. 检测交易状态
        trade_state = self._check_trade_state(screenshot, login_state, tab_state)

        result = StateCheckResult(
            window_state=window_state,
            tab_state=tab_state,
            login_state=login_state,
            trade_state=trade_state,
            timestamp=time.time(),
            screenshot=screenshot
        )

        self.last_check_result = result
        logger.info(f"State check complete: {result}")

        return result

    def _check_window_state(self) -> THSState:
        """
        检测窗口状态

        Returns:
            THSState: 窗口状态
        """
        try:
            # 使用AppleScript检测窗口状态
            script = '''
            tell application "System Events"
                if not (exists process "同花顺") then
                    return "not_found"
                else
                    tell process "同花顺"
                        if frontmost then
                            return "foreground"
                        else
                            return "background"
                        end if
                    end tell
                end if
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=5
            )

            output = result.stdout.strip()

            if output == "not_found":
                return THSState.WINDOW_NOT_FOUND
            elif output == "foreground":
                self._update_window_bounds()
                return THSState.WINDOW_FOREGROUND
            else:
                return THSState.WINDOW_BACKGROUND

        except Exception as e:
            logger.error(f"Failed to check window state: {e}")
            return THSState.WINDOW_NOT_FOUND

    def _update_window_bounds(self):
        """更新窗口边界信息"""
        try:
            script = '''
            tell application "System Events"
                tell process "同花顺"
                    tell window 1
                        set windowPosition to position
                        set windowSize to size
                        return {item 1 of windowPosition, item 2 of windowPosition, ¬
                                item 1 of windowSize, item 2 of windowSize}
                    end tell
                end tell
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=5
            )

            # 解析输出: "x, y, width, height"
            coords = result.stdout.strip().split(", ")
            if len(coords) == 4:
                self.window_bounds = {
                    'x': int(coords[0]),
                    'y': int(coords[1]),
                    'width': int(coords[2]),
                    'height': int(coords[3])
                }
                logger.debug(f"Window bounds updated: {self.window_bounds}")

        except Exception as e:
            logger.error(f"Failed to get window bounds: {e}")

    def _capture_window_screenshot(self) -> Optional[np.ndarray]:
        """
        截取窗口屏幕截图

        Returns:
            numpy array: 截图数据
        """
        try:
            if self.window_bounds:
                # 使用窗口边界截图
                region = (
                    self.window_bounds['x'],
                    self.window_bounds['y'],
                    self.window_bounds['width'],
                    self.window_bounds['height']
                )
                screenshot = ImageGrab.grab(bbox=region)
            else:
                # 全屏截图
                screenshot = ImageGrab.grab()

            # 转换为OpenCV格式
            screenshot_np = np.array(screenshot)
            screenshot_cv = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)

            return screenshot_cv

        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return None

    def _check_tab_state(self, screenshot: np.ndarray) -> THSState:
        """
        检测当前Tab页状态

        Args:
            screenshot: 屏幕截图

        Returns:
            THSState: Tab页状态
        """
        if screenshot is None:
            return THSState.TAB_UNKNOWN

        # 使用模板匹配检测各个Tab
        tab_templates = {
            'tab_trade': THSState.TAB_TRADE,
            'tab_market': THSState.TAB_MARKET,
            'tab_news': THSState.TAB_NEWS,
            'tab_portfolio': THSState.TAB_PORTFOLIO
        }

        for template_key, state in tab_templates.items():
            if template_key in self.templates_cache:
                if self._match_template(screenshot, self.templates_cache[template_key]):
                    logger.info(f"Detected tab: {state}")
                    return state

        # 如果没有匹配到任何Tab，使用OCR作为备选方案
        # 这里可以集成 OCR 功能

        return THSState.TAB_UNKNOWN

    def _check_login_state(self, screenshot: np.ndarray) -> THSState:
        """
        检测登录状态

        Args:
            screenshot: 屏幕截图

        Returns:
            THSState: 登录状态
        """
        if screenshot is None:
            return THSState.LOGIN_UNKNOWN

        # 检测登录超时对话框
        if 'login_timeout_dialog' in self.templates_cache:
            if self._match_template(screenshot, self.templates_cache['login_timeout_dialog']):
                logger.info("Detected login timeout dialog")
                return THSState.LOGIN_TIMEOUT

        # 检测登录按钮（表示未登录）
        if 'login_button' in self.templates_cache:
            if self._match_template(screenshot, self.templates_cache['login_button']):
                logger.info("Detected login button - not logged in")
                return THSState.LOGIN_REQUIRED

        # 检测登出按钮（表示已登录）
        if 'logout_button' in self.templates_cache:
            if self._match_template(screenshot, self.templates_cache['logout_button']):
                logger.info("Detected logout button - logged in")
                return THSState.LOGIN_SUCCESS

        # 检测交易面板（已登录的另一个标志）
        if 'trade_panel' in self.templates_cache:
            if self._match_template(screenshot, self.templates_cache['trade_panel']):
                logger.info("Detected trade panel - logged in")
                return THSState.LOGIN_SUCCESS

        return THSState.LOGIN_UNKNOWN

    def _check_trade_state(self, screenshot: np.ndarray,
                          login_state: THSState,
                          tab_state: THSState) -> THSState:
        """
        检测交易状态

        Args:
            screenshot: 屏幕截图
            login_state: 登录状态
            tab_state: Tab状态

        Returns:
            THSState: 交易状态
        """
        # 必须已登录且在交易Tab
        if login_state != THSState.LOGIN_SUCCESS:
            return THSState.TRADE_LOCKED

        if tab_state != THSState.TAB_TRADE:
            return THSState.TRADE_LOCKED

        # 检查是否在交易时间
        if not self._is_trading_hours():
            logger.info("Outside trading hours")
            return THSState.TRADE_LOCKED

        # 检测是否有确认对话框
        if 'confirm_button' in self.templates_cache:
            if self._match_template(screenshot, self.templates_cache['confirm_button']):
                logger.info("Detected confirmation dialog")
                return THSState.TRADE_CONFIRMING

        return THSState.TRADE_READY

    def _match_template(self, image: np.ndarray, template: np.ndarray,
                        threshold: float = 0.8) -> bool:
        """
        模板匹配

        Args:
            image: 待匹配图像
            template: 模板图像
            threshold: 匹配阈值

        Returns:
            bool: 是否匹配
        """
        try:
            if image is None or template is None:
                return False

            # 执行模板匹配
            result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            return max_val >= threshold

        except Exception as e:
            logger.error(f"Template matching failed: {e}")
            return False

    def _is_trading_hours(self) -> bool:
        """
        检查是否在交易时间

        Returns:
            bool: 是否在交易时间
        """
        import datetime
        now = datetime.datetime.now()

        # 周末不交易
        if now.weekday() >= 5:  # 周六=5, 周日=6
            return False

        # 交易时间：9:30-11:30, 13:00-15:00
        current_time = now.time()
        morning_start = datetime.time(9, 30)
        morning_end = datetime.time(11, 30)
        afternoon_start = datetime.time(13, 0)
        afternoon_end = datetime.time(15, 0)

        return (
            (morning_start <= current_time <= morning_end) or
            (afternoon_start <= current_time <= afternoon_end)
        )

    def capture_template(self, template_name: str, region: Tuple[int, int, int, int] = None):
        """
        捕获并保存模板图像

        Args:
            template_name: 模板名称
            region: 截图区域 (x, y, width, height)
        """
        try:
            if region:
                screenshot = ImageGrab.grab(bbox=region)
            else:
                # 交互式选择区域
                print("Move mouse to top-left corner and press Enter...")
                input()
                x1, y1 = pyautogui.position()

                print("Move mouse to bottom-right corner and press Enter...")
                input()
                x2, y2 = pyautogui.position()

                region = (x1, y1, x2-x1, y2-y1)
                screenshot = ImageGrab.grab(bbox=region)

            # 保存模板
            template_path = os.path.join(self.templates_dir, f"{template_name}.png")
            screenshot.save(template_path)

            # 更新缓存
            template_cv = cv2.imread(template_path)
            self.templates_cache[template_name] = template_cv

            logger.info(f"Template saved: {template_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to capture template: {e}")
            return False

    def get_state_summary(self) -> Dict:
        """
        获取状态摘要

        Returns:
            Dict: 状态摘要信息
        """
        if not self.last_check_result:
            return {"status": "No check performed"}

        result = self.last_check_result
        return {
            "timestamp": result.timestamp,
            "ready_for_trading": result.is_ready_for_trading(),
            "window": result.window_state.value,
            "tab": result.tab_state.value,
            "login": result.login_state.value,
            "trade": result.trade_state.value,
            "details": result.details
        }


def main():
    """测试状态检测器"""
    detector = THSStateDetector()

    while True:
        print("\n=== 同花顺状态检测器 ===")
        print("1. 执行全面状态检测")
        print("2. 捕获模板图像")
        print("3. 查看最近检测结果")
        print("4. 退出")

        choice = input("\n请选择操作: ")

        if choice == "1":
            result = detector.check_all_states()
            print(f"\n检测结果:")
            print(f"  窗口状态: {result.window_state.value}")
            print(f"  Tab状态: {result.tab_state.value}")
            print(f"  登录状态: {result.login_state.value}")
            print(f"  交易状态: {result.trade_state.value}")
            print(f"  可以交易: {result.is_ready_for_trading()}")

        elif choice == "2":
            name = input("输入模板名称: ")
            detector.capture_template(name)

        elif choice == "3":
            summary = detector.get_state_summary()
            import json
            print(json.dumps(summary, indent=2, ensure_ascii=False))

        elif choice == "4":
            break

        else:
            print("无效选择")


if __name__ == "__main__":
    main()