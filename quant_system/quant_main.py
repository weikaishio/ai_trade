"""
量化交易系统主程序

支持多种运行模式：
1. 自动监控模式 - 定时循环检查和执行
2. 手动分析模式 - 一次性分析持仓
3. 测试模式 - 模拟运行不实际交易
"""

import sys
import time
import logging
import signal
from typing import List, Optional
from pathlib import Path
from datetime import datetime
import argparse

# 添加当前目录和父目录到路径
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(current_dir))  # 优先从quant_system导入
sys.path.insert(1, str(parent_dir))   # 然后从父目录导入ths_mac_trader

# 支持两种导入方式：作为脚本运行和作为包导入
try:
    # 尝试相对导入（作为包运行时）
    from .market_data_client import MarketDataClient
    from .model_client import ModelClient
    from .decision_engine import DecisionEngine, Position, TradeSignal
    from .risk_manager import RiskManager
    from .config_quant import (
        AUTO_CHECK_INTERVAL,
        POSITION_REFRESH_INTERVAL,
        TEST_MODE,
        DRY_RUN,
        MOCK_DATA_ENABLED,
        MOCK_POSITIONS,
        AUTOMATION_MODE,
        AUTO_OCR_ENABLED,
        AUTO_TRADING_ENABLED,
        is_trading_time
    )
except ImportError:
    # 使用绝对导入（作为脚本直接运行时）
    from market_data_client import MarketDataClient
    from model_client import ModelClient
    from decision_engine import DecisionEngine, Position, TradeSignal
    from risk_manager import RiskManager
    from config_quant import (
        AUTO_CHECK_INTERVAL,
        POSITION_REFRESH_INTERVAL,
        TEST_MODE,
        DRY_RUN,
        MOCK_DATA_ENABLED,
        MOCK_POSITIONS,
        AUTOMATION_MODE,
        AUTO_OCR_ENABLED,
        AUTO_TRADING_ENABLED,
        is_trading_time
    )

