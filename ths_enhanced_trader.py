"""
增强版同花顺交易器
集成状态检测、自动恢复和登录管理功能
"""

import time
import logging
from typing import Optional, List
from ths_mac_trader import THSMacTrader, Position
from ths_state_detector import THSStateDetector, THSState
from ths_auto_recovery import THSAutoRecovery, AutoRecoveryDecorator
from ths_login_manager import THSLoginManager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class THSEnhancedTrader(THSMacTrader):
    """
    增强版同花顺交易器
    在原有交易功能基础上增加：
    1. 自动状态检测
    2. 自动故障恢复
    3. 自动登录管理
    4. 智能重试机制
    """

    def __init__(self, auto_recovery: bool = True, auto_login: bool = True):
        """
        初始化增强交易器

        Args:
            auto_recovery: 是否启用自动恢复
            auto_login: 是否启用自动登录
        """
        super().__init__()

        # 初始化各个管理器
        self.state_detector = THSStateDetector()
        self.auto_recovery = THSAutoRecovery(trader_instance=self) if auto_recovery else None
        self.login_manager = THSLoginManager(trader_instance=self) if auto_login else None

        # 如果启用自动恢复，将登录管理器注入
        if self.auto_recovery and self.login_manager:
            self.auto_recovery.set_login_manager(self.login_manager)

        # 配置
        self.enable_auto_recovery = auto_recovery
        self.enable_auto_login = auto_login
        self.max_retries = 3
        self.retry_delay = 2

        # 统计信息
        self.trade_stats = {
            'total_orders': 0,
            'successful_orders': 0,
            'failed_orders': 0,
            'recovery_count': 0
        }

        logger.info(f"Enhanced trader initialized - Auto Recovery: {auto_recovery}, Auto Login: {auto_login}")

    def _ensure_ready(self) -> bool:
        """确保系统处于就绪状态"""
        if not self.enable_auto_recovery:
            # 如果禁用自动恢复，只做基本检查
            return self.activate_ths_window()

        # 使用自动恢复确保就绪
        return self.auto_recovery.ensure_trading_ready()

    def buy(self, code: str, price: float, quantity: int, confirm: bool = False) -> bool:
        """
        增强版买入方法，带自动恢复

        Args:
            code: 股票代码
            price: 买入价格
            quantity: 买入数量
            confirm: 是否自动确认

        Returns:
            bool: 是否成功
        """
        logger.info(f"Enhanced buy order: {code} @ {price} x {quantity}")
        self.trade_stats['total_orders'] += 1

        for attempt in range(self.max_retries):
            try:
                # 确保系统就绪
                if not self._ensure_ready():
                    logger.error(f"System not ready for trading (attempt {attempt + 1})")
                    time.sleep(self.retry_delay)
                    continue

                # 执行买入
                success = super().buy(code, price, quantity, confirm)

                if success:
                    self.trade_stats['successful_orders'] += 1
                    logger.info(f"Buy order successful: {code}")
                    return True

                logger.warning(f"Buy order failed (attempt {attempt + 1})")

            except Exception as e:
                logger.error(f"Buy order exception: {e}")

            # 重试前等待
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)

        self.trade_stats['failed_orders'] += 1
        logger.error(f"Buy order failed after {self.max_retries} attempts")
        return False

    def sell(self, code: str, price: float, quantity: int, confirm: bool = False) -> bool:
        """
        增强版卖出方法，带自动恢复

        Args:
            code: 股票代码
            price: 卖出价格
            quantity: 卖出数量
            confirm: 是否自动确认

        Returns:
            bool: 是否成功
        """
        logger.info(f"Enhanced sell order: {code} @ {price} x {quantity}")
        self.trade_stats['total_orders'] += 1

        for attempt in range(self.max_retries):
            try:
                # 确保系统就绪
                if not self._ensure_ready():
                    logger.error(f"System not ready for trading (attempt {attempt + 1})")
                    time.sleep(self.retry_delay)
                    continue

                # 执行卖出
                success = super().sell(code, price, quantity, confirm)

                if success:
                    self.trade_stats['successful_orders'] += 1
                    logger.info(f"Sell order successful: {code}")
                    return True

                logger.warning(f"Sell order failed (attempt {attempt + 1})")

            except Exception as e:
                logger.error(f"Sell order exception: {e}")

            # 重试前等待
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)

        self.trade_stats['failed_orders'] += 1
        logger.error(f"Sell order failed after {self.max_retries} attempts")
        return False

    def clear_all_positions(self, positions: List[Position] = None,
                           confirm: bool = False,
                           use_market_price: bool = False) -> bool:
        """
        增强版清仓方法，带自动恢复

        Args:
            positions: 持仓列表
            confirm: 是否自动确认
            use_market_price: 是否使用市价

        Returns:
            bool: 是否成功
        """
        logger.info("Enhanced clear all positions")

        # 确保系统就绪
        if not self._ensure_ready():
            logger.error("System not ready for clearing positions")
            return False

        # 执行清仓
        return super().clear_all_positions(positions, confirm, use_market_price)

    def batch_orders(self, orders: list, interval: float = 2.0) -> dict:
        """
        批量下单，带进度跟踪和失败恢复

        Args:
            orders: 订单列表，每个订单为 (code, price, quantity, direction)
            interval: 订单间隔时间

        Returns:
            dict: 执行结果统计
        """
        logger.info(f"Starting batch orders: {len(orders)} orders")

        results = {
            'total': len(orders),
            'successful': 0,
            'failed': 0,
            'details': []
        }

        for i, order in enumerate(orders, 1):
            code, price, quantity, direction = order
            logger.info(f"Processing order {i}/{len(orders)}: {code} {direction}")

            try:
                if direction.lower() == 'buy':
                    success = self.buy(code, price, quantity, confirm=False)
                elif direction.lower() == 'sell':
                    success = self.sell(code, price, quantity, confirm=False)
                else:
                    logger.error(f"Unknown direction: {direction}")
                    success = False

                if success:
                    results['successful'] += 1
                else:
                    results['failed'] += 1

                results['details'].append({
                    'order': order,
                    'success': success,
                    'index': i
                })

            except Exception as e:
                logger.error(f"Order {i} exception: {e}")
                results['failed'] += 1
                results['details'].append({
                    'order': order,
                    'success': False,
                    'error': str(e),
                    'index': i
                })

            # 间隔等待（最后一个订单不等待）
            if i < len(orders):
                time.sleep(interval)

        logger.info(f"Batch orders complete - Success: {results['successful']}, Failed: {results['failed']}")
        return results

    def check_system_status(self) -> dict:
        """
        检查系统状态

        Returns:
            dict: 系统状态信息
        """
        state = self.state_detector.check_all_states()

        status = {
            'timestamp': time.time(),
            'ready_for_trading': state.is_ready_for_trading(),
            'window_state': state.window_state.value,
            'tab_state': state.tab_state.value,
            'login_state': state.login_state.value,
            'trade_state': state.trade_state.value,
            'auto_recovery_enabled': self.enable_auto_recovery,
            'auto_login_enabled': self.enable_auto_login
        }

        # 添加统计信息
        if self.auto_recovery:
            status['recovery_stats'] = self.auto_recovery.get_recovery_stats()

        status['trade_stats'] = self.trade_stats

        return status

    def setup_login_credentials(self):
        """设置登录凭证"""
        if not self.login_manager:
            logger.error("Login manager not initialized")
            return False

        return self.login_manager.setup_credentials_interactive()

    def perform_login(self, account_name: str = None) -> bool:
        """执行登录"""
        if not self.login_manager:
            logger.error("Login manager not initialized")
            return False

        return self.login_manager.login(account_name)

    def monitor_and_trade(self, monitor_function, interval: int = 60):
        """
        监控模式，定期检查并执行交易

        Args:
            monitor_function: 监控函数，返回需要执行的订单列表
            interval: 检查间隔（秒）
        """
        logger.info(f"Starting monitor mode with {interval}s interval")

        while True:
            try:
                # 检查系统状态
                status = self.check_system_status()

                if not status['ready_for_trading']:
                    logger.warning("System not ready, attempting recovery...")
                    if self.enable_auto_recovery:
                        self._ensure_ready()
                    else:
                        logger.error("Auto recovery disabled, skipping this cycle")
                        time.sleep(interval)
                        continue

                # 调用监控函数获取订单
                orders = monitor_function()

                if orders:
                    logger.info(f"Monitor generated {len(orders)} orders")
                    results = self.batch_orders(orders)
                    logger.info(f"Orders executed - Success: {results['successful']}, Failed: {results['failed']}")
                else:
                    logger.debug("No orders generated by monitor")

                # 等待下一个周期
                time.sleep(interval)

            except KeyboardInterrupt:
                logger.info("Monitor stopped by user")
                break

            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(interval)

    def get_statistics(self) -> dict:
        """获取交易统计信息"""
        stats = self.trade_stats.copy()

        # 计算成功率
        if stats['total_orders'] > 0:
            stats['success_rate'] = stats['successful_orders'] / stats['total_orders']
        else:
            stats['success_rate'] = 0

        # 添加恢复统计
        if self.auto_recovery:
            recovery_stats = self.auto_recovery.get_recovery_stats()
            stats['recovery_stats'] = recovery_stats

        return stats


