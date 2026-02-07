"""
买入策略引擎模块

整合选股、仓位管理和执行逻辑：
1. 生成买入信号
2. 执行买入订单
3. 买入后跟踪
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

try:
    from .stock_selector import StockSelector, CandidateStock
    from .portfolio_manager import PortfolioManager, BuyRecommendation, PositionMethod
    from .decision_engine import Position, Priority
    from .market_data_client import MarketDataClient
    from .config_quant import BUY_STRATEGY_CONFIG
except ImportError:
    from stock_selector import StockSelector, CandidateStock
    from portfolio_manager import PortfolioManager, BuyRecommendation, PositionMethod
    from decision_engine import Position, Priority
    from market_data_client import MarketDataClient
    from config_quant import BUY_STRATEGY_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class BuySignal:
    """买入信号"""
    stock_code: str                     # 股票代码
    stock_name: str                     # 股票名称
    quantity: int                       # 买入数量
    price: float                        # 买入价格
    amount: float                       # 买入金额
    priority: Priority                  # 优先级
    score: float                        # 综合评分
    reasons: List[str] = field(default_factory=list)  # 买入理由
    confidence: float = 0.8             # 置信度
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "quantity": self.quantity,
            "price": self.price,
            "amount": self.amount,
            "priority": self.priority.value,
            "score": self.score,
            "reasons": self.reasons,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat()
        }


class BuyStrategy:
    """
    买入策略引擎

    整合选股器和组合管理器，生成并执行买入决策
    """

    def __init__(self, total_capital: float = 100000.0):
        """
        初始化买入策略引擎

        Args:
            total_capital: 总资金（元）
        """
        self.selector = StockSelector()
        self.portfolio_mgr = PortfolioManager(total_capital)
        self.market_client = MarketDataClient()
        self.config = BUY_STRATEGY_CONFIG

        logger.info("买入策略引擎初始化完成")

    def generate_buy_signals(
        self,
        available_cash: float,
        current_positions: List[Position],
        stock_pool: Optional[List[str]] = None,
        max_buy_count: int = 5
    ) -> List[BuySignal]:
        """
        生成买入信号

        流程：
        1. 选股 - 获取候选股票
        2. 仓位分配 - 计算每只股票的买入数量
        3. 生成信号 - 转换为买入信号

        Args:
            available_cash: 可用资金
            current_positions: 当前持仓列表
            stock_pool: 股票池（如果为None则使用默认）
            max_buy_count: 最大买入数量

        Returns:
            买入信号列表
        """
        logger.info("=" * 60)
        logger.info("开始生成买入信号")
        logger.info("=" * 60)

        # 检查是否有足够资金
        min_required_cash = self.config.get("min_position_value", 5000)
        if available_cash < min_required_cash:
            logger.warning(f"可用资金不足 ({available_cash:.2f}元 < {min_required_cash}元)")
            return []

        # 1. 选股
        logger.info("步骤1: 智能选股...")
        candidates = self.selector.get_candidate_stocks(
            stock_pool=stock_pool,
            max_count=max_buy_count * 2  # 多选一些备选
        )

        if not candidates:
            logger.warning("未选出候选股票")
            return []

        logger.info(f"选出 {len(candidates)} 只候选股票")

        # 2. 仓位分配
        logger.info("步骤2: 仓位分配...")
        recommendations = self.portfolio_mgr.allocate_positions(
            candidates,
            available_cash,
            current_positions,
            method=PositionMethod.SCORE_WEIGHTED
        )

        if not recommendations:
            logger.warning("未生成买入建议")
            return []

        logger.info(f"生成 {len(recommendations)} 个买入建议")

        # 3. 组合优化
        logger.info("步骤3: 组合优化...")
        recommendations = self.portfolio_mgr.optimize_portfolio(
            recommendations,
            current_positions
        )

        logger.info(f"优化后保留 {len(recommendations)} 个建议")

        # 4. 限制买入数量
        recommendations = recommendations[:max_buy_count]

        # 5. 转换为买入信号
        logger.info("步骤4: 生成买入信号...")
        buy_signals = []

        for rec in recommendations:
            # 确定优先级（基于评分）
            if rec.score >= 85:
                priority = Priority.HIGH
            elif rec.score >= 75:
                priority = Priority.MEDIUM
            else:
                priority = Priority.LOW

            # 计算置信度
            confidence = min(0.95, rec.score / 100)

            signal = BuySignal(
                stock_code=rec.stock_code,
                stock_name=rec.stock_name,
                quantity=rec.quantity,
                price=rec.price,
                amount=rec.amount,
                priority=priority,
                score=rec.score,
                reasons=rec.reasons,
                confidence=confidence
            )

            buy_signals.append(signal)

        # 按优先级排序
        buy_signals.sort(key=lambda s: (s.priority.value, -s.score))

        logger.info(f"生成 {len(buy_signals)} 个买入信号")
        logger.info("=" * 60)

        # 打印买入信号摘要
        self._print_buy_signals_summary(buy_signals)

        return buy_signals

    def validate_buy_signal(self, signal: BuySignal) -> tuple[bool, List[str]]:
        """
        验证买入信号

        Args:
            signal: 买入信号

        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []

        # 1. 检查买入数量（必须是100的倍数）
        if signal.quantity <= 0:
            errors.append("买入数量必须大于0")
        elif signal.quantity % 100 != 0:
            errors.append("买入数量必须是100的倍数")

        # 2. 检查价格
        if signal.price <= 0:
            errors.append("买入价格必须大于0")

        # 3. 检查金额
        min_amount = self.config.get("min_position_value", 5000)
        if signal.amount < min_amount:
            errors.append(f"买入金额过小 ({signal.amount:.2f}元 < {min_amount}元)")

        # 4. 验证实时价格
        try:
            market_data = self.market_client.get_stock_data(signal.stock_code, use_cache=False)
            if market_data:
                # 检查涨跌停
                if abs(market_data.change_percent) >= 9.9:
                    errors.append(f"股票涨跌停 ({market_data.change_percent:+.2f}%)")

                # 检查价格差异
                price_diff_ratio = abs(market_data.current_price - signal.price) / signal.price
                if price_diff_ratio > 0.03:  # 价格偏差超过3%
                    errors.append(
                        f"价格偏差过大: 信号价{signal.price:.2f}, "
                        f"实时价{market_data.current_price:.2f}"
                    )
            else:
                errors.append("无法获取实时行情")
        except Exception as e:
            logger.error(f"验证买入信号异常: {e}")
            errors.append(f"验证异常: {str(e)}")

        return len(errors) == 0, errors

    def _print_buy_signals_summary(self, signals: List[BuySignal]) -> None:
        """打印买入信号摘要"""
        if not signals:
            return

        print("\n" + "=" * 60)
        print("买入信号摘要")
        print("=" * 60)

        total_amount = sum(s.amount for s in signals)
        print(f"信号数量: {len(signals)}")
        print(f"总买入金额: {total_amount:.2f}元")
        print()

        for i, signal in enumerate(signals, 1):
            print(f"{i}. {signal.stock_name} ({signal.stock_code})")
            print(f"   买入: {signal.quantity}股 @ {signal.price:.2f}元")
            print(f"   金额: {signal.amount:.2f}元")
            print(f"   优先级: {signal.priority.value} | 评分: {signal.score:.1f} | 置信度: {signal.confidence:.1%}")
            print(f"   理由: {', '.join(signal.reasons[:2])}")
            print()

        print("=" * 60)

    def print_buy_signal_detail(self, signal: BuySignal) -> None:
        """打印买入信号详情"""
        print("\n" + "=" * 60)
        print(f"股票: {signal.stock_name} ({signal.stock_code})")
        print(f"动作: BUY (优先级: {signal.priority.value})")
        print(f"数量: {signal.quantity}股 @ {signal.price:.2f}元")
        print(f"金额: {signal.amount:.2f}元")
        print(f"评分: {signal.score:.1f}")
        print(f"置信度: {signal.confidence:.1%}")
        print(f"\n买入理由:")
        for i, reason in enumerate(signal.reasons, 1):
            print(f"  {i}. {reason}")
        print("=" * 60)


