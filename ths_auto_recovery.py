"""
同花顺自动恢复管理器
根据检测到的状态自动执行恢复操作
"""

import time
import logging
import subprocess
from typing import Optional, Dict, Callable, List
from dataclasses import dataclass
from enum import Enum
import pyautogui
from ths_state_detector import THSStateDetector, THSState, StateCheckResult

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RecoveryAction(Enum):
    """恢复动作枚举"""
    ACTIVATE_WINDOW = "activate_window"
    SWITCH_TO_TRADE_TAB = "switch_to_trade_tab"
    LOGIN = "login"
    DISMISS_TIMEOUT_DIALOG = "dismiss_timeout_dialog"
    RESTART_APP = "restart_app"
    NONE = "none"


@dataclass
class RecoveryPlan:
    """恢复计划"""
    actions: List[RecoveryAction]
    priority: int  # 优先级，数字越小优先级越高
    estimated_time: float  # 预计耗时（秒）
    retry_count: int = 0
    max_retries: int = 3


class THSAutoRecovery:
    """同花顺自动恢复管理器"""

    def __init__(self, trader_instance=None):
        """
        初始化恢复管理器

        Args:
            trader_instance: THSMacTrader实例，用于执行交易操作
        """
        self.detector = THSStateDetector()
        self.trader = trader_instance
        self.recovery_history = []
        self.max_recovery_attempts = 3
        self.recovery_timeout = 60  # 单次恢复最大耗时

        # 恢复策略映射
        self.recovery_strategies = {
            THSState.WINDOW_NOT_FOUND: self._recover_window_not_found,
            THSState.WINDOW_BACKGROUND: self._recover_window_background,
            THSState.TAB_UNKNOWN: self._recover_tab_unknown,
            THSState.LOGIN_REQUIRED: self._recover_login_required,
            THSState.LOGIN_TIMEOUT: self._recover_login_timeout,
        }

        # 初始化登录管理器
        self.login_manager = None  # 将在后面实现

    def ensure_trading_ready(self, max_wait: float = 30) -> bool:
        """
        确保系统处于可交易状态

        Args:
            max_wait: 最大等待时间

        Returns:
            bool: 是否成功恢复到可交易状态
        """
        start_time = time.time()
        attempt = 0

        while time.time() - start_time < max_wait:
            attempt += 1
            logger.info(f"Recovery attempt {attempt}")

            # 1. 检测当前状态
            state_result = self.detector.check_all_states()

            # 2. 如果已就绪，直接返回
            if state_result.is_ready_for_trading():
                logger.info("System is ready for trading")
                return True

            # 3. 生成恢复计划
            recovery_plan = self._create_recovery_plan(state_result)

            if not recovery_plan or not recovery_plan.actions:
                logger.warning("No recovery actions needed or available")
                return False

            # 4. 执行恢复计划
            success = self._execute_recovery_plan(recovery_plan, state_result)

            if not success:
                logger.error(f"Recovery plan execution failed")
                if attempt >= self.max_recovery_attempts:
                    logger.error("Max recovery attempts reached")
                    return False

                # 等待一段时间后重试
                time.sleep(2)
                continue

            # 5. 验证恢复结果
            time.sleep(1)  # 给系统一些响应时间
            verify_result = self.detector.check_all_states()

            if verify_result.is_ready_for_trading():
                logger.info("System successfully recovered to trading ready state")
                return True

            logger.warning("Recovery executed but system not ready, retrying...")

        logger.error(f"Failed to ensure trading ready within {max_wait} seconds")
        return False

    def _create_recovery_plan(self, state: StateCheckResult) -> RecoveryPlan:
        """
        根据状态创建恢复计划

        Args:
            state: 当前状态

        Returns:
            RecoveryPlan: 恢复计划
        """
        actions = []

        # 按优先级排序的恢复动作
        # 1. 首先处理窗口问题
        if state.window_state == THSState.WINDOW_NOT_FOUND:
            actions.append(RecoveryAction.RESTART_APP)
            return RecoveryPlan(actions=actions, priority=1, estimated_time=10)

        if state.window_state == THSState.WINDOW_BACKGROUND:
            actions.append(RecoveryAction.ACTIVATE_WINDOW)

        # 2. 处理登录超时（优先级高于普通登录）
        if state.login_state == THSState.LOGIN_TIMEOUT:
            actions.append(RecoveryAction.DISMISS_TIMEOUT_DIALOG)
            actions.append(RecoveryAction.LOGIN)

        # 3. 处理未登录
        elif state.login_state == THSState.LOGIN_REQUIRED:
            actions.append(RecoveryAction.LOGIN)

        # 4. 处理Tab切换（只有在登录后才有意义）
        if state.login_state == THSState.LOGIN_SUCCESS:
            if state.tab_state != THSState.TAB_TRADE:
                actions.append(RecoveryAction.SWITCH_TO_TRADE_TAB)

        if not actions:
            return RecoveryPlan(actions=[RecoveryAction.NONE], priority=99, estimated_time=0)

        # 计算优先级和预计时间
        priority = self._calculate_priority(actions)
        estimated_time = self._estimate_recovery_time(actions)

        return RecoveryPlan(
            actions=actions,
            priority=priority,
            estimated_time=estimated_time
        )

    def _calculate_priority(self, actions: List[RecoveryAction]) -> int:
        """计算恢复计划优先级"""
        priority_map = {
            RecoveryAction.RESTART_APP: 1,
            RecoveryAction.ACTIVATE_WINDOW: 2,
            RecoveryAction.DISMISS_TIMEOUT_DIALOG: 3,
            RecoveryAction.LOGIN: 4,
            RecoveryAction.SWITCH_TO_TRADE_TAB: 5,
            RecoveryAction.NONE: 99
        }

        if not actions:
            return 99

        # 返回最高优先级
        return min(priority_map.get(action, 99) for action in actions)

    def _estimate_recovery_time(self, actions: List[RecoveryAction]) -> float:
        """估算恢复时间"""
        time_map = {
            RecoveryAction.RESTART_APP: 10.0,
            RecoveryAction.ACTIVATE_WINDOW: 1.0,
            RecoveryAction.DISMISS_TIMEOUT_DIALOG: 2.0,
            RecoveryAction.LOGIN: 5.0,
            RecoveryAction.SWITCH_TO_TRADE_TAB: 2.0,
            RecoveryAction.NONE: 0.0
        }

        return sum(time_map.get(action, 0) for action in actions)

    def _execute_recovery_plan(self, plan: RecoveryPlan, state: StateCheckResult) -> bool:
        """
        执行恢复计划

        Args:
            plan: 恢复计划
            state: 当前状态

        Returns:
            bool: 是否成功执行
        """
        logger.info(f"Executing recovery plan with {len(plan.actions)} actions")

        for action in plan.actions:
            logger.info(f"Executing action: {action.value}")

            try:
                if action == RecoveryAction.RESTART_APP:
                    success = self._restart_app()

                elif action == RecoveryAction.ACTIVATE_WINDOW:
                    success = self._activate_window()

                elif action == RecoveryAction.DISMISS_TIMEOUT_DIALOG:
                    success = self._dismiss_timeout_dialog()

                elif action == RecoveryAction.LOGIN:
                    success = self._perform_login()

                elif action == RecoveryAction.SWITCH_TO_TRADE_TAB:
                    success = self._switch_to_trade_tab()

                elif action == RecoveryAction.NONE:
                    success = True

                else:
                    logger.warning(f"Unknown action: {action}")
                    success = False

                if not success:
                    logger.error(f"Failed to execute action: {action.value}")
                    return False

                # 记录恢复历史
                self.recovery_history.append({
                    'timestamp': time.time(),
                    'action': action.value,
                    'success': success
                })

            except Exception as e:
                logger.error(f"Exception during action {action.value}: {e}")
                return False

        return True

    def _recover_window_not_found(self, state: StateCheckResult) -> bool:
        """恢复窗口未找到状态"""
        return self._restart_app()

    def _recover_window_background(self, state: StateCheckResult) -> bool:
        """恢复窗口在后台状态"""
        return self._activate_window()

    def _recover_tab_unknown(self, state: StateCheckResult) -> bool:
        """恢复Tab未知状态"""
        return self._switch_to_trade_tab()

    def _recover_login_required(self, state: StateCheckResult) -> bool:
        """恢复需要登录状态"""
        return self._perform_login()

    def _recover_login_timeout(self, state: StateCheckResult) -> bool:
        """恢复登录超时状态"""
        # 先关闭超时对话框
        if self._dismiss_timeout_dialog():
            time.sleep(1)
            # 然后重新登录
            return self._perform_login()
        return False

    def _restart_app(self) -> bool:
        """重启应用"""
        try:
            logger.info("Restarting TongHuaShun application...")

            # 1. 先尝试正常退出
            subprocess.run(['osascript', '-e', 'tell application "同花顺" to quit'], timeout=5)
            time.sleep(2)

            # 2. 如果还在运行，强制终止
            subprocess.run(['pkill', '-f', '同花顺'], timeout=5)
            time.sleep(2)

            # 3. 启动应用
            subprocess.run(['open', '-a', '同花顺'], timeout=10)
            time.sleep(5)  # 等待应用启动

            return True

        except Exception as e:
            logger.error(f"Failed to restart app: {e}")
            return False

    def _activate_window(self) -> bool:
        """激活窗口到前台"""
        try:
            script = '''
            tell application "同花顺"
                activate
            end tell
            '''

            subprocess.run(['osascript', '-e', script], timeout=5)
            time.sleep(1)

            # 验证是否成功激活
            state = self.detector._check_window_state()
            return state == THSState.WINDOW_FOREGROUND

        except Exception as e:
            logger.error(f"Failed to activate window: {e}")
            return False

    def _dismiss_timeout_dialog(self) -> bool:
        """关闭超时对话框"""
        try:
            logger.info("Dismissing timeout dialog...")

            # 方法1：尝试点击确定按钮（如果有坐标）
            if self.trader and hasattr(self.trader, 'coords'):
                confirm_coords = self.trader.coords.get('confirm_button')
                if confirm_coords:
                    pyautogui.click(confirm_coords[0], confirm_coords[1])
                    time.sleep(1)
                    return True

            # 方法2：使用ESC键关闭
            pyautogui.press('escape')
            time.sleep(1)

            # 方法3：使用回车键确认
            pyautogui.press('return')
            time.sleep(1)

            return True

        except Exception as e:
            logger.error(f"Failed to dismiss timeout dialog: {e}")
            return False

    def _perform_login(self) -> bool:
        """执行登录操作"""
        try:
            logger.info("Performing login...")

            # 如果有登录管理器，使用它
            if self.login_manager:
                return self.login_manager.login()

            # 否则使用默认登录流程
            # 这里需要根据实际的登录界面实现
            if self.trader:
                # 假设trader有login方法
                if hasattr(self.trader, 'login'):
                    return self.trader.login()

            logger.warning("No login method available")
            return False

        except Exception as e:
            logger.error(f"Failed to perform login: {e}")
            return False

    def _switch_to_trade_tab(self) -> bool:
        """切换到交易Tab"""
        try:
            logger.info("Switching to trade tab...")

            # 方法1：使用快捷键（如果有）
            # 通常 Cmd+1, Cmd+2 等快捷键切换Tab
            pyautogui.hotkey('cmd', '2')  # 假设交易是第2个Tab
            time.sleep(1)

            # 方法2：点击Tab（如果有坐标）
            if self.trader and hasattr(self.trader, 'coords'):
                trade_tab_coords = self.trader.coords.get('trade_tab')
                if trade_tab_coords:
                    pyautogui.click(trade_tab_coords[0], trade_tab_coords[1])
                    time.sleep(1)
                    return True

            # 验证是否成功切换
            state = self.detector.check_all_states()
            return state.tab_state == THSState.TAB_TRADE

        except Exception as e:
            logger.error(f"Failed to switch to trade tab: {e}")
            return False

    def set_login_manager(self, login_manager):
        """设置登录管理器"""
        self.login_manager = login_manager

    def get_recovery_stats(self) -> Dict:
        """获取恢复统计信息"""
        if not self.recovery_history:
            return {
                "total_recoveries": 0,
                "success_rate": 0,
                "last_recovery": None
            }

        total = len(self.recovery_history)
        successful = sum(1 for r in self.recovery_history if r.get('success'))

        return {
            "total_recoveries": total,
            "successful_recoveries": successful,
            "success_rate": successful / total if total > 0 else 0,
            "last_recovery": self.recovery_history[-1] if self.recovery_history else None,
            "history": self.recovery_history[-10:]  # 最近10条记录
        }


