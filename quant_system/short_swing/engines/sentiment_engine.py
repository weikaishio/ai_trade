"""
情绪周期判断引擎

基于市场数据判断当前处于哪个情绪周期阶段。
"""

import logging
from typing import List, Optional
from datetime import datetime

from ..data.models import StockQuote, SentimentState
from ..data.data_fetcher import get_fetcher
from ..config_short_swing import SENTIMENT_THRESHOLDS, SENTIMENT_CONTINUITY

logger = logging.getLogger(__name__)


class SentimentEngine:
    """情绪周期判断引擎"""

    def __init__(self):
        """初始化情绪引擎"""
        self.fetcher = get_fetcher()
        self.history: List[SentimentState] = []  # 历史情绪状态

    def analyze_sentiment(self) -> SentimentState:
        """
        分析当前市场情绪状态

        Returns:
            情绪状态对象
        """
        logger.info("Starting sentiment analysis...")

        # 获取市场快照
        market_snapshot = self.fetcher.get_market_snapshot()
        if not market_snapshot:
            logger.error("Failed to fetch market snapshot")
            return self._create_default_state()

        # 获取涨停股票
        limit_up_stocks = self.fetcher.get_limit_up_stocks()

        # 计算市场指标
        metrics = self._calculate_market_metrics(market_snapshot, limit_up_stocks)

        # 判断情绪状态
        state = self._determine_sentiment_state(metrics)

        # 添加到历史
        self.history.append(state)
        if len(self.history) > SENTIMENT_CONTINUITY["lookback_days"]:
            self.history.pop(0)

        logger.info(f"Sentiment state: {state.state} "
                   f"(limit_up={state.limit_up_count}, "
                   f"avg_change={state.avg_change_percent:.2f}%, "
                   f"rising_ratio={state.rising_ratio:.2%})")

        return state

    def _calculate_market_metrics(
        self,
        market_snapshot: List[StockQuote],
        limit_up_stocks: List[StockQuote]
    ) -> dict:
        """
        计算市场指标

        Args:
            market_snapshot: 市场快照
            limit_up_stocks: 涨停股票列表

        Returns:
            市场指标字典
        """
        total_count = len(market_snapshot)
        if total_count == 0:
            return {
                "limit_up_count": 0,
                "avg_change_percent": 0.0,
                "rising_ratio": 0.0,
                "falling_ratio": 0.0,
                "volume_ratio": 1.0,
            }

        # 涨停数量
        limit_up_count = len(limit_up_stocks)

        # 计算涨跌分布
        rising_count = sum(1 for q in market_snapshot if q.change_percent > 0)
        falling_count = sum(1 for q in market_snapshot if q.change_percent < 0)

        rising_ratio = rising_count / total_count
        falling_ratio = falling_count / total_count

        # 平均涨幅
        total_change = sum(q.change_percent for q in market_snapshot)
        avg_change_percent = total_change / total_count

        # 市场整体量比
        total_volume_ratio = sum(q.volume_ratio for q in market_snapshot)
        avg_volume_ratio = total_volume_ratio / total_count

        return {
            "limit_up_count": limit_up_count,
            "avg_change_percent": avg_change_percent,
            "rising_ratio": rising_ratio,
            "falling_ratio": falling_ratio,
            "volume_ratio": avg_volume_ratio,
        }

    def _determine_sentiment_state(self, metrics: dict) -> SentimentState:
        """
        根据指标判断情绪状态

        Args:
            metrics: 市场指标

        Returns:
            情绪状态
        """
        limit_up_count = metrics["limit_up_count"]
        avg_change = metrics["avg_change_percent"]
        rising_ratio = metrics["rising_ratio"]
        falling_ratio = metrics["falling_ratio"]
        volume_ratio = metrics["volume_ratio"]

        # 判断逻辑（从高到低优先级）
        state_name = "unknown"
        confidence = 0.0
        description = ""

        # 1. 退潮期判断（最高优先级）
        ebbing_threshold = SENTIMENT_THRESHOLDS["ebbing"]
        if (falling_ratio > ebbing_threshold["falling_ratio"] and
            volume_ratio > ebbing_threshold["volume_ratio"] and
            limit_up_count < ebbing_threshold["limit_up_count"]):
            state_name = "ebbing"
            confidence = min(0.9, falling_ratio + volume_ratio / 10)
            description = "市场高位放量下跌，情绪退潮"

        # 2. 高潮期判断
        elif limit_up_count >= SENTIMENT_THRESHOLDS["climax"]["limit_up_count"]:
            state_name = "climax"
            confidence = min(1.0, limit_up_count / 150)
            description = "涨停数量爆发，市场情绪高潮"

        # 3. 升温期判断
        elif (limit_up_count >= SENTIMENT_THRESHOLDS["heating"]["limit_up_count"] and
              avg_change >= SENTIMENT_THRESHOLDS["heating"]["avg_change_percent"] and
              rising_ratio >= SENTIMENT_THRESHOLDS["heating"]["rising_ratio"]):
            state_name = "heating"
            confidence = (rising_ratio + avg_change / 5) / 2
            description = "市场活跃度提升，情绪升温"

        # 4. 回暖期判断
        elif (limit_up_count >= SENTIMENT_THRESHOLDS["warming"]["limit_up_count"] and
              avg_change >= SENTIMENT_THRESHOLDS["warming"]["avg_change_percent"] and
              rising_ratio >= SENTIMENT_THRESHOLDS["warming"]["rising_ratio"]):
            state_name = "warming"
            confidence = (rising_ratio + avg_change / 3) / 2
            description = "市场开始回暖，局部活跃"

        # 5. 冰点期（默认）
        else:
            state_name = "freezing"
            confidence = 1.0 - rising_ratio
            description = "市场冷清，情绪冰点"

        return SentimentState(
            state=state_name,
            limit_up_count=limit_up_count,
            avg_change_percent=avg_change,
            rising_ratio=rising_ratio,
            falling_ratio=falling_ratio,
            volume_ratio=volume_ratio,
            confidence=confidence,
            description=description,
        )

    def _create_default_state(self) -> SentimentState:
        """创建默认情绪状态（数据获取失败时使用）"""
        return SentimentState(
            state="unknown",
            limit_up_count=0,
            avg_change_percent=0.0,
            rising_ratio=0.0,
            falling_ratio=0.0,
            volume_ratio=1.0,
            confidence=0.0,
            description="数据获取失败，无法判断情绪",
        )

    def get_trading_advice(self, state: Optional[SentimentState] = None) -> str:
        """
        根据情绪状态给出交易建议

        Args:
            state: 情绪状态，如果为None则使用最新状态

        Returns:
            交易建议文本
        """
        if state is None:
            if not self.history:
                return "暂无数据，建议观望"
            state = self.history[-1]

        advice_map = {
            "freezing": "市场冰点期，建议空仓观望，等待回暖信号",
            "warming": "市场开始回暖，可小仓位试探，关注龙头题材",
            "heating": "市场情绪升温，积极参与，但要注意仓位控制",
            "climax": "市场情绪高潮，谨慎追高，随时准备减仓",
            "ebbing": "市场退潮期，立即减仓或清仓，保护利润",
            "unknown": "数据异常，建议暂停交易",
        }

        return advice_map.get(state.state, "无法给出建议")

    def is_suitable_for_trading(self, min_state: str = "warming") -> bool:
        """
        判断当前情绪是否适合交易

        Args:
            min_state: 最低要求的情绪状态

        Returns:
            是否适合交易
        """
        if not self.history:
            return False

        state_priority = {
            "freezing": 0,
            "warming": 1,
            "heating": 2,
            "climax": 3,
            "ebbing": -1,  # 退潮期不适合交易
            "unknown": -2,
        }

        current_state = self.history[-1].state
        current_priority = state_priority.get(current_state, -2)
        min_priority = state_priority.get(min_state, 1)

        return current_priority >= min_priority