class BuyTiming:
    """
    买入时机判断

    判断当前是否适合买入
    """

    @staticmethod
    def is_good_time_to_buy() -> tuple[bool, str]:
        """
        判断当前是否适合买入

        Returns:
            (是否适合, 原因)
        """
        now = datetime.now()
        hour = now.hour
        minute = now.minute

        # 避开开盘集合竞价 (9:15-9:30)
        if hour == 9 and minute < 30:
            return False, "开盘集合竞价时段，避免买入"

        # 避开收盘集合竞价 (14:57-15:00)
        if hour == 14 and minute >= 57:
            return False, "收盘集合竞价时段，避免买入"

        # 推荐买入时段
        # 早盘: 9:35-10:00 (开盘稳定后)
        if hour == 9 and 35 <= minute <= 59:
            return True, "早盘买入窗口（开盘稳定后）"

        if hour == 10 and minute == 0:
            return True, "早盘买入窗口（开盘稳定后）"

        # 尾盘: 14:00-14:30 (尾盘低吸)
        if hour == 14 and 0 <= minute <= 30:
            return True, "尾盘买入窗口（低吸机会）"

        # 其他时段也可以买入，但优先级较低
        return True, "交易时段"

    @staticmethod
    def get_next_buy_window() -> Optional[datetime]:
        """
        获取下一个买入窗口时间

        Returns:
            下一个买入窗口的开始时间
        """
        now = datetime.now()
        hour = now.hour
        minute = now.minute

        # 当前在早盘买入窗口之前
        if hour < 9 or (hour == 9 and minute < 35):
            return now.replace(hour=9, minute=35, second=0, microsecond=0)

        # 当前在早盘买入窗口之后、尾盘买入窗口之前
        if hour < 14:
            return now.replace(hour=14, minute=0, second=0, microsecond=0)

        # 当前在尾盘买入窗口之后
        # 返回明天的早盘窗口
        from datetime import timedelta
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=9, minute=35, second=0, microsecond=0)


# ============================================================================
# 使用示例和测试
# ============================================================================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建买入策略引擎
    buy_strategy = BuyStrategy(total_capital=100000)

    # 模拟当前持仓
    current_positions = [
        Position("600483", "福能股份", 100, 24.50, 10, 23.30),
    ]

    # 模拟可用资金
    available_cash = 50000

    print("\n=== 测试生成买入信号 ===")

    # 生成买入信号
    buy_signals = buy_strategy.generate_buy_signals(
        available_cash=available_cash,
        current_positions=current_positions,
        max_buy_count=3
    )

    # 验证信号
    print("\n=== 验证买入信号 ===")
    for signal in buy_signals:
        valid, errors = buy_strategy.validate_buy_signal(signal)
        print(f"\n{signal.stock_code}: {'有效' if valid else '无效'}")
        if errors:
            for error in errors:
                print(f"  - {error}")

    # 测试买入时机
    print("\n=== 测试买入时机 ===")
    is_good, reason = BuyTiming.is_good_time_to_buy()
    print(f"当前时机: {'适合' if is_good else '不适合'}")
    print(f"原因: {reason}")

    if not is_good:
        next_window = BuyTiming.get_next_buy_window()
        if next_window:
            print(f"下一个买入窗口: {next_window.strftime('%Y-%m-%d %H:%M')}")