class AutoRecoveryDecorator:
    """
    自动恢复装饰器
    用于装饰交易方法，在执行前自动确保系统就绪
    """

    def __init__(self, recovery_manager: THSAutoRecovery):
        self.recovery_manager = recovery_manager

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            # 执行前确保系统就绪
            if not self.recovery_manager.ensure_trading_ready():
                raise RuntimeError("Failed to ensure trading ready state")

            # 执行原函数
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error during {func.__name__}: {e}")
                # 可以在这里添加错误恢复逻辑
                raise

        return wrapper


def main():
    """测试自动恢复管理器"""
    recovery = THSAutoRecovery()

    while True:
        print("\n=== 同花顺自动恢复管理器 ===")
        print("1. 执行自动恢复")
        print("2. 查看恢复统计")
        print("3. 测试单个恢复动作")
        print("4. 退出")

        choice = input("\n请选择操作: ")

        if choice == "1":
            success = recovery.ensure_trading_ready()
            print(f"恢复{'成功' if success else '失败'}")

        elif choice == "2":
            stats = recovery.get_recovery_stats()
            import json
            print(json.dumps(stats, indent=2, ensure_ascii=False))

        elif choice == "3":
            print("\n可用的恢复动作:")
            for i, action in enumerate(RecoveryAction):
                print(f"{i+1}. {action.value}")

            action_choice = input("选择动作编号: ")
            try:
                action_idx = int(action_choice) - 1
                action = list(RecoveryAction)[action_idx]

                plan = RecoveryPlan(
                    actions=[action],
                    priority=1,
                    estimated_time=5
                )

                success = recovery._execute_recovery_plan(plan, None)
                print(f"执行{'成功' if success else '失败'}")

            except (ValueError, IndexError):
                print("无效选择")

        elif choice == "4":
            break

        else:
            print("无效选择")


if __name__ == "__main__":
    main()