"""
智能决策引擎模块

综合分析模型评分、实时行情、持仓信息，生成交易决策信号。
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

try:
    from .market_data_client import StockData
    from .model_client import ModelScore
    from .config_quant import (
        SCORE_THRESHOLDS,
        STOP_LOSS,
        STOP_PROFIT,
        EMERGENCY_STOP_LOSS,
        HOLDING_DAYS_WARNING,
        HOLDING_DAYS_LONG,
        DECISION_WEIGHTS,
        BLACKLIST_STOCKS,
        WHITELIST_STOCKS,
        ST_STOCK_PREFIX
    )
except ImportError:
    from market_data_client import StockData
    from model_client import ModelScore
    from config_quant import (
        SCORE_THRESHOLDS,
        STOP_LOSS,
        STOP_PROFIT,
        EMERGENCY_STOP_LOSS,
        HOLDING_DAYS_WARNING,
        HOLDING_DAYS_LONG,
        DECISION_WEIGHTS,
        BLACKLIST_STOCKS,
        WHITELIST_STOCKS,
        ST_STOCK_PREFIX
    )

# 配置日志
logger = logging.getLogger(__name__)


class TradeAction(Enum):
    """交易动作"""
    STRONG_SELL = "strong_sell"  # 强烈卖出
    SELL = "sell"                # 建议卖出
    HOLD = "hold"                # 持有观望
    BUY = "buy"                  # 可考虑持有/买入
    NO_ACTION = "no_action"      # 无操作


class Priority(Enum):
    """优先级"""
    CRITICAL = 1   # 紧急（立即执行）
    HIGH = 2       # 高优先级
    MEDIUM = 3     # 中等优先级
    LOW = 4        # 低优先级


@dataclass
class Position:
    """持仓信息"""
    code: str                    # 股票代码
    name: str                    # 股票名称
    quantity: int                # 持仓数量
    cost_price: float            # 成本价
    holding_days: int = 0        # 持仓天数
    current_price: float = 0.0   # 当前价（从市场数据更新）

    def calculate_profit_loss(self) -> float:
        """计算盈亏金额"""
        if self.current_price > 0:
            return (self.current_price - self.cost_price) * self.quantity
        return 0.0

    def calculate_profit_loss_ratio(self) -> float:
        """计算盈亏比例"""
        if self.cost_price > 0 and self.current_price > 0:
            return (self.current_price - self.cost_price) / self.cost_price
        return 0.0

    def calculate_position_value(self) -> float:
        """计算持仓市值"""
        if self.current_price > 0:
            return self.current_price * self.quantity
        return self.cost_price * self.quantity

    def is_st_stock(self) -> bool:
        """是否为ST股票"""
        return any(self.name.startswith(prefix) for prefix in ST_STOCK_PREFIX)


@dataclass
class TradeSignal:
    """交易信号"""
    stock_code: str                    # 股票代码
    stock_name: str                    # 股票名称
    action: TradeAction                # 交易动作
    priority: Priority                 # 优先级
    quantity: int                      # 建议交易数量
    price: Optional[float] = None      # 建议价格
    reasons: List[str] = field(default_factory=list)  # 决策原因
    score: Optional[float] = None      # 综合评分
    confidence: float = 0.0            # 决策置信度
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "action": self.action.value,
            "priority": self.priority.value,
            "quantity": self.quantity,
            "price": self.price,
            "reasons": self.reasons,
            "score": self.score,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat()
        }

    def is_sell_signal(self) -> bool:
        """是否为卖出信号"""
        return self.action in [TradeAction.STRONG_SELL, TradeAction.SELL]

    def is_high_priority(self) -> bool:
        """是否为高优先级"""
        return self.priority in [Priority.CRITICAL, Priority.HIGH]


class DecisionEngine:
    """
    智能决策引擎

    综合分析多维度数据，生成智能交易决策：
    1. 模型评分分析
    2. 实时行情分析
    3. 持仓盈亏分析
    4. 持仓时间分析
    5. 风险评估
    """

    def __init__(self):
        """初始化决策引擎"""
        self.decision_weights = DECISION_WEIGHTS
        logger.info("决策引擎初始化完成")

    def analyze_position(
        self,
        position: Position,
        market_data: Optional[StockData] = None,
        model_score: Optional[ModelScore] = None
    ) -> TradeSignal:
        """
        分析单个持仓，生成交易信号

        Args:
            position: 持仓信息
            market_data: 市场实时数据
            model_score: 模型评分

        Returns:
            TradeSignal: 交易信号
        """
        reasons = []
        signal_scores = {}

        # 更新持仓当前价
        if market_data:
            position.current_price = market_data.current_price

        # 1. 黑名单检查
        if position.code in BLACKLIST_STOCKS:
            return TradeSignal(
                stock_code=position.code,
                stock_name=position.name,
                action=TradeAction.STRONG_SELL,
                priority=Priority.CRITICAL,
                quantity=position.quantity,
                price=position.current_price if market_data else None,
                reasons=["股票在黑名单中，强制卖出"],
                confidence=1.0
            )

        # 2. 模型评分分析
        if model_score:
            score_signal = self._analyze_model_score(model_score, reasons)
            signal_scores['model'] = score_signal

        # 3. 实时行情分析
        if market_data:
            market_signal = self._analyze_market_data(market_data, position, reasons)
            signal_scores['market'] = market_signal

        # 4. 盈亏分析
        profit_loss_signal = self._analyze_profit_loss(position, reasons)
        signal_scores['profit_loss'] = profit_loss_signal

        # 5. 持仓时间分析
        holding_signal = self._analyze_holding_time(position, reasons)
        signal_scores['holding'] = holding_signal

        # 6. 综合决策
        final_action, priority, confidence = self._make_final_decision(
            signal_scores, position, model_score
        )

        # 生成交易信号
        signal = TradeSignal(
            stock_code=position.code,
            stock_name=position.name,
            action=final_action,
            priority=priority,
            quantity=position.quantity,
            price=position.current_price if market_data else None,
            reasons=reasons,
            score=model_score.score if model_score else None,
            confidence=confidence
        )

        logger.info(
            f"持仓分析完成: {position.code} {position.name} -> "
            f"{final_action.value} (优先级: {priority.value}, 置信度: {confidence:.2%})"
        )

        return signal

    def analyze_positions_batch(
        self,
        positions: List[Position],
        market_data_dict: Dict[str, StockData],
        model_scores_dict: Dict[str, ModelScore]
    ) -> List[TradeSignal]:
        """
        批量分析持仓

        Args:
            positions: 持仓列表
            market_data_dict: {股票代码: 市场数据} 字典
            model_scores_dict: {股票代码: 模型评分} 字典

        Returns:
            交易信号列表
        """
        signals = []

        for position in positions:
            market_data = market_data_dict.get(position.code)
            model_score = model_scores_dict.get(position.code)

            signal = self.analyze_position(position, market_data, model_score)
            signals.append(signal)

        # 按优先级排序
        signals.sort(key=lambda s: (s.priority.value, -s.confidence))

        logger.info(f"批量分析完成: {len(positions)} 个持仓，生成 {len(signals)} 个信号")
        return signals

    def _analyze_model_score(self, model_score: ModelScore, reasons: List[str]) -> float:
        """
        分析模型评分

        Returns:
            信号强度 (-1.0 到 1.0): 负值=卖出，正值=买入/持有
        """
        score = model_score.score
        recommendation = model_score.recommendation
        confidence = model_score.confidence

        # 强烈卖出信号
        if score < SCORE_THRESHOLDS['strong_sell']:
            reasons.append(f"模型评分极低 ({score:.1f}/100)，强烈建议卖出")
            # 确保最低信号强度为-0.5，即使置信度很低
            return max(-1.0 * confidence, -0.5)

        # 卖出信号
        elif score < SCORE_THRESHOLDS['sell']:
            reasons.append(f"模型评分较低 ({score:.1f}/100)，建议卖出")
            # 确保最低信号强度为-0.4
            return max(-0.7 * confidence, -0.4)

        # 持有观望
        elif score < SCORE_THRESHOLDS['hold']:
            reasons.append(f"模型评分一般 ({score:.1f}/100)，建议持有观望")
            return -0.3 * confidence

        # 可持有
        elif score < SCORE_THRESHOLDS['buy']:
            reasons.append(f"模型评分良好 ({score:.1f}/100)，可继续持有")
            return 0.3 * confidence

        # 强烈持有
        else:
            reasons.append(f"模型评分优秀 ({score:.1f}/100)，继续持有")
            return 0.8 * confidence

    def _analyze_market_data(
        self,
        market_data: StockData,
        position: Position,
        reasons: List[str]
    ) -> float:
        """
        分析实时行情

        Returns:
            信号强度 (-1.0 到 1.0)
        """
        signal = 0.0

        # 跌停检查
        if market_data.is_limit_down():
            reasons.append(f"股票跌停 ({market_data.current_price})")
            signal -= 0.8

        # 涨停检查
        elif market_data.is_limit_up():
            reasons.append(f"股票涨停 ({market_data.current_price})，可继续持有")
            signal += 0.5

        # 价格位置分析
        else:
            price_position = market_data.get_price_position()

            if price_position < 0.2:
                reasons.append(f"当前价接近日内最低点 ({price_position:.1%})")
                signal -= 0.3
            elif price_position > 0.8:
                reasons.append(f"当前价接近日内最高点 ({price_position:.1%})")
                signal += 0.2

        # 涨跌幅分析
        if market_data.change_percent < -5:
            reasons.append(f"大幅下跌 ({market_data.change_percent:+.2f}%)")
            signal -= 0.5
        elif market_data.change_percent > 5:
            reasons.append(f"大幅上涨 ({market_data.change_percent:+.2f}%)")
            signal += 0.3

        return max(-1.0, min(1.0, signal))

    def _analyze_profit_loss(self, position: Position, reasons: List[str]) -> float:
        """
        分析盈亏状态

        Returns:
            信号强度 (-1.0 到 1.0)
        """
        if position.current_price <= 0:
            return 0.0

        profit_loss_ratio = position.calculate_profit_loss_ratio()
        profit_loss_amount = position.calculate_profit_loss()

        # 紧急止损
        if profit_loss_ratio <= EMERGENCY_STOP_LOSS:
            reasons.append(
                f"触发紧急止损线 ({profit_loss_ratio:.2%}，"
                f"亏损{abs(profit_loss_amount):.2f}元)"
            )
            return -1.0

        # 正常止损
        elif profit_loss_ratio <= STOP_LOSS:
            reasons.append(
                f"触发止损线 ({profit_loss_ratio:.2%}，"
                f"亏损{abs(profit_loss_amount):.2f}元)"
            )
            return -0.8

        # 止盈
        elif profit_loss_ratio >= STOP_PROFIT:
            reasons.append(
                f"达到止盈目标 ({profit_loss_ratio:.2%}，"
                f"盈利{profit_loss_amount:.2f}元)"
            )
            return -0.6  # 止盈也是卖出信号

        # 小幅亏损
        elif -0.05 <= profit_loss_ratio < 0:
            reasons.append(f"小幅亏损 ({profit_loss_ratio:.2%})")
            return -0.3

        # 盈利状态
        elif profit_loss_ratio > 0:
            reasons.append(f"当前盈利 ({profit_loss_ratio:.2%})")
            return 0.2

        return 0.0

    def _analyze_holding_time(self, position: Position, reasons: List[str]) -> float:
        """
        分析持仓时间

        Returns:
            信号强度 (-1.0 到 1.0)
        """
        holding_days = position.holding_days
        profit_loss_ratio = position.calculate_profit_loss_ratio()

        # 长期持仓且亏损
        if holding_days >= HOLDING_DAYS_LONG and profit_loss_ratio < 0:
            reasons.append(f"长期持仓({holding_days}天)且亏损，建议止损")
            return -0.6

        # 持仓警告期且亏损
        elif holding_days >= HOLDING_DAYS_WARNING and profit_loss_ratio < 0:
            reasons.append(f"持仓{holding_days}天且亏损，需关注")
            return -0.4

        # 短期持仓
        elif holding_days < 5:
            reasons.append(f"短期持仓({holding_days}天)")
            return 0.1

        return 0.0

    def _make_final_decision(
        self,
        signal_scores: Dict[str, float],
        position: Position,
        model_score: Optional[ModelScore]
    ) -> Tuple[TradeAction, Priority, float]:
        """
        综合所有信号做出最终决策

        Args:
            signal_scores: 各维度信号得分
            position: 持仓信息
            model_score: 模型评分

        Returns:
            (交易动作, 优先级, 置信度)
        """
        # 计算加权综合得分
        weighted_score = 0.0
        total_weight = 0.0

        for dimension, weight_key in [
            ('model', 'model_score'),
            ('market', 'price_trend'),
            ('profit_loss', 'profit_loss'),
            ('holding', 'holding_time')
        ]:
            if dimension in signal_scores:
                weight = self.decision_weights.get(weight_key, 0.25)
                weighted_score += signal_scores[dimension] * weight
                total_weight += weight

        # 归一化
        if total_weight > 0:
            final_score = weighted_score / total_weight
        else:
            final_score = 0.0

        # 根据综合得分确定动作和优先级
        # 紧急卖出 (得分 < -0.7)
        if final_score < -0.7:
            action = TradeAction.STRONG_SELL
            priority = Priority.CRITICAL
            confidence = min(0.95, abs(final_score))

        # 强烈卖出 (得分 -0.7 到 -0.5)
        elif final_score < -0.5:
            action = TradeAction.SELL
            priority = Priority.HIGH
            confidence = min(0.85, abs(final_score) * 0.9)

        # 建议卖出 (得分 -0.5 到 -0.15)
        elif final_score < -0.15:
            action = TradeAction.SELL
            priority = Priority.MEDIUM
            confidence = abs(final_score) * 0.8

        # 持有观望 (得分 -0.15 到 0.15)
        elif final_score < 0.15:
            action = TradeAction.HOLD
            priority = Priority.LOW
            confidence = 0.5

        # 继续持有 (得分 >= 0.2)
        else:
            action = TradeAction.BUY
            priority = Priority.LOW
            confidence = min(0.8, final_score)

        return action, priority, confidence

    def filter_sell_signals(self, signals: List[TradeSignal]) -> List[TradeSignal]:
        """
        过滤出卖出信号

        Args:
            signals: 交易信号列表

        Returns:
            卖出信号列表（按优先级排序）
        """
        sell_signals = [s for s in signals if s.is_sell_signal()]
        sell_signals.sort(key=lambda s: (s.priority.value, -s.confidence))

        logger.info(f"过滤出 {len(sell_signals)} 个卖出信号")
        return sell_signals


# ============================================================================
# 使用示例和测试
# ============================================================================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建决策引擎
    engine = DecisionEngine()

    # 模拟数据
    print("\n=== 测试持仓分析 ===")

    # 创建测试持仓
    position = Position(
        code="600483",
        name="福能股份",
        quantity=100,
        cost_price=24.50,
        holding_days=10,
        current_price=23.30
    )

    # 模拟市场数据
    market_data = StockData(
        code="600483",
        name="福能股份",
        current_price=23.30,
        change_amount=-1.20,
        change_percent=-4.90,
        volume=50000,
        turnover=11650.0,
        highest=24.00,
        lowest=23.10,
        open_price=24.00,
        previous_close=24.50,
        timestamp=datetime.now()
    )

    # 模拟模型评分
    model_score = ModelScore(
        stock_code="600483",
        score=28.5,
        recommendation="strong_sell",
        confidence=0.85,
        factors={"technical": 25.0, "fundamental": 30.0, "sentiment": 30.0},
        timestamp=datetime.now()
    )

    # 执行分析
    signal = engine.analyze_position(position, market_data, model_score)

    # 输出结果
    print(f"\n股票: {signal.stock_name} ({signal.stock_code})")
    print(f"交易动作: {signal.action.value}")
    print(f"优先级: {signal.priority.value}")
    print(f"建议数量: {signal.quantity}")
    print(f"建议价格: {signal.price}")
    print(f"置信度: {signal.confidence:.2%}")
    print(f"决策原因:")
    for i, reason in enumerate(signal.reasons, 1):
        print(f"  {i}. {reason}")

    print(f"\n持仓盈亏: {position.calculate_profit_loss():.2f}元 ({position.calculate_profit_loss_ratio():.2%})")
    print(f"是否卖出信号: {signal.is_sell_signal()}")
    print(f"是否高优先级: {signal.is_high_priority()}")
