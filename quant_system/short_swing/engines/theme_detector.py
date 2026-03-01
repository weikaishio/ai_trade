"""
主线题材识别引擎

识别当前市场主线题材和龙头股票。
"""

import logging
from typing import List, Dict, Optional
from collections import defaultdict

from ..data.models import StockQuote, Theme, ThemeStock
from ..data.data_fetcher import get_fetcher
from ..config_short_swing import THEME_DETECTION, LEADER_CRITERIA

logger = logging.getLogger(__name__)


class ThemeDetector:
    """主线题材识别引擎"""

    def __init__(self):
        """初始化题材检测器"""
        self.fetcher = get_fetcher()

    def detect_themes(self) -> List[Theme]:
        """
        检测当前市场主线题材

        Returns:
            题材列表，按强度排序
        """
        logger.info("Starting theme detection...")

        # 获取涨停股票和强势股票（涨幅>5%）
        limit_up_stocks = self.fetcher.get_limit_up_stocks()
        market_snapshot = self.fetcher.get_market_snapshot()
        strong_stocks = [q for q in market_snapshot if q.change_percent >= 5.0]

        # 合并强势股票池
        all_strong_stocks = self._merge_and_deduplicate(limit_up_stocks, strong_stocks)

        if not all_strong_stocks:
            logger.warning("No strong stocks found for theme detection")
            return []

        # 简化版：基于股票名称中的关键词聚类
        # 实际应用中可以调用概念板块API或使用更复杂的聚类算法
        themes = self._cluster_by_keywords(all_strong_stocks)

        # 筛选和评分
        valid_themes = []
        for theme in themes:
            if self._is_valid_theme(theme):
                # 识别龙头股
                theme.leader_stock = self._identify_leader(theme.stocks)
                # 计算题材强度评分
                theme.score = self._calculate_theme_score(theme)
                valid_themes.append(theme)

        # 按评分排序
        valid_themes.sort(key=lambda t: t.score, reverse=True)

        logger.info(f"Detected {len(valid_themes)} valid themes")
        for theme in valid_themes[:3]:
            logger.info(f"  - {theme.theme_name}: {theme.stock_count} stocks, "
                       f"score={theme.score:.1f}, leader={theme.leader_stock.name if theme.leader_stock else 'None'}")

        return valid_themes

    def _merge_and_deduplicate(
        self,
        limit_up: List[StockQuote],
        strong: List[StockQuote]
    ) -> List[StockQuote]:
        """合并并去重股票列表"""
        seen_codes = set()
        merged = []

        for stock in limit_up + strong:
            if stock.code not in seen_codes:
                seen_codes.add(stock.code)
                merged.append(stock)

        return merged

    def _cluster_by_keywords(self, stocks: List[StockQuote]) -> List[Theme]:
        """
        基于股票名称关键词进行主题聚类

        简化版实现：从股票名称中提取常见题材关键词
        """
        # 预定义题材关键词（可扩展）
        theme_keywords = {
            "芯片": ["芯片", "半导体", "集成电路"],
            "新能源": ["新能源", "锂电", "光伏", "储能"],
            "AI": ["人工智能", "AI", "算力", "大模型"],
            "医药": ["医药", "生物", "医疗", "疫苗"],
            "汽车": ["汽车", "车", "整车"],
            "地产": ["地产", "房地产", "建筑"],
            "军工": ["军工", "国防", "航空", "航天"],
            "消费": ["消费", "白酒", "食品", "零售"],
            "金融": ["银行", "保险", "证券", "金融"],
            "科技": ["科技", "软件", "互联网", "5G", "数码", "电子", "通信"],
            "农业": ["农业", "种植", "养殖", "智农", "农牧", "渔业", "农产品"],
            "有色金属": ["有色", "金属", "铜", "铝", "锌", "岭南", "锡", "镍", "铅"],
            "环保": ["环保", "生态", "环卫", "天楹", "垃圾", "水务", "节能", "治理"],
            "化工": ["化工", "化学", "农药", "化肥", "塑料"],
            "钢铁": ["钢铁", "钢", "铁"],
            "煤炭": ["煤炭", "煤", "能源"],
            "电力": ["电力", "发电", "水电", "核电", "电网"],
            "交通": ["交通", "物流", "航运", "港口", "快递", "运输"],
            "传媒": ["传媒", "广告", "影视", "游戏", "出版", "文化"],
        }

        # 聚类
        clusters: Dict[str, List[StockQuote]] = defaultdict(list)

        for stock in stocks:
            matched = False
            for theme_name, keywords in theme_keywords.items():
                if any(kw in stock.name for kw in keywords):
                    clusters[theme_name].append(stock)
                    matched = True
                    break  # 只归类到第一个匹配的题材

            # 未匹配到已知题材，归类为"其他"
            if not matched:
                clusters["其他"].append(stock)

        # 转换为Theme对象
        themes = []
        for theme_name, theme_stocks in clusters.items():
            if theme_name == "其他":  # 跳过"其他"分类
                continue

            theme_stock_list = [
                ThemeStock(
                    code=s.code,
                    name=s.name,
                    change_percent=s.change_percent,
                    volume_ratio=s.volume_ratio,
                    is_leader=False,  # 稍后识别
                )
                for s in theme_stocks
            ]

            avg_change = sum(s.change_percent for s in theme_stocks) / len(theme_stocks)

            theme = Theme(
                theme_name=theme_name,
                concept_codes=[],  # 简化版未使用概念板块代码
                stocks=theme_stock_list,
                leader_stock=None,
                avg_change_percent=avg_change,
                stock_count=len(theme_stock_list),
                score=0.0,  # 稍后计算
            )
            themes.append(theme)

        return themes

    def _is_valid_theme(self, theme: Theme) -> bool:
        """
        判断题材是否有效

        Args:
            theme: 题材对象

        Returns:
            是否有效
        """
        min_stocks = THEME_DETECTION["min_stocks_per_theme"]
        min_avg_change = THEME_DETECTION["min_avg_change_percent"]

        return (
            theme.stock_count >= min_stocks and
            theme.avg_change_percent >= min_avg_change
        )

    def _identify_leader(self, stocks: List[ThemeStock]) -> Optional[ThemeStock]:
        """
        识别题材龙头股

        Args:
            stocks: 题材内股票列表

        Returns:
            龙头股，如果没有符合条件的则返回None
        """
        if not stocks:
            return None

        # 龙头股标准（按优先级）
        candidates = []

        for stock in stocks:
            score = 0.0

            # 1. 涨停优先
            if stock.change_percent >= 9.8:
                score += 50

            # 2. 量比放大
            if stock.volume_ratio >= LEADER_CRITERIA["min_volume_ratio"]:
                score += 20

            # 3. 涨幅高
            score += stock.change_percent * 2

            candidates.append((stock, score))

        # 按评分排序，取最高分
        candidates.sort(key=lambda x: x[1], reverse=True)
        leader, leader_score = candidates[0]

        # 最低评分要求
        if leader_score >= 50:
            leader.is_leader = True
            return leader

        return None

    def _calculate_theme_score(self, theme: Theme) -> float:
        """
        计算题材强度评分（0-100分）

        Args:
            theme: 题材对象

        Returns:
            评分
        """
        score = 0.0

        # 1. 股票数量（最多30分）
        stock_count_score = min(30, theme.stock_count * 2)
        score += stock_count_score

        # 2. 平均涨幅（最多40分）
        avg_change_score = min(40, theme.avg_change_percent * 3)
        score += avg_change_score

        # 3. 龙头加成（20分）
        if theme.leader_stock:
            score += 20

        # 4. 整体活跃度（量比，最多10分）
        avg_volume_ratio = sum(s.volume_ratio for s in theme.stocks) / len(theme.stocks)
        volume_score = min(10, avg_volume_ratio * 3)
        score += volume_score

        return min(100.0, score)

    def get_top_theme(self) -> Optional[Theme]:
        """
        获取当前最强主线题材

        Returns:
            最强题材，如果没有则返回None
        """
        themes = self.detect_themes()
        return themes[0] if themes else None