def example_monitor_function():
    """
    示例监控函数
    实际使用时应该根据市场数据、策略等生成订单
    """
    import random

    # 模拟生成订单
    if random.random() > 0.7:  # 30%概率生成订单
        return [
            ("600000", 10.5, 100, "buy"),
        ]
    return []


def main():
    """测试增强版交易器"""
    trader = THSEnhancedTrader(auto_recovery=True, auto_login=True)

    while True:
        print("\n=== 增强版同花顺交易器 ===")
        print("1. 检查系统状态")
        print("2. 设置登录凭证")
        print("3. 执行自动登录")
        print("4. 测试买入")
        print("5. 测试卖出")
        print("6. 批量下单测试")
        print("7. 启动监控模式")
        print("8. 查看统计信息")
        print("9. 退出")

        choice = input("\n请选择操作: ")

        if choice == "1":
            status = trader.check_system_status()
            import json
            print(json.dumps(status, indent=2, ensure_ascii=False))

        elif choice == "2":
            trader.setup_login_credentials()

        elif choice == "3":
            success = trader.perform_login()
            print(f"登录{'成功' if success else '失败'}")

        elif choice == "4":
            code = input("股票代码: ")
            price = float(input("价格: "))
            quantity = int(input("数量: "))
            success = trader.buy(code, price, quantity, confirm=False)
            print(f"买入{'成功' if success else '失败'}")

        elif choice == "5":
            code = input("股票代码: ")
            price = float(input("价格: "))
            quantity = int(input("数量: "))
            success = trader.sell(code, price, quantity, confirm=False)
            print(f"卖出{'成功' if success else '失败'}")

        elif choice == "6":
            orders = [
                ("600000", 10.5, 100, "buy"),
                ("603993", 25.0, 100, "sell"),
            ]
            results = trader.batch_orders(orders)
            print(f"批量下单结果: {results}")

        elif choice == "7":
            print("启动监控模式（按Ctrl+C停止）...")
            trader.monitor_and_trade(example_monitor_function, interval=30)

        elif choice == "8":
            stats = trader.get_statistics()
            import json
            print(json.dumps(stats, indent=2, ensure_ascii=False))

        elif choice == "9":
            break

        else:
            print("无效选择")


if __name__ == "__main__":
    main()