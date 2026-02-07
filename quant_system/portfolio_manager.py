"""
投资组合管理模块

负责仓位管理和资金分配：
1. 计算可用资金
2. 仓位分配算法（Kelly公式、等权重、风险平价）
3. 行业分散度检查
4. 持仓数量限制
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import math

try:
    from .decision_engine import Position
    from .stock_selector import CandidateStock
    from .config_quant import BUY_STRATEGY_CONFIG
except ImportError:
    from decision_engine import Position
    from stock_selector import CandidateStock
    from config_quant import BUY_STRATEGY_CONFIG

logger = logging.getLogger(__name__)


class PositionMethod(Enum):
    """仓位分配方法"""
    EQUAL_WEIGHT = "等权重"          # 每只股票相同仓位
    KELLY = "Kelly公式"              # Kelly公式计算最优仓位
    SCORE_WEIGHTED = "评分加权"       # 根据评分加权分配
    RISK_PARITY = "风险平价"          # 风险平价分配


@dataclass
class BuyRecommendation:
    """买入建议"""
    stock_code: str                  # 股票代码
    stock_name: str                  # 股票名称
    quantity: int                    # 建议买入数量
    price: float                     # 建议买入价格
    amount: float                    # 买入金额
    position_ratio: float            # 仓位占比
    score: float                     # 综合评分
    reasons: List[str]               # 买入理由

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "quantity": self.quantity,
            "price": self.price,
            "amount": self.amount,
            "position_ratio": self.position_ratio,
            "score": self.score,
            "reasons": self.reasons
        }


class PortfolioManager:
    """
    投资组合管理器

    负责仓位分配、资金管理和风险控制
    """

    def __init__(self, total_capital: float = 100000.0):
        """
        初始化组合管理器

        Args:
            total_capital: 总资金（元）
        """
        self.total_capital = total_capital
        self.config = BUY_STRATEGY_CONFIG

        # 配置参数
        self.max_positions = self.config.get("max_positions", 10)
        self.max_single_position = self.config.get("max_single_position", 0.2)
        self.max_industry_concentration = self.config.get("max_industry_concentration", 0.4)
        self.min_position_value = self.config.get("min_position_value", 5000)
        self.cash_reserve_ratio = self.config.get("cash_reserve_ratio", 0.1)

        logger.info("组合管理器初始化完成")
        logger.info(f"总资金: {total_capital:.2f}元")
        logger.info(f"最大持仓数: {self.max_positions}")
        logger.info(f"单股最大仓位: {self.max_single_position:.1%}")

    def calculate_available_cash(
        self,
        current_positions: List[Position],
        total_capital: Optional[float] = None
    ) -> float:
        """
        计算可用资金

        Args:
            current_positions: 当前持仓列表
            total_capital: 总资金（如果为None则使用初始化时的值）

        Returns:
            可用资金（元）
        """
        if total_capital is None:
            total_capital = self.total_capital

        # 计算当前持仓市值
        position_value = sum(p.calculate_position_value() for p in current_positions)

        # 可用资金 = 总资金 - 持仓市值
        available_cash = total_capital - position_value

        # 保留现金缓冲
        cash_reserve = total_capital * self.cash_reserve_ratio
        usable_cash = max(0, available_cash - cash_reserve)

        logger.info(f"总资金: {total_capital:.2f}元")
        logger.info(f"持仓市值: {position_value:.2f}元")
        logger.info(f"可用资金: {available_cash:.2f}元")
        logger.info(f"现金缓冲: {cash_reserve:.2f}元")
        logger.info(f"可使用资金: {usable_cash:.2f}元")

        return usable_cash

    def allocate_positions(
        self,
        candidates: List[CandidateStock],
        available_cash: float,
        current_positions: List[Position],
        method: PositionMethod = PositionMethod.SCORE_WEIGHTED
    ) -> List[BuyRecommendation]:
        """
        分配买入仓位

        Args:
            candidates: 候选股票列表
            available_cash: 可用资金
            current_positions: 当前持仓列表
            method: 仓位分配方法

        Returns:
            买入建议列表
        """
        logger.info(f"开始仓位分配，可用资金: {available_cash:.2f}元")
        logger.info(f"候选股票数: {len(candidates)}, 分配方法: {method.value}")

        # 1. 检查持仓数量限制
        available_slots = self.max_positions - len(current_positions)
        if available_slots <= 0:
            logger.warning("已达最大持仓数量，无法买入新股票")
            return []

        logger.info(f"可用仓位槽: {available_slots}")

        # 2. 过滤已持有的股票
        held_codes = {p.code for p in current_positions}
        candidates = [c for c in candidates if c.code not in held_codes]

        if not candidates:
            logger.warning("没有可买入的新股票")
            return []

        # 3. 限制买入数量
        buy_count = min(len(candidates), available_slots)
        candidates = candidates[:buy_count]

        logger.info(f"计划买入 {buy_count} 只股票")

        # 4. 根据不同方法分配仓位
        if method == PositionMethod.EQUAL_WEIGHT:
            recommendations = self._allocate_equal_weight(
                candidates, available_cash, current_positions
            )
        elif method == PositionMethod.KELLY:
            recommendations = self._allocate_kelly(
                candidates, available_cash, current_positions
            )
        elif method == PositionMethod.SCORE_WEIGHTED:
            recommendations = self._allocate_score_weighted(
                candidates, available_cash, current_positions
            )
        else:
            recommendations = self._allocate_equal_weight(
                candidates, available_cash, current_positions
            )

        # 5. 过滤掉金额过小的建议
        recommendations = [
            r for r in recommendations
            if r.amount >= self.min_position_value
        ]

        logger.info(f"生成 {len(recommendations)} 个买入建议")

        return recommendations

    def _allocate_equal_weight(
        self,
        candidates: List[CandidateStock],
        available_cash: float,
        current_positions: List[Position]
    ) -> List[BuyRecommendation]:
        """等权重分配"""
        recommendations = []

        # 平均分配资金
        per_stock_cash = available_cash / len(candidates)

        for candidate in candidates:
            quantity = self._calculate_buy_quantity(
                candidate.current_price,
                per_stock_cash
            )

            if quantity > 0:
                amount = quantity * candidate.current_price
                position_ratio = amount / self.total_capital

                recommendations.append(BuyRecommendation(
                    stock_code=candidate.code,
                    stock_name=candidate.name,
                    quantity=quantity,
                    price=candidate.current_price,
                    amount=amount,
                    position_ratio=position_ratio,
                    score=candidate.score,
                    reasons=candidate.reasons
                ))

        return recommendations

    def _allocate_score_weighted(
        self,
        candidates: List[CandidateStock],
        available_cash: float,
        current_positions: List[Position]
    ) -> List[BuyRecommendation]:
        """评分加权分配"""
        recommendations = []

        # 计算总评分
        total_score = sum(c.score for c in candidates)

        if total_score <= 0:
            # 如果没有评分，回退到等权重
            return self._allocate_equal_weight(candidates, available_cash, current_positions)

        for candidate in candidates:
            # 根据评分分配资金
            weight = candidate.score / total_score
            allocated_cash = available_cash * weight

            # 限制单股最大仓位
            max_cash_for_stock = self.total_capital * self.max_single_position
            allocated_cash = min(allocated_cash, max_cash_for_stock)

            quantity = self._calculate_buy_quantity(
                candidate.current_price,
                allocated_cash
            )

            if quantity > 0:
                amount = quantity * candidate.current_price
                position_ratio = amount / self.total_capital

                recommendations.append(BuyRecommendation(
                    stock_code=candidate.code,
                    stock_name=candidate.name,
                    quantity=quantity,
                    price=candidate.current_price,
                    amount=amount,
                    position_ratio=position_ratio,
                    score=candidate.score,
                    reasons=candidate.reasons
                ))

        return recommendations

    def _allocate_kelly(
        self,
        candidates: List[CandidateStock],
        available_cash: float,
        current_positions: List[Position]
    ) -> List[BuyRecommendation]:
        """Kelly公式分配"""
        recommendations = []

        for candidate in candidates:
            # 根据评分估算胜率和赔率
            # 这是简化处理，实际应该基于历史回测数据
            win_prob = min(0.9, candidate.score / 100)
            win_return = 0.15  # 假设盈利15%
            loss_return = -0.08  # 假设亏损8%

            # 计算Kelly仓位
            kelly_ratio = self._calculate_kelly_position(
                win_prob, win_return, loss_return
            )

            # Kelly/4 更保守
            conservative_ratio = kelly_ratio / 4

            # 分配资金
            allocated_cash = self.total_capital * conservative_ratio

            # 限制单股最大仓位
            max_cash_for_stock = self.total_capital * self.max_single_position
            allocated_cash = min(allocated_cash, max_cash_for_stock)

            # 确保不超过可用资金
            if allocated_cash > available_cash:
                allocated_cash = available_cash

            quantity = self._calculate_buy_quantity(
                candidate.current_price,
                allocated_cash
            )

            if quantity > 0:
                amount = quantity * candidate.current_price
                position_ratio = amount / self.total_capital

                recommendations.append(BuyRecommendation(
                    stock_code=candidate.code,
                    stock_name=candidate.name,
                    quantity=quantity,
                    price=candidate.current_price,
                    amount=amount,
                    position_ratio=position_ratio,
                    score=candidate.score,
                    reasons=candidate.reasons + [
                        f"Kelly仓位: {kelly_ratio:.2%} (保守使用{conservative_ratio:.2%})"
                    ]
                ))

                # 扣除已分配的资金
                available_cash -= amount

        return recommendations

    def _calculate_kelly_position(
        self,
        win_prob: float,
        win_return: float,
        loss_return: float
    ) -> float:
        """
        Kelly公式计算最优仓位

        f* = (p*b - q) / b
        其中：
        p = 获胜概率
        q = 失败概率 (1-p)
        b = 赔率（获胜时的回报率）

        Args:
            win_prob: 获胜概率 (0-1)
            win_return: 盈利时的回报率
            loss_return: 亏损时的回报率（负数）

        Returns:
            最优仓位比例 (0-1)
        """
        if win_prob <= 0 or win_prob >= 1:
            return 0.0

        if win_return <= 0 or loss_return >= 0:
            return 0.0

        q = 1 - win_prob
        kelly_ratio = (win_prob * win_return - q * abs(loss_return)) / win_return

        # 限制在 0-0.25 之间
        return max(0, min(0.25, kelly_ratio))

    def _calculate_buy_quantity(
        self,
        price: float,
        allocated_cash: float
    ) -> int:
        """
        计算买入数量

        Args:
            price: 股票价格
            allocated_cash: 分配的资金

        Returns:
            买入数量（手，100股的倍数）
        """
        if price <= 0 or allocated_cash <= 0:
            return 0

        # 计算可买手数（向下取整）
        lots = int(allocated_cash / (price * 100))

        return lots * 100

    def check_position_limits(
        self,
        recommendations: List[BuyRecommendation],
        current_positions: List[Position]
    ) -> Tuple[List[BuyRecommendation], List[str]]:
        """
        检查仓位限制

        Args:
            recommendations: 买入建议列表
            current_positions: 当前持仓列表

        Returns:
            (通过检查的建议, 警告信息列表)
        """
        warnings = []
        passed_recommendations = []

        # 检查持仓数量
        total_positions = len(current_positions) + len(recommendations)
        if total_positions > self.max_positions:
            warnings.append(
                f"超过最大持仓数量限制: {total_positions}/{self.max_positions}"
            )
            # 只保留前N个建议
            recommendations = recommendations[:self.max_positions - len(current_positions)]

        # 检查单股仓位
        for rec in recommendations:
            if rec.position_ratio > self.max_single_position:
                warnings.append(
                    f"{rec.stock_code} 仓位过大: {rec.position_ratio:.2%} > "
                    f"{self.max_single_position:.2%}"
                )
                continue

            # 检查最小买入金额
            if rec.amount < self.min_position_value:
                warnings.append(
                    f"{rec.stock_code} 买入金额过小: {rec.amount:.2f}元 < "
                    f"{self.min_position_value}元"
                )
                continue

            passed_recommendations.append(rec)

        return passed_recommendations, warnings

    def check_diversification(
        self,
        recommendations: List[BuyRecommendation],
        current_positions: List[Position]
    ) -> Dict[str, float]:
        """
        检查投资组合分散度

        Args:
            recommendations: 买入建议列表
            current_positions: 当前持仓列表

        Returns:
            行业集中度字典 {行业: 仓位占比}
        """
        # 注意：这里简化处理，实际应该获取真实的行业信息
        # 可以通过调用行业分类API或维护行业映射表

        # 计算总市值
        total_value = sum(p.calculate_position_value() for p in current_positions)
        total_value += sum(r.amount for r in recommendations)

        if total_value <= 0:
            return {}

        # 计算行业占比（这里用股票代码前3位作为简化的"行业"标识）
        industry_weights = {}

        # 当前持仓
        for position in current_positions:
            industry = position.code[:3]  # 简化处理
            value = position.calculate_position_value()
            weight = value / total_value

            if industry in industry_weights:
                industry_weights[industry] += weight
            else:
                industry_weights[industry] = weight

        # 新增持仓
        for rec in recommendations:
            industry = rec.stock_code[:3]  # 简化处理
            weight = rec.amount / total_value

            if industry in industry_weights:
                industry_weights[industry] += weight
            else:
                industry_weights[industry] = weight

        # 检查是否有行业过度集中
        for industry, weight in industry_weights.items():
            if weight > self.max_industry_concentration:
                logger.warning(
                    f"行业{industry}集中度过高: {weight:.2%} > "
                    f"{self.max_industry_concentration:.2%}"
                )

        return industry_weights

    def optimize_portfolio(
        self,
        recommendations: List[BuyRecommendation],
        current_positions: List[Position]
    ) -> List[BuyRecommendation]:
        """
        优化投资组合

        Args:
            recommendations: 买入建议列表
            current_positions: 当前持仓列表

        Returns:
            优化后的买入建议列表
        """
        # 1. 检查仓位限制
        recommendations, warnings = self.check_position_limits(
            recommendations, current_positions
        )

        for warning in warnings:
            logger.warning(warning)

        # 2. 检查分散度
        industry_weights = self.check_diversification(
            recommendations, current_positions
        )

        logger.info("行业分布:")
        for industry, weight in sorted(
            industry_weights.items(), key=lambda x: x[1], reverse=True
        ):
            logger.info(f"  {industry}: {weight:.2%}")

        return recommendations


# ============================================================================
# 使用示例和测试
# ============================================================================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建组合管理器
    manager = PortfolioManager(total_capital=100000)

    # 模拟当前持仓
    current_positions = [
        Position("600483", "福能股份", 100, 24.50, 10, 23.30),
        Position("603993", "洛阳钼业", 200, 5.50, 5, 5.80),
    ]

    # 计算可用资金
    available_cash = manager.calculate_available_cash(current_positions)

    # 模拟候选股票
    candidates = [
        CandidateStock(
            code="600519",
            name="贵州茅台",
            score=85.0,
            model_score=88.0,
            current_price=1800.0,
            reasons=["高端白酒龙头", "业绩优秀"]
        ),
        CandidateStock(
            code="600036",
            name="招商银行",
            score=80.0,
            model_score=82.0,
            current_price=38.50,
            reasons=["银行业龙头", "估值合理"]
        ),
    ]

    print("\n=== 测试仓位分配 ===")

    # 测试评分加权分配
    recommendations = manager.allocate_positions(
        candidates,
        available_cash,
        current_positions,
        method=PositionMethod.SCORE_WEIGHTED
    )

    print(f"\n生成 {len(recommendations)} 个买入建议:")
    for rec in recommendations:
        print(f"\n{rec.stock_name} ({rec.stock_code})")
        print(f"  买入数量: {rec.quantity}股")
        print(f"  买入价格: {rec.price:.2f}元")
        print(f"  买入金额: {rec.amount:.2f}元")
        print(f"  仓位占比: {rec.position_ratio:.2%}")
        print(f"  综合评分: {rec.score:.1f}")

    # 测试优化
    print("\n=== 测试组合优化 ===")
    optimized = manager.optimize_portfolio(recommendations, current_positions)
    print(f"优化后保留 {len(optimized)} 个建议")