# 配置日志
log_dir = current_dir / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "quant_system.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(log_file)),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class QuantTradingSystem:
    """
    量化交易系统主类

    集成所有核心组件，提供统一的交易流程
    """

    def __init__(self, test_mode: bool = TEST_MODE, dry_run: bool = DRY_RUN):
        """
        初始化量化交易系统

        Args:
            test_mode: 测试模式
            dry_run: 模拟运行（不实际交易）
        """
        self.test_mode = test_mode
        self.dry_run = dry_run
        self.running = True  # 运行标志（用于优雅退出）

        logger.info("=" * 60)
        logger.info("量化交易系统启动")
        logger.info(f"测试模式: {test_mode}")
        logger.info(f"模拟运行: {dry_run}")
        logger.info("=" * 60)

        # 初始化组件
        self.market_client = MarketDataClient()
        self.model_client = ModelClient()
        self.decision_engine = DecisionEngine()

        # 确保数据目录存在
        risk_data_dir = current_dir / "data" / "risk"
        risk_data_dir.mkdir(parents=True, exist_ok=True)
        self.risk_manager = RiskManager(data_dir=str(risk_data_dir))

        # 尝试导入交易客户端
        try:
            from ths_mac_trader import THSMacTrader
            self.trader = THSMacTrader()
            self.trader_available = True
            logger.info("THSMacTrader 加载成功")
        except ImportError:
            self.trader = None
            self.trader_available = False
            logger.warning("THSMacTrader 未找到，仅支持模拟交易")

        # 尝试导入OCR模块
        try:
            from ocr_positions import PositionOCR
            self.ocr = PositionOCR()
            self.ocr_available = True
            logger.info("OCR模块加载成功")
        except ImportError:
            self.ocr = None
            self.ocr_available = False
            logger.warning("OCR模块未找到，需要手动输入持仓")

        logger.info("系统初始化完成")

        # 设置信号处理器
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """设置信号处理器（优雅退出）"""
        def signal_handler(signum, frame):
            sig_name = signal.Signals(signum).name
            logger.info(f"\n收到信号 {sig_name}，准备优雅退出...")
            self.running = False

        # 注册信号处理
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # kill命令

    def stop(self) -> None:
        """停止系统"""
        logger.info("停止量化交易系统...")
        self.running = False

    def _check_critical_risk(self) -> bool:
        """
        检查是否存在严重风险

        Returns:
            bool: True表示存在严重风险，需要停止系统
        """
        # 检查熔断机制
        if self.risk_manager.circuit_breaker_active:
            logger.critical("⚠️ 熔断机制已触发！")
            logger.critical(f"冷却时间至: {self.risk_manager.circuit_breaker_until}")
            return True

        # 检查日损失限制
        daily_summary = self.risk_manager.get_daily_summary()
        if daily_summary['total_profit_loss'] < -50000:  # 示例：单日亏损超过5万
            logger.critical(f"⚠️ 单日亏损过大: {daily_summary['total_profit_loss']:.2f}元")
            return True

        return False

    def get_positions(self) -> List[Position]:
        """
        获取持仓列表

        支持多种方式：
        1. 模拟数据（测试模式）
        2. OCR识别
        3. 手动输入
        """
        # 测试模式使用模拟数据
        if self.test_mode or MOCK_DATA_ENABLED:
            logger.info("使用模拟持仓数据")
            return [
                Position(
                    code=p["code"],
                    name=p["name"],
                    quantity=p["quantity"],
                    cost_price=p["cost_price"],
                    holding_days=p.get("holding_days", 0)
                )
                for p in MOCK_POSITIONS
            ]

        # 尝试OCR
        if self.ocr_available and self.ocr and AUTO_OCR_ENABLED:
            # 根据自动化模式选择方法
            if AUTOMATION_MODE:
                logger.info("使用OCR自动识别持仓（自动化模式）...")
                try:
                    # 使用自动化方法，无需人工交互
                    positions = self.ocr.get_positions_automatic()
                    if positions:
                        logger.info(f"OCR自动识别成功，获取 {len(positions)} 个持仓")
                        return positions
                    else:
                        logger.warning("OCR自动识别未获取到持仓，返回空列表")
                        # 自动化模式下不回退到手动输入
                        return []
                except Exception as e:
                    logger.warning(f"OCR自动识别失败: {e}")
                    # 自动化模式下不回退到手动输入
                    return []
            else:
                logger.info("使用OCR识别持仓（交互式模式）...")
                try:
                    # 使用交互式方法
                    positions = self.ocr.get_positions_interactive()
                    if positions:
                        logger.info(f"OCR识别成功，获取 {len(positions)} 个持仓")
                        return positions
                except Exception as e:
                    logger.warning(f"OCR识别失败: {e}")

        # 手动输入（仅在非自动化模式下）
        if not AUTOMATION_MODE:
            if self.trader_available and hasattr(self.trader, 'get_positions_from_input'):
                logger.info("请手动输入持仓信息...")
                return self.trader.get_positions_from_input()
            else:
                logger.error("无法获取持仓数据")
                return []
        else:
            logger.warning("自动化模式下无法获取持仓，返回空列表")
            return []

    def analyze_and_execute(
        self,
        positions: List[Position],
        total_portfolio_value: Optional[float] = None
    ) -> List[TradeSignal]:
        """
        分析持仓并执行交易

        Args:
            positions: 持仓列表
            total_portfolio_value: 总资产价值

        Returns:
            执行的交易信号列表
        """
        if not positions:
            logger.warning("没有持仓需要分析")
            return []

        logger.info(f"开始分析 {len(positions)} 个持仓...")

        # 1. 获取市场数据
        logger.info("获取实时行情...")
        stock_codes = [p.code for p in positions]
        market_data_dict = self.market_client.get_batch_stock_data(stock_codes)

        # 更新持仓当前价
        for position in positions:
            market_data = market_data_dict.get(position.code)
            if market_data:
                position.current_price = market_data.current_price

        # 2. 获取模型评分
        logger.info("获取模型评分...")
        positions_data = {
            p.code: {
                "current_price": p.current_price,
                "holding_days": p.holding_days,
                "profit_loss_ratio": p.calculate_profit_loss_ratio()
            }
            for p in positions if p.current_price > 0
        }

        model_scores_dict = self.model_client.get_batch_scores(
            stock_codes,
            positions_data
        )

        # 3. 决策分析
        logger.info("执行决策分析...")
        signals = self.decision_engine.analyze_positions_batch(
            positions,
            market_data_dict,
            model_scores_dict
        )

        # 4. 过滤卖出信号
        sell_signals = self.decision_engine.filter_sell_signals(signals)

        if not sell_signals:
            logger.info("没有需要执行的卖出信号")
            return []

        logger.info(f"生成 {len(sell_signals)} 个卖出信号")

        # 5. 风险检查和执行
        executed_signals = []

        for signal in sell_signals:
            # 找到对应的持仓
            position = next((p for p in positions if p.code == signal.stock_code), None)
            if not position:
                continue

            # 风险检查
            risk_report = self.risk_manager.check_trade_permission(
                signal,
                position,
                total_portfolio_value or 0.0
            )

            # 输出分析结果
            self._print_signal_info(signal, position, risk_report)

            # 执行交易
            if risk_report.passed:
                if self._execute_trade(signal, position):
                    executed_signals.append(signal)
            else:
                logger.warning(f"风险检查未通过: {signal.stock_code}")
                for error in risk_report.errors:
                    logger.warning(f"  - {error}")

        logger.info(f"执行完成: {len(executed_signals)}/{len(sell_signals)}")
        return executed_signals

    def _execute_trade(self, signal: TradeSignal, position: Position) -> bool:
        """
        执行单笔交易

        Args:
            signal: 交易信号
            position: 持仓信息

        Returns:
            是否执行成功
        """
        if self.dry_run or self.test_mode:
            logger.info(f"[模拟] 卖出 {signal.stock_code} {signal.stock_name} {signal.quantity}股")
            # 记录模拟交易
            self.risk_manager.record_trade(
                stock_code=signal.stock_code,
                stock_name=signal.stock_name,
                action="simulated_sell",
                quantity=signal.quantity,
                price=signal.price or 0.0,
                profit_loss=position.calculate_profit_loss()
            )
            return True

        # 实际交易
        if not self.trader_available:
            logger.error("交易客户端不可用")
            return False

        try:
            logger.info(f"执行交易: 卖出 {signal.stock_code} {signal.quantity}股 @{signal.price}")

            # 调用THSMacTrader执行卖出
            success = self.trader.sell(
                code=signal.stock_code,
                price=signal.price or 0.0,
                quantity=signal.quantity,
                confirm=False  # 需要手动确认
            )

            if success:
                # 记录交易
                self.risk_manager.record_trade(
                    stock_code=signal.stock_code,
                    stock_name=signal.stock_name,
                    action="sell",
                    quantity=signal.quantity,
                    price=signal.price or 0.0,
                    profit_loss=position.calculate_profit_loss()
                )
                logger.info(f"交易成功: {signal.stock_code}")
                return True
            else:
                logger.error(f"交易失败: {signal.stock_code}")
                return False

        except Exception as e:
            logger.error(f"执行交易异常: {e}", exc_info=True)
            return False

    def _print_signal_info(self, signal: TradeSignal, position: Position, risk_report):
        """打印交易信号详情"""
        print("\n" + "=" * 60)
        print(f"股票: {signal.stock_name} ({signal.stock_code})")
        print(f"动作: {signal.action.value.upper()} (优先级: {signal.priority.value})")
        print(f"数量: {signal.quantity}股 @ {signal.price:.2f}元")
        print(f"置信度: {signal.confidence:.1%}")
        print(f"\n持仓信息:")
        print(f"  成本价: {position.cost_price:.2f}元")
        print(f"  当前价: {position.current_price:.2f}元")
        print(f"  盈亏: {position.calculate_profit_loss():.2f}元 ({position.calculate_profit_loss_ratio():.2%})")
        print(f"  持仓天数: {position.holding_days}天")
        print(f"\n决策原因:")
        for i, reason in enumerate(signal.reasons, 1):
            print(f"  {i}. {reason}")
        print(f"\n风险评估: {risk_report.risk_level.value.upper()}")
        print(f"是否通过: {'是' if risk_report.passed else '否'}")
        if risk_report.warnings:
            print(f"警告:")
            for warning in risk_report.warnings:
                print(f"  - {warning}")
        if risk_report.errors:
            print(f"错误:")
            for error in risk_report.errors:
                print(f"  - {error}")
        print("=" * 60)

    def run_once(self, positions: Optional[List[Position]] = None) -> None:
        """
        执行一次分析和交易

        Args:
            positions: 持仓列表（如果为None则自动获取）
        """
        logger.info("\n" + "=" * 60)
        logger.info("开始执行分析")
        logger.info("=" * 60)

        # 获取持仓
        if positions is None:
            positions = self.get_positions()

        if not positions:
            logger.warning("没有持仓数据")
            return

        # 计算总资产（简化处理）
        total_value = sum(p.calculate_position_value() for p in positions)
        logger.info(f"总持仓市值: {total_value:.2f}元")

        # 执行分析和交易
        self.analyze_and_execute(positions, total_value)

        # 打印日报
        self._print_daily_summary()

    def run_auto(self, interval: int = AUTO_CHECK_INTERVAL) -> None:
        """
        自动监控模式

        Args:
            interval: 检查间隔（秒）
        """
        logger.info("\n" + "=" * 60)
        logger.info(f"启动自动监控模式 (间隔: {interval}秒)")
        logger.info("按 Ctrl+C 或发送 SIGTERM 信号停止")
        logger.info("=" * 60)

        positions = None
        last_refresh = None

        try:
            while self.running:
                # 检查交易时间
                if not is_trading_time():
                    logger.info("非交易时间，等待中...")
                    time.sleep(60)  # 非交易时间每分钟检查一次
                    continue

                # 检查严重风险
                if self._check_critical_risk():
                    logger.critical("=" * 60)
                    logger.critical("检测到严重风险，系统自动停止！")
                    logger.critical("=" * 60)
                    break

                # 刷新持仓数据
                current_time = datetime.now()
                if last_refresh is None or \
                   (current_time - last_refresh).total_seconds() >= POSITION_REFRESH_INTERVAL:
                    logger.info("刷新持仓数据...")
                    positions = self.get_positions()
                    last_refresh = current_time

                # 执行分析
                if positions:
                    self.run_once(positions)
                else:
                    logger.warning("无持仓数据，跳过本次检查")

                # 等待下次检查
                logger.info(f"等待 {interval} 秒后下次检查...")
                for _ in range(interval):
                    if not self.running:
                        break
                    time.sleep(1)

        except KeyboardInterrupt:
            logger.info("\n用户中断，退出自动监控模式")
        except Exception as e:
            logger.error(f"自动监控异常: {e}", exc_info=True)
        finally:
            logger.info("自动监控模式已停止")

    def _print_daily_summary(self) -> None:
        """打印当日摘要"""
        summary = self.risk_manager.get_daily_summary()
        stats = self.risk_manager.get_risk_statistics()

        print("\n" + "=" * 60)
        print("当日交易摘要")
        print("=" * 60)
        print(f"交易次数: {summary['trade_count']}")
        print(f"交易金额: {summary['total_amount']:.2f}元")
        print(f"盈亏: {summary['total_profit_loss']:.2f}元")
        print(f"\n最近7天统计:")
        print(f"  总交易: {stats['trade_count']}笔")
        print(f"  胜率: {stats['win_rate']:.1%}")
        print(f"  总盈亏: {stats['total_profit_loss']:.2f}元")
        print(f"  最大盈利: {stats['max_profit']:.2f}元")
        print(f"  最大亏损: {stats['max_loss']:.2f}元")
        print("=" * 60)


# ============================================================================
# 命令行接口
# ============================================================================

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="智能量化交易系统")

    parser.add_argument(
        "--mode",
        choices=["once", "auto"],
        default="auto",
        help="运行模式: once=单次分析, auto=自动监控"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="测试模式（使用模拟数据）"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="模拟运行（不实际交易）"
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=AUTO_CHECK_INTERVAL,
        help="自动模式检查间隔（秒）"
    )

    args = parser.parse_args()

    # 创建日志目录
    Path("logs").mkdir(exist_ok=True)

    # 创建系统实例
    system = QuantTradingSystem(
        test_mode=args.test,
        dry_run=args.dry_run
    )

    # 运行
    if args.mode == "once":
        system.run_once()
    elif args.mode == "auto":
        system.run_auto(interval=args.interval)


if __name__ == "__main__":
    main()
