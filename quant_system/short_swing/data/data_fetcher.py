"""
数据获取模块

从东方财富API和模型服务获取数据，支持缓存和重试。
"""

import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
import time

from .models import StockQuote, StockInfo, ModelScore
from .cache_manager import get_cache
from ..config_short_swing import EASTMONEY_API, MODEL_SERVICE
from ..utils.trading_time import is_trading_time, should_use_cached_data

logger = logging.getLogger(__name__)


class DataFetcher:
    """数据获取器"""

    def __init__(self):
        """初始化数据获取器"""
        self.cache = get_cache()
        self.session = requests.Session()
        self.session.headers.update({
            "Referer": "https://quote.eastmoney.com",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        })

    def _to_secid(self, code: str) -> str:
        """
        转换股票代码为东方财富secid格式

        Args:
            code: 股票代码，如 sh600519, sz000001

        Returns:
            secid，如 1.600519, 0.000001
        """
        prefix = code[:2].lower()
        digits = code[2:]

        if prefix == "sh":
            return f"1.{digits}"
        elif prefix == "sz":
            return f"0.{digits}"
        elif prefix == "bj":
            return f"0.{digits}"
        else:
            raise ValueError(f"Unknown market prefix: {prefix} in code {code}")

    def _retry_request(
        self,
        method: str,
        url: str,
        max_retries: int = EASTMONEY_API["retry_times"],
        **kwargs
    ) -> requests.Response:
        """
        带重试的HTTP请求

        Args:
            method: HTTP方法 (GET/POST)
            url: 请求URL
            max_retries: 最大重试次数
            **kwargs: requests参数

        Returns:
            响应对象

        Raises:
            requests.RequestException: 请求失败
        """
        for attempt in range(max_retries):
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=EASTMONEY_API.get("timeout", 10),
                    **kwargs
                )
                response.raise_for_status()
                return response

            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    delay = EASTMONEY_API.get("retry_delay", 1) * (attempt + 1)
                    logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}. "
                                 f"Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"Request failed after {max_retries} attempts: {e}")
                    raise

    def get_market_snapshot(self) -> List[StockQuote]:
        """
        获取A股市场快照（全市场实时行情）

        智能缓存策略：
        - 交易时间内：获取实时数据，并同时缓存到 "last_trading_day" 键
        - 非交易时间：返回上一个交易日的缓存数据

        Returns:
            股票行情列表
        """
        # 检查是否应该使用缓存数据（非交易时间）
        use_cached = should_use_cached_data()

        if use_cached:
            # 非交易时间：尝试返回最近一个交易日的数据
            last_trading_cache_key = "market_snapshot_last_trading_day"
            cached = self.cache.get(last_trading_cache_key, category="market_data")
            if cached:
                logger.info(f"Non-trading time detected, loaded last trading day snapshot ({len(cached)} stocks)")
                return [StockQuote(**item) for item in cached]
            else:
                logger.warning("Non-trading time but no cached data available, falling back to real-time API")

        # 交易时间或缓存未命中：获取实时数据
        cache_key = f"market_snapshot_{datetime.now().strftime('%Y%m%d_%H%M')}"
        cached = self.cache.get(cache_key, category="market_data")
        if cached:
            logger.info("Market snapshot loaded from cache")
            return [StockQuote(**item) for item in cached]

        url = f"{EASTMONEY_API['quote_url']}"
        params = {
            "pn": "1",
            "pz": "5000",  # 获取前5000只股票
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",  # A股主板+创业板+科创板
            "fields": "f12,f13,f14,f2,f3,f4,f5,f6,f7,f15,f16,f17,f18,f8,f9,f10",  # f13是市场代码
        }

        try:
            response = self._retry_request("GET", url, params=params)
            data = response.json()

            if not data.get("data") or not data["data"].get("diff"):
                logger.warning("Empty market snapshot data")
                return []

            quotes = []
            # data["diff"] 是一个字典，需要遍历其值
            for item in data["data"]["diff"].values():
                try:
                    code = item["f12"]
                    market = "sh" if item["f13"] == 1 else "sz"
                    full_code = f"{market}{code}"

                    # 东方财富API返回的价格字段是百分位格式，需要除以100
                    quote = StockQuote(
                        code=full_code,
                        name=item["f14"],
                        price=item["f2"] / 100 if item["f2"] else 0.0,
                        change=item["f4"] / 100 if item["f4"] else 0.0,
                        change_percent=item["f3"] / 100 if item["f3"] else 0.0,
                        open=item["f17"] / 100 if item["f17"] else 0.0,
                        high=item["f15"] / 100 if item["f15"] else 0.0,
                        low=item["f16"] / 100 if item["f16"] else 0.0,
                        prev_close=item["f18"] / 100 if item["f18"] else 0.0,
                        volume=item["f5"],
                        amount=item["f6"],
                        turnover=item.get("f8", 0.0) / 100 if item.get("f8") else 0.0,
                        volume_ratio=item.get("f10", 100) / 100 if item.get("f10") else 1.0,
                        time=datetime.now().strftime("%H:%M:%S"),
                    )
                    quotes.append(quote)
                except (KeyError, TypeError) as e:
                    logger.warning(f"Failed to parse quote item: {e}")
                    continue

            # 缓存1分钟（按时间戳）
            self.cache.set(cache_key, [q.dict() for q in quotes], category="market_data", ttl=60)

            # 如果是交易时间，同时缓存到 "last_trading_day" 键（长期有效）
            is_trading, stage = is_trading_time()
            if is_trading:
                last_trading_cache_key = "market_snapshot_last_trading_day"
                # 缓存24小时，确保非交易时间可用
                self.cache.set(last_trading_cache_key, [q.dict() for q in quotes],
                             category="market_data", ttl=86400)
                logger.info(f"Cached {len(quotes)} stocks to last_trading_day (trading stage: {stage})")

            logger.info(f"Fetched {len(quotes)} stock quotes")
            return quotes

        except Exception as e:
            logger.error(f"Failed to fetch market snapshot: {e}", exc_info=True)
            return []

    def get_limit_up_stocks(self) -> List[StockQuote]:
        """
        获取今日涨停股票列表

        智能缓存策略：
        - 交易时间内：获取实时涨停数据，并缓存到 "limit_up_last_trading_day"
        - 非交易时间：返回上一个交易日的涨停数据

        Returns:
            涨停股票列表
        """
        # 检查是否应该使用缓存数据（非交易时间）
        use_cached = should_use_cached_data()

        if use_cached:
            # 非交易时间：尝试返回最近一个交易日的涨停数据
            last_trading_cache_key = "limit_up_last_trading_day"
            cached = self.cache.get(last_trading_cache_key, category="market_data")
            if cached:
                logger.info(f"Non-trading time detected, loaded last trading day limit-up stocks ({len(cached)} stocks)")
                return [StockQuote(**item) for item in cached]
            else:
                logger.warning("Non-trading time but no cached limit-up data available, falling back to real-time API")

        # 交易时间或缓存未命中：获取实时数据
        cache_key = f"limit_up_{datetime.now().strftime('%Y%m%d_%H%M')}"
        cached = self.cache.get(cache_key, category="market_data")
        if cached:
            logger.info("Limit-up stocks loaded from cache")
            return [StockQuote(**item) for item in cached]

        url = f"{EASTMONEY_API['quote_url']}"
        params = {
            "pn": "1",
            "pz": "500",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            "fields": "f12,f13,f14,f2,f3,f4,f5,f6,f7,f15,f16,f17,f18,f8,f9,f10",  # f13是市场代码
            "fid": "f3",  # 按涨幅排序
        }

        try:
            response = self._retry_request("GET", url, params=params)
            data = response.json()

            if not data.get("data") or not data["data"].get("diff"):
                return []

            limit_up_stocks = []
            # data["diff"] 是一个字典，需要遍历其值
            for item in data["data"]["diff"].values():
                try:
                    # 涨停判断：涨幅 >= 9.8%（原始值是980，考虑精度问题）
                    if item["f3"] < 980:
                        continue

                    code = item["f12"]
                    market = "sh" if item["f13"] == 1 else "sz"
                    full_code = f"{market}{code}"

                    # 东方财富API返回的价格字段是百分位格式，需要除以100
                    quote = StockQuote(
                        code=full_code,
                        name=item["f14"],
                        price=item["f2"] / 100 if item["f2"] else 0.0,
                        change=item["f4"] / 100 if item["f4"] else 0.0,
                        change_percent=item["f3"] / 100 if item["f3"] else 0.0,
                        open=item["f17"] / 100 if item["f17"] else 0.0,
                        high=item["f15"] / 100 if item["f15"] else 0.0,
                        low=item["f16"] / 100 if item["f16"] else 0.0,
                        prev_close=item["f18"] / 100 if item["f18"] else 0.0,
                        volume=item["f5"],
                        amount=item["f6"],
                        turnover=item.get("f8", 0.0) / 100 if item.get("f8") else 0.0,
                        volume_ratio=item.get("f10", 100) / 100 if item.get("f10") else 1.0,
                        time=datetime.now().strftime("%H:%M:%S"),
                    )
                    limit_up_stocks.append(quote)
                except (KeyError, TypeError) as e:
                    logger.warning(f"Failed to parse limit-up stock: {e}")
                    continue

            # 缓存1分钟（按时间戳）
            self.cache.set(cache_key, [q.dict() for q in limit_up_stocks],
                          category="market_data", ttl=60)

            # 如果是交易时间，同时缓存到 "limit_up_last_trading_day" 键（长期有效）
            is_trading, stage = is_trading_time()
            if is_trading:
                last_trading_cache_key = "limit_up_last_trading_day"
                # 缓存24小时，确保非交易时间可用
                self.cache.set(last_trading_cache_key, [q.dict() for q in limit_up_stocks],
                             category="market_data", ttl=86400)
                logger.info(f"Cached {len(limit_up_stocks)} limit-up stocks to last_trading_day (trading stage: {stage})")

            logger.info(f"Fetched {len(limit_up_stocks)} limit-up stocks")
            return limit_up_stocks

        except Exception as e:
            logger.error(f"Failed to fetch limit-up stocks: {e}", exc_info=True)
            return []

    def get_stock_info(self, code: str) -> Optional[StockInfo]:
        """
        获取股票基本信息

        Args:
            code: 股票代码

        Returns:
            股票信息，失败返回None
        """
        cache_key = f"stock_info_{code}"
        cached = self.cache.get(cache_key, category="stock_info")
        if cached:
            return StockInfo(**cached)

        # 简化版：从快照数据中提取基本信息
        # 实际应用可调用更详细的API
        try:
            info = StockInfo(
                code=code,
                name="",  # 从快照获取
                market_cap=0.0,
                circulating_cap=0.0,
                listing_date=None,
                is_st=code.upper().startswith("ST"),
            )

            self.cache.set(cache_key, info.dict(), category="stock_info", ttl=3600)
            return info

        except Exception as e:
            logger.error(f"Failed to fetch stock info for {code}: {e}")
            return None

    def get_model_scores(self, stock_codes: List[str]) -> Dict[str, ModelScore]:
        """
        批量获取模型评分

        Args:
            stock_codes: 股票代码列表

        Returns:
            股票代码 -> ModelScore 映射
        """
        if not stock_codes:
            return {}

        # 检查缓存
        cache_key = f"model_scores_{','.join(sorted(stock_codes))}"
        cached = self.cache.get(cache_key, category="model_score")
        if cached:
            logger.info(f"Model scores for {len(stock_codes)} stocks loaded from cache")
            return {k: ModelScore(**v) for k, v in cached.items()}

        url = f"{MODEL_SERVICE['base_url']}{MODEL_SERVICE['comprehensive_score_endpoint']}"

        # 转换代码格式（去掉sh/sz前缀）
        codes_without_prefix = [code[2:] if len(code) > 6 else code for code in stock_codes]

        try:
            response = requests.post(
                url,
                json={"codes": codes_without_prefix},
                timeout=MODEL_SERVICE.get("timeout", 30),
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("result"):
                logger.warning("Empty model score response")
                return {}

            scores = {}
            for item in data["result"]:
                try:
                    # 模型API返回的字段名是 "code"，不是 "stock_code"
                    code = str(item["code"])  # 可能是数字，转为字符串

                    # 补全股票代码（如果是不足6位的，前面补0）
                    code = code.zfill(6)

                    # 添加市场前缀
                    if code.startswith("6"):
                        full_code = f"sh{code}"
                    elif code.startswith("0") or code.startswith("3"):
                        full_code = f"sz{code}"
                    else:
                        full_code = f"sz{code}"  # 默认深圳

                    score = ModelScore(
                        code=full_code,
                        limit_up_prob=item.get("limit_up_prob", 0.0),
                        downside_risk_prob=item.get("downside_risk_prob", 0.0),
                        chanlun_risk_prob=item.get("chanlun_risk_prob", 0.0),
                        short_term_risk=item.get("short_term_risk", 0.0),
                        total_score=item.get("total_score", 0.0),
                    )
                    scores[full_code] = score
                except (KeyError, TypeError) as e:
                    logger.warning(f"Failed to parse model score: {e}")
                    continue

            # 缓存5分钟
            self.cache.set(cache_key, {k: v.dict() for k, v in scores.items()},
                          category="model_score", ttl=300)
            logger.info(f"Fetched model scores for {len(scores)} stocks")
            return scores

        except Exception as e:
            logger.error(f"Failed to fetch model scores: {e}", exc_info=True)
            return {}


# 全局数据获取器实例
_fetcher_instance: Optional[DataFetcher] = None


def get_fetcher() -> DataFetcher:
    """获取全局数据获取器实例（单例模式）"""
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = DataFetcher()
    return _fetcher_instance
