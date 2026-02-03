"""
市场数据客户端模块

使用腾讯股票API获取实时行情数据，支持批量查询、缓存和异常处理。
"""

import re
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from .config_quant import (
        TENCENT_STOCK_API_URL,
        STOCK_API_TIMEOUT,
        STOCK_API_RETRY,
        CACHE_ENABLED,
        CACHE_TTL,
        format_stock_code
    )
except ImportError:
    from config_quant import (
        TENCENT_STOCK_API_URL,
        STOCK_API_TIMEOUT,
        STOCK_API_RETRY,
        CACHE_ENABLED,
        CACHE_TTL,
        format_stock_code
    )

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class StockData:
    """股票实时数据模型"""
    code: str                    # 股票代码（6位）
    name: str                    # 股票名称
    current_price: float         # 当前价
    change_amount: float         # 涨跌额
    change_percent: float        # 涨跌幅（%）
    volume: int                  # 成交量（手）
    turnover: float              # 成交额（万元）
    highest: float               # 最高价
    lowest: float                # 最低价
    open_price: float            # 今开
    previous_close: float        # 昨收
    timestamp: datetime          # 数据时间戳

    # 盘口数据（可选，默认为空）
    bid_prices: List[float] = field(default_factory=list)      # 买一到买五价格
    bid_volumes: List[int] = field(default_factory=list)       # 买一到买五数量
    ask_prices: List[float] = field(default_factory=list)      # 卖一到卖五价格
    ask_volumes: List[int] = field(default_factory=list)       # 卖一到卖五数量
    outer_disc: int = 0                 # 外盘
    inner_disc: int = 0                 # 内盘

    # 扩展数据（可选）
    pe_ratio: float = 0.0               # 市盈率
    total_market_cap: float = 0.0       # 总市值（万）
    circulation_market_cap: float = 0.0 # 流通市值（万）
    turnover_rate: float = 0.0          # 换手率

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "code": self.code,
            "name": self.name,
            "current_price": self.current_price,
            "change_amount": self.change_amount,
            "change_percent": self.change_percent,
            "volume": self.volume,
            "turnover": self.turnover,
            "highest": self.highest,
            "lowest": self.lowest,
            "open_price": self.open_price,
            "previous_close": self.previous_close,
            "timestamp": self.timestamp.isoformat()
        }

    def is_limit_up(self) -> bool:
        """是否涨停"""
        return abs(self.change_percent - 10.0) < 0.01

    def is_limit_down(self) -> bool:
        """是否跌停"""
        return abs(self.change_percent + 10.0) < 0.01

    def get_price_position(self) -> float:
        """
        获取当前价在日内区间的位置（0-1）
        0: 在最低价，1: 在最高价
        """
        if self.highest == self.lowest:
            return 0.5
        return (self.current_price - self.lowest) / (self.highest - self.lowest)

    def calculate_technical_indicators(self) -> Dict:
        """
        计算技术指标

        Returns:
            包含技术指标的字典
        """
        indicators = {}

        # 计算买卖压力比
        total_bid_volume = sum(self.bid_volumes) if self.bid_volumes else 0
        total_ask_volume = sum(self.ask_volumes) if self.ask_volumes else 0

        if total_ask_volume > 0:
            indicators['bid_ask_ratio'] = total_bid_volume / total_ask_volume
        else:
            indicators['bid_ask_ratio'] = float('inf') if total_bid_volume > 0 else 1.0

        # 计算价格位置（相对于今日高低点）
        indicators['price_position'] = self.get_price_position()

        # 计算成交活跃度（相对于10万手）
        indicators['volume_ratio'] = self.volume / 100000 if self.volume else 0

        # 内外盘比例
        if self.inner_disc > 0:
            indicators['outer_inner_ratio'] = self.outer_disc / self.inner_disc
        else:
            indicators['outer_inner_ratio'] = float('inf') if self.outer_disc > 0 else 1.0

        # 振幅
        if self.previous_close > 0:
            indicators['amplitude'] = ((self.highest - self.lowest) / self.previous_close) * 100
        else:
            indicators['amplitude'] = 0

        # 量比（当日成交量与近期平均成交量的比值，这里简化处理）
        indicators['volume'] = self.volume
        indicators['turnover'] = self.turnover

        return indicators


