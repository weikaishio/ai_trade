"""
腾讯股票API数据获取和解析模块
"""

import aiohttp
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
import re
import logging

class TencentStockAPI:
    """腾讯股票API客户端"""

    BASE_URL = "http://qt.gtimg.cn/q="

    def __init__(self):
        self.session = None
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _parse_response(self, response_text: str) -> Dict:
        """
        解析腾讯股票API响应

        响应格式示例:
        v_sh600483="1~顺鑫农业~600483~45.23~44.89~45.50~34567~16234~18333~45.23~100~45.22~200..."

        字段说明:
        0: 未知
        1: 股票名称
        2: 股票代码
        3: 当前价格
        4: 昨收价
        5: 今开价
        6: 成交量（手）
        7: 外盘
        8: 内盘
        9-18: 买一到买五价格和量
        19-28: 卖一到卖五价格和量
        29: 最新成交时间
        30: 涨跌额
        31: 涨跌幅
        32: 最高价
        33: 最低价
        34: 成交额（万）
        35: 换手率
        36: 市盈率
        37: 未知
        38: 总市值（万）
        39: 流通市值（万）
        """
        try:
            # 提取数据部分
            match = re.search(r'="(.+)"', response_text)
            if not match:
                raise ValueError(f"Invalid response format: {response_text}")

            data_str = match.group(1)
            fields = data_str.split('~')

            if len(fields) < 40:
                raise ValueError(f"Incomplete data: expected 40+ fields, got {len(fields)}")

            # 解析买卖盘数据
            bid_prices = []
            bid_volumes = []
            ask_prices = []
            ask_volumes = []

            # 买盘数据 (索引 9-18)
            for i in range(9, 19, 2):
                if i < len(fields) and i+1 < len(fields):
                    bid_prices.append(float(fields[i]) if fields[i] else 0)
                    bid_volumes.append(int(fields[i+1]) if fields[i+1] else 0)

            # 卖盘数据 (索引 19-28)
            for i in range(19, 29, 2):
                if i < len(fields) and i+1 < len(fields):
                    ask_prices.append(float(fields[i]) if fields[i] else 0)
                    ask_volumes.append(int(fields[i+1]) if fields[i+1] else 0)

            return {
                'name': fields[1],
                'code': fields[2],
                'current_price': float(fields[3]) if fields[3] else 0,
                'yesterday_close': float(fields[4]) if fields[4] else 0,
                'today_open': float(fields[5]) if fields[5] else 0,
                'volume': int(fields[6]) if fields[6] else 0,  # 成交量（手）
                'outer_disc': int(fields[7]) if fields[7] else 0,  # 外盘
                'inner_disc': int(fields[8]) if fields[8] else 0,  # 内盘
                'bid_prices': bid_prices,
                'bid_volumes': bid_volumes,
                'ask_prices': ask_prices,
                'ask_volumes': ask_volumes,
                'timestamp': fields[29] if len(fields) > 29 else datetime.now().strftime('%H:%M:%S'),
                'change_amount': float(fields[30]) if len(fields) > 30 and fields[30] else 0,
                'change_percent': float(fields[31]) if len(fields) > 31 and fields[31] else 0,
                'high': float(fields[32]) if len(fields) > 32 and fields[32] else 0,
                'low': float(fields[33]) if len(fields) > 33 and fields[33] else 0,
                'turnover': float(fields[34]) if len(fields) > 34 and fields[34] else 0,  # 成交额（万）
                'turnover_rate': float(fields[35]) if len(fields) > 35 and fields[35] else 0,  # 换手率
                'pe_ratio': float(fields[36]) if len(fields) > 36 and fields[36] else 0,  # 市盈率
                'total_market_cap': float(fields[38]) if len(fields) > 38 and fields[38] else 0,  # 总市值（万）
                'circulation_market_cap': float(fields[39]) if len(fields) > 39 and fields[39] else 0,  # 流通市值（万）
            }

        except Exception as e:
            self.logger.error(f"Parse error: {e}, response: {response_text[:200]}")
            raise

    async def get_stock_data(self, stock_code: str) -> Optional[Dict]:
        """
        获取单只股票实时数据

        Args:
            stock_code: 股票代码（如 '600483' 或 'sh600483'）

        Returns:
            解析后的股票数据字典
        """
        # 格式化股票代码
        if not stock_code.startswith(('sh', 'sz')):
            # 自动判断市场
            if stock_code.startswith('6'):
                stock_code = f'sh{stock_code}'
            elif stock_code.startswith(('0', '3')):
                stock_code = f'sz{stock_code}'
            else:
                raise ValueError(f"Unknown stock code format: {stock_code}")

        url = f"{self.BASE_URL}{stock_code}"

        try:
            async with self.session.get(url, timeout=5) as response:
                if response.status != 200:
                    self.logger.error(f"API request failed: {response.status}")
                    return None

                text = await response.text(encoding='gbk')  # 腾讯API使用GBK编码
                return self._parse_response(text)

        except asyncio.TimeoutError:
            self.logger.error(f"Timeout fetching {stock_code}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching {stock_code}: {e}")
            return None

    async def get_batch_stock_data(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """
        批量获取股票数据

        Args:
            stock_codes: 股票代码列表

        Returns:
            {stock_code: stock_data} 字典
        """
        tasks = [self.get_stock_data(code) for code in stock_codes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        data = {}
        for code, result in zip(stock_codes, results):
            if isinstance(result, Exception):
                self.logger.error(f"Failed to get data for {code}: {result}")
                data[code] = None
            else:
                data[code] = result

        return data

    def calculate_technical_indicators(self, stock_data: Dict) -> Dict:
        """
        计算技术指标

        Args:
            stock_data: 股票数据

        Returns:
            包含技术指标的字典
        """
        indicators = {}

        # 计算买卖压力比
        total_bid_volume = sum(stock_data.get('bid_volumes', []))
        total_ask_volume = sum(stock_data.get('ask_volumes', []))

        if total_ask_volume > 0:
            indicators['bid_ask_ratio'] = total_bid_volume / total_ask_volume
        else:
            indicators['bid_ask_ratio'] = float('inf')

        # 计算价格位置（相对于今日高低点）
        high = stock_data.get('high', 0)
        low = stock_data.get('low', 0)
        current = stock_data.get('current_price', 0)

        if high > low:
            indicators['price_position'] = (current - low) / (high - low)
        else:
            indicators['price_position'] = 0.5

        # 计算成交活跃度
        indicators['volume_ratio'] = stock_data.get('volume', 0) / 100000  # 相对于10万手

        # 内外盘比例
        outer = stock_data.get('outer_disc', 0)
        inner = stock_data.get('inner_disc', 0)

        if inner > 0:
            indicators['outer_inner_ratio'] = outer / inner
        else:
            indicators['outer_inner_ratio'] = float('inf') if outer > 0 else 1

        return indicators


# 使用示例
async def example_usage():
    """示例：获取股票数据"""
    async with TencentStockAPI() as client:
        # 获取单只股票
        data = await client.get_stock_data('600483')
        if data:
            print(f"股票名称: {data['name']}")
            print(f"当前价格: {data['current_price']}")
            print(f"涨跌幅: {data['change_percent']}%")

            # 计算技术指标
            indicators = client.calculate_technical_indicators(data)
            print(f"买卖压力比: {indicators['bid_ask_ratio']:.2f}")

        # 批量获取
        batch_data = await client.get_batch_stock_data(['600483', '603993', '600000'])
        for code, stock_data in batch_data.items():
            if stock_data:
                print(f"{code}: {stock_data['name']} - {stock_data['current_price']}")


if __name__ == "__main__":
    asyncio.run(example_usage())