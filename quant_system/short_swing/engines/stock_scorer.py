"""
选股评分系统

整合市场数据、模型评分和情绪周期，生成选股候选列表。
"""

import logging
from typing import List, Optional

from ..data.models import StockQuote, StockCandidate, SentimentState, Theme
from ..data.data_fetcher import get_fetcher
from ..config_short_swing import (
    STOCK_SCORING_WEIGHTS,
    SHORT_SWING_FILTERS,
    SCORE_THRESHOLDS,
)

logger = logging.getLogger(__name__)


class StockScorer:
    """选股评分系统"""

    def __init__(self):
        """初始化选股评分器"""
        self.fetcher = get_fetcher()

    def generate_candidates(
        self,
        sentiment: SentimentState,
        themes: List[Theme],
        limit: int = 20,
        min_score: float = SCORE_THRESHOLDS["watch"]
    ) -> List[StockCandidate]:
        """
        生成选股候选列表

        Args:
            sentiment: 当前情绪状态
            themes: 主线题材列表
            limit: 返回数量上限
            min_score: 最低评分

        Returns:
            候选股票列表，按评分排序
        """
        logger.info(f"Generating stock candidates (min_score={min_score}, limit={limit})...")

        # 获取市场快照
        market_snapshot = self.fetcher.get_market_snapshot()
        if not market_snapshot:
            logger.error("Failed to fetch market snapshot")
            return []

        # 应用基础过滤
        filtered_stocks = self._apply_filters(market_snapshot)
        logger.info(f"Filtered {len(filtered_stocks)} stocks from {len(market_snapshot)}")

        if not filtered_stocks:
            logger.warning("No stocks passed filters")
            return []

        # 获取模型评分
        stock_codes = [s.code for s in filtered_stocks]
        model_scores = self.fetcher.get_model_scores(stock_codes)

        # 构建题材映射（股票代码 -> 题材名称）
        theme_map = self._build_theme_map(themes)

        # 评分和构建候选对象
        candidates = []
        for stock in filtered_stocks:
            # 跳过没有模型评分的股票
            if stock.code not in model_scores:
                logger.debug(f"Skipping {stock.code}: no model score")
                continue

            score_obj = model_scores[stock.code]

            # 计算综合评分
            final_score = self._calculate_final_score(
                stock=stock,
                model_score=score_obj,
                sentiment=sentiment,
                is_in_theme=(stock.code in theme_map)
            )

            # 评分过滤
            if final_score < min_score:
                continue

            # 判断信号
            signal = self._determine_signal(final_score)

            # 构建候选对象
            candidate = StockCandidate(
                code=stock.code,
                name=stock.name,
                price=stock.price,
                change_percent=stock.change_percent,
                volume_ratio=stock.volume_ratio,
                turnover=stock.turnover,
                market_cap=0.0,  # 简化版未获取市值
                limit_up_prob=score_obj.limit_up_prob,
                downside_risk=score_obj.downside_risk_prob,
                chanlun_risk=score_obj.chanlun_risk_prob,
                final_score=final_score,
                signal=signal,
                theme=theme_map.get(stock.code),
                is_leader=self._is_leader_in_themes(stock.code, themes),
                sentiment_bonus=self._calculate_sentiment_bonus(sentiment),
            )
            candidates.append(candidate)

        # 按评分排序
        candidates.sort(key=lambda c: c.final_score, reverse=True)

        # 截取前N个
        top_candidates = candidates[:limit]

        logger.info(f"Generated {len(top_candidates)} candidates")
        for i, c in enumerate(top_candidates[:5], 1):
            logger.info(f"  {i}. {c.name} ({c.code}): score={c.final_score:.1f}, "
                       f"signal={c.signal}, theme={c.theme or 'None'}")

        return top_candidates

    def _apply_filters(self, stocks: List[StockQuote]) -> List[StockQuote]:
        """
        应用超短线选股过滤条件

        Args:
            stocks: 股票列表

        Returns:
            过滤后的股票列表
        """
        filtered = []

        for stock in stocks:
            # 价格过滤
            if stock.price > SHORT_SWING_FILTERS["max_price"]:
                continue

            # 量比过滤
            if stock.volume_ratio < SHORT_SWING_FILTERS["min_volume_ratio"]:
                continue

            # 换手率过滤
            if stock.turnover < SHORT_SWING_FILTERS["min_turnover"]:
                continue

            # ST股票过滤
            if SHORT_SWING_FILTERS["exclude_st"] and "ST" in stock.name:
                continue

            # 涨幅过滤（排除涨停，留给主题识别）
            if stock.change_percent >= 9.8:
                continue

            # 跌幅过滤（排除跌停）
            if stock.change_percent <= -9.8:
                continue

            filtered.append(stock)

        return filtered

    def _calculate_final_score(
        self,
        stock: StockQuote,
        model_score,
        sentiment: SentimentState,
        is_in_theme: bool
    ) -> float:
        """
        计算股票最终评分（0-100分）

        Args:
            stock: 股票行情
            model_score: 模型评分对象
            sentiment: 情绪状态
            is_in_theme: 是否属于主线题材

        Returns:
            最终评分
        """
        weights = STOCK_SCORING_WEIGHTS

        # 基础分（模型综合分）
        base_score = model_score.total_score

        # 涨停概率加成
        limit_up_bonus = model_score.limit_up_prob * weights["limit_up_prob"] * 100

        # 风险扣分
        downside_penalty = model_score.downside_risk_prob * weights["downside_risk"] * 100
        chanlun_penalty = model_score.chanlun_risk_prob * weights["chanlun_risk"] * 100

        # 情绪周期加成
        sentiment_bonus = self._calculate_sentiment_bonus(sentiment) * weights["sentiment_bonus"] * 100

        # 主题加成
        theme_bonus = 10.0 if is_in_theme else 0.0

        # 综合评分
        final_score = (
            base_score * 0.3 +  # 基础分占30%
            limit_up_bonus +
            downside_penalty +
            chanlun_penalty +
            sentiment_bonus +
            theme_bonus
        )

        return min(100.0, max(0.0, final_score))

    def _calculate_sentiment_bonus(self, sentiment: SentimentState) -> float:
        """
        计算情绪周期加成系数（0-1）

        Args:
            sentiment: 情绪状态

        Returns:
            加成系数
        """
        sentiment_bonus_map = {
            "freezing": 0.0,  # 冰点期无加成
            "warming": 0.3,   # 回暖期小幅加成
            "heating": 0.6,   # 升温期中等加成
            "climax": 0.4,    # 高潮期降低加成（风险高）
            "ebbing": -0.5,   # 退潮期负加成（风险极高）
            "unknown": 0.0,
        }

        return sentiment_bonus_map.get(sentiment.state, 0.0)

    def _determine_signal(self, score: float) -> str:
        """
        根据评分确定信号

        Args:
            score: 最终评分

        Returns:
            信号类型: strong_buy/buy/watch/ignore
        """
        if score >= SCORE_THRESHOLDS["strong_buy"]:
            return "strong_buy"
        elif score >= SCORE_THRESHOLDS["buy"]:
            return "buy"
        elif score >= SCORE_THRESHOLDS["watch"]:
            return "watch"
        else:
            return "ignore"

    def _build_theme_map(self, themes: List[Theme]) -> dict:
        """
        构建股票代码 -> 题材名称映射

        Args:
            themes: 题材列表

        Returns:
            {股票代码: 题材名称}
        """
        theme_map = {}
        for theme in themes:
            for stock in theme.stocks:
                theme_map[stock.code] = theme.theme_name
        return theme_map

    def _is_leader_in_themes(self, code: str, themes: List[Theme]) -> bool:
        """
        判断股票是否为某个题材的龙头

        Args:
            code: 股票代码
            themes: 题材列表

        Returns:
            是否为龙头
        """
        for theme in themes:
            if theme.leader_stock and theme.leader_stock.code == code:
                return True
        return False