class MarketDataClient:
    """
    市场数据客户端

    使用腾讯股票API获取实时行情数据
    API URL: http://qt.gtimg.cn/q=sh600483,sz000001
    """

    def __init__(self, enable_cache: bool = CACHE_ENABLED, cache_ttl: int = CACHE_TTL):
        """
        初始化市场数据客户端

        Args:
            enable_cache: 是否启用缓存
            cache_ttl: 缓存有效期（秒）
        """
        self.api_url = TENCENT_STOCK_API_URL
        self.timeout = STOCK_API_TIMEOUT
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[StockData, datetime]] = {}

        # 配置请求会话（支持重试）
        self.session = requests.Session()
        retry_strategy = Retry(
            total=STOCK_API_RETRY,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        logger.info("市场数据客户端初始化完成")

    def get_stock_data(self, code: str, use_cache: bool = True) -> Optional[StockData]:
        """
        获取单只股票实时数据

        Args:
            code: 股票代码（6位数字）
            use_cache: 是否使用缓存

        Returns:
            StockData对象，失败返回None
        """
        # 检查缓存
        if use_cache and self.enable_cache:
            cached_data = self._get_from_cache(code)
            if cached_data:
                logger.debug(f"从缓存获取 {code} 数据")
                return cached_data

        try:
            # 格式化股票代码
            formatted_code = format_stock_code(code)

            # 发起请求
            url = f"{self.api_url}{formatted_code}"
            logger.debug(f"请求URL: {url}")

            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = 'gbk'  # 腾讯API返回GBK编码

            # 解析数据
            stock_data = self._parse_response(response.text, code)

            if stock_data:
                # 缓存数据
                if self.enable_cache:
                    self._save_to_cache(code, stock_data)
                logger.info(f"成功获取 {code} 数据: {stock_data.name} {stock_data.current_price}")
                return stock_data
            else:
                logger.warning(f"解析 {code} 数据失败")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"请求 {code} 数据超时")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"请求 {code} 数据失败: {e}")
            return None
        except Exception as e:
            logger.error(f"获取 {code} 数据异常: {e}", exc_info=True)
            return None

    def get_batch_stock_data(
        self,
        codes: List[str],
        use_cache: bool = True
    ) -> Dict[str, Optional[StockData]]:
        """
        批量获取股票数据

        Args:
            codes: 股票代码列表
            use_cache: 是否使用缓存

        Returns:
            {股票代码: StockData对象} 字典
        """
        result = {}

        # 分离缓存命中和未命中的代码
        cached_codes = []
        uncached_codes = []

        if use_cache and self.enable_cache:
            for code in codes:
                cached_data = self._get_from_cache(code)
                if cached_data:
                    result[code] = cached_data
                    cached_codes.append(code)
                else:
                    uncached_codes.append(code)
        else:
            uncached_codes = codes

        if cached_codes:
            logger.info(f"从缓存获取 {len(cached_codes)} 只股票数据")

        if not uncached_codes:
            return result

        # 批量请求未缓存的数据
        try:
            # 格式化所有代码
            formatted_codes = [format_stock_code(code) for code in uncached_codes]
            codes_str = ",".join(formatted_codes)

            # 发起请求
            url = f"{self.api_url}{codes_str}"
            logger.debug(f"批量请求URL: {url}")

            response = self.session.get(url, timeout=self.timeout * 2)  # 批量请求超时时间翻倍
            response.raise_for_status()
            response.encoding = 'gbk'

            # 解析每只股票的数据
            for code in uncached_codes:
                stock_data = self._parse_response(response.text, code)
                result[code] = stock_data

                if stock_data and self.enable_cache:
                    self._save_to_cache(code, stock_data)

            logger.info(f"成功批量获取 {len(uncached_codes)} 只股票数据")

        except Exception as e:
            logger.error(f"批量获取股票数据失败: {e}", exc_info=True)
            # 失败时尝试逐个获取
            logger.info("尝试逐个获取股票数据...")
            for code in uncached_codes:
                if code not in result:
                    result[code] = self.get_stock_data(code, use_cache=False)

        return result

    def _parse_response(self, response_text: str, code: str) -> Optional[StockData]:
        """
        解析腾讯API响应数据

        响应格式：
        v_sh600483="1~证券简称~600483~当前价~涨跌~涨跌%~成交量(手)~成交额(万)~...~最高~最低~今开~昨收~..."

        Args:
            response_text: API响应文本
            code: 股票代码

        Returns:
            StockData对象或None
        """
        try:
            # 提取对应股票的数据行
            pattern = rf'v_[a-z]+{code}="([^"]+)"'
            match = re.search(pattern, response_text)

            if not match:
                logger.warning(f"未找到 {code} 的数据")
                return None

            data_str = match.group(1)
            fields = data_str.split('~')

            # 检查字段数量（至少需要40个字段）
            if len(fields) < 40:
                logger.warning(f"{code} 数据字段不完整: {len(fields)} 字段")
                return None

            # 解析基础字段
            name = fields[1]
            current_price = float(fields[3]) if fields[3] else 0.0
            previous_close = float(fields[4]) if fields[4] else 0.0
            open_price = float(fields[5]) if fields[5] else 0.0
            volume = int(fields[6]) if fields[6] else 0
            outer_disc = int(fields[7]) if fields[7] else 0  # 外盘
            inner_disc = int(fields[8]) if fields[8] else 0  # 内盘

            # 解析买卖盘数据（买卖五档）
            bid_prices = []
            bid_volumes = []
            ask_prices = []
            ask_volumes = []

            # 买盘数据 (索引 9-18: 买一价、买一量、买二价、买二量...)
            for i in range(9, 19, 2):
                if i < len(fields) and i+1 < len(fields):
                    bid_prices.append(float(fields[i]) if fields[i] else 0.0)
                    bid_volumes.append(int(fields[i+1]) if fields[i+1] else 0)

            # 卖盘数据 (索引 19-28: 卖一价、卖一量、卖二价、卖二量...)
            for i in range(19, 29, 2):
                if i < len(fields) and i+1 < len(fields):
                    ask_prices.append(float(fields[i]) if fields[i] else 0.0)
                    ask_volumes.append(int(fields[i+1]) if fields[i+1] else 0)

            # 解析价格和涨跌数据
            change_amount = float(fields[31]) if len(fields) > 31 and fields[31] else 0.0
            change_percent = float(fields[32]) if len(fields) > 32 and fields[32] else 0.0
            highest = float(fields[33]) if len(fields) > 33 and fields[33] else current_price
            lowest = float(fields[34]) if len(fields) > 34 and fields[34] else current_price
            turnover = float(fields[37]) if len(fields) > 37 and fields[37] else 0.0

            # 解析扩展数据
            turnover_rate = float(fields[38]) if len(fields) > 38 and fields[38] else 0.0
            pe_ratio = float(fields[39]) if len(fields) > 39 and fields[39] else 0.0
            total_market_cap = float(fields[45]) if len(fields) > 45 and fields[45] else 0.0
            circulation_market_cap = float(fields[44]) if len(fields) > 44 and fields[44] else 0.0

            # 创建StockData对象
            stock_data = StockData(
                code=code,
                name=name,
                current_price=current_price,
                change_amount=change_amount,
                change_percent=change_percent,
                volume=volume,
                turnover=turnover,
                highest=highest,
                lowest=lowest,
                open_price=open_price,
                previous_close=previous_close,
                timestamp=datetime.now(),
                # 盘口数据
                bid_prices=bid_prices,
                bid_volumes=bid_volumes,
                ask_prices=ask_prices,
                ask_volumes=ask_volumes,
                outer_disc=outer_disc,
                inner_disc=inner_disc,
                # 扩展数据
                pe_ratio=pe_ratio,
                total_market_cap=total_market_cap,
                circulation_market_cap=circulation_market_cap,
                turnover_rate=turnover_rate
            )

            return stock_data

        except (IndexError, ValueError) as e:
            logger.error(f"解析 {code} 数据失败: {e}")
            return None

    def _get_from_cache(self, code: str) -> Optional[StockData]:
        """从缓存获取数据"""
        if code in self._cache:
            stock_data, cache_time = self._cache[code]
            # 检查缓存是否过期
            if datetime.now() - cache_time < timedelta(seconds=self.cache_ttl):
                return stock_data
            else:
                # 删除过期缓存
                del self._cache[code]
        return None

    def _save_to_cache(self, code: str, stock_data: StockData) -> None:
        """保存数据到缓存"""
        self._cache[code] = (stock_data, datetime.now())

    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        logger.info("缓存已清空")

    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        now = datetime.now()
        valid_count = sum(
            1 for _, cache_time in self._cache.values()
            if now - cache_time < timedelta(seconds=self.cache_ttl)
        )

        return {
            "total_cached": len(self._cache),
            "valid_cached": valid_count,
            "expired_cached": len(self._cache) - valid_count,
            "cache_enabled": self.enable_cache,
            "cache_ttl": self.cache_ttl
        }


# ============================================================================
# 使用示例和测试
# ============================================================================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建客户端
    client = MarketDataClient()

    # 测试单个股票查询
    print("\n=== 测试单个股票查询 ===")
    stock_data = client.get_stock_data("600483")
    if stock_data:
        print(f"股票: {stock_data.name} ({stock_data.code})")
        print(f"当前价: {stock_data.current_price}")
        print(f"涨跌幅: {stock_data.change_percent}%")
        print(f"成交量: {stock_data.volume}手")
        print(f"价格位置: {stock_data.get_price_position():.2%}")
        print(f"涨停: {stock_data.is_limit_up()}")
        print(f"跌停: {stock_data.is_limit_down()}")

    # 测试批量查询
    print("\n=== 测试批量查询 ===")
    codes = ["600483", "603993", "000001"]
    batch_data = client.get_batch_stock_data(codes)

    for code, data in batch_data.items():
        if data:
            print(f"{code} - {data.name}: {data.current_price} ({data.change_percent:+.2f}%)")
        else:
            print(f"{code} - 获取失败")

    # 测试缓存
    print("\n=== 测试缓存 ===")
    print("缓存统计:", client.get_cache_stats())

    # 再次查询（应该命中缓存）
    print("\n再次查询（使用缓存）...")
    stock_data2 = client.get_stock_data("600483", use_cache=True)
    if stock_data2:
        print(f"缓存数据: {stock_data2.name} {stock_data2.current_price}")

    print("\n缓存统计:", client.get_cache_stats())
