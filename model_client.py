"""
深度学习模型API客户端
"""

import aiohttp
import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging
import json

class DeepLearningModelClient:
    """深度学习模型API客户端"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_comprehensive_score(
        self,
        stock_code: str,
        market_data: Dict,
        position_data: Optional[Dict] = None,
        additional_features: Optional[Dict] = None
    ) -> Dict:
        """
        调用综合评分API

        Args:
            stock_code: 股票代码
            market_data: 市场数据
            position_data: 持仓数据（可选）
            additional_features: 额外特征（可选）

        Returns:
            {
                'score': float,  # 0-100的评分
                'confidence': float,  # 置信度
                'features': Dict,  # 使用的特征
                'recommendation': str,  # 'strong_sell', 'sell', 'hold', 'buy', 'strong_buy'
                'reasons': List[str],  # 决策原因
                'risk_level': str,  # 'low', 'medium', 'high'
            }
        """
        endpoint = f"{self.base_url}/api/comprehensive_score_custom"

        # 构建请求数据
        request_data = self._prepare_model_input(
            stock_code, market_data, position_data, additional_features
        )

        try:
            async with self.session.post(
                endpoint,
                json=request_data,
                timeout=10
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"Model API error: {response.status}, {error_text}")
                    return self._get_default_score()

                result = await response.json()
                return self._parse_model_response(result)

        except asyncio.TimeoutError:
            self.logger.error(f"Model API timeout for {stock_code}")
            return self._get_default_score()
        except Exception as e:
            self.logger.error(f"Model API error for {stock_code}: {e}")
            return self._get_default_score()

    def _prepare_model_input(
        self,
        stock_code: str,
        market_data: Dict,
        position_data: Optional[Dict],
        additional_features: Optional[Dict]
    ) -> Dict:
        """准备模型输入数据"""

        features = {
            # 基础信息
            'stock_code': stock_code,
            'timestamp': datetime.now().isoformat(),

            # 价格特征
            'current_price': market_data.get('current_price', 0),
            'change_percent': market_data.get('change_percent', 0),
            'high': market_data.get('high', 0),
            'low': market_data.get('low', 0),
            'yesterday_close': market_data.get('yesterday_close', 0),

            # 成交特征
            'volume': market_data.get('volume', 0),
            'turnover': market_data.get('turnover', 0),
            'turnover_rate': market_data.get('turnover_rate', 0),

            # 买卖盘特征
            'bid_prices': market_data.get('bid_prices', []),
            'bid_volumes': market_data.get('bid_volumes', []),
            'ask_prices': market_data.get('ask_prices', []),
            'ask_volumes': market_data.get('ask_volumes', []),

            # 市场特征
            'pe_ratio': market_data.get('pe_ratio', 0),
            'total_market_cap': market_data.get('total_market_cap', 0),
            'circulation_market_cap': market_data.get('circulation_market_cap', 0),
        }

        # 添加持仓特征
        if position_data:
            features.update({
                'holding_quantity': position_data.get('quantity', 0),
                'cost_price': position_data.get('cost_price', 0),
                'profit_loss_percent': position_data.get('profit_loss_percent', 0),
                'holding_days': position_data.get('holding_days', 0),
            })

        # 添加额外特征
        if additional_features:
            features.update(additional_features)

        # 计算衍生特征
        features.update(self._calculate_derived_features(features))

        return {'features': features}

    def _calculate_derived_features(self, features: Dict) -> Dict:
        """计算衍生特征"""
        derived = {}

        # 价格相对位置
        high = features.get('high', 0)
        low = features.get('low', 0)
        current = features.get('current_price', 0)

        if high > low:
            derived['price_position'] = (current - low) / (high - low)
        else:
            derived['price_position'] = 0.5

        # 买卖压力
        total_bid = sum(features.get('bid_volumes', []))
        total_ask = sum(features.get('ask_volumes', []))

        if total_ask > 0:
            derived['bid_ask_pressure'] = total_bid / total_ask
        else:
            derived['bid_ask_pressure'] = 1.0

        # 相对强弱
        if 'yesterday_close' in features and features['yesterday_close'] > 0:
            derived['relative_strength'] = current / features['yesterday_close']
        else:
            derived['relative_strength'] = 1.0

        # 波动率
        if high > 0:
            derived['volatility'] = (high - low) / high
        else:
            derived['volatility'] = 0

        return derived

    def _parse_model_response(self, response: Dict) -> Dict:
        """解析模型响应"""
        try:
            score = float(response.get('score', 50))
            confidence = float(response.get('confidence', 0.5))

            # 根据评分确定推荐操作
            if score < 20:
                recommendation = 'strong_sell'
                risk_level = 'high'
            elif score < 40:
                recommendation = 'sell'
                risk_level = 'medium'
            elif score < 60:
                recommendation = 'hold'
                risk_level = 'low'
            elif score < 80:
                recommendation = 'buy'
                risk_level = 'low'
            else:
                recommendation = 'strong_buy'
                risk_level = 'medium'

            return {
                'score': score,
                'confidence': confidence,
                'features': response.get('features', {}),
                'recommendation': recommendation,
                'reasons': response.get('reasons', []),
                'risk_level': risk_level,
                'raw_response': response
            }

        except Exception as e:
            self.logger.error(f"Parse model response error: {e}")
            return self._get_default_score()

    def _get_default_score(self) -> Dict:
        """获取默认评分（当模型不可用时）"""
        return {
            'score': 50.0,
            'confidence': 0.0,
            'features': {},
            'recommendation': 'hold',
            'reasons': ['Model unavailable, using default'],
            'risk_level': 'high'
        }

    async def get_batch_scores(
        self,
        stock_list: List[Tuple[str, Dict, Optional[Dict]]]
    ) -> Dict[str, Dict]:
        """
        批量获取模型评分

        Args:
            stock_list: [(stock_code, market_data, position_data), ...]

        Returns:
            {stock_code: score_result}
        """
        tasks = []
        for stock_code, market_data, position_data in stock_list:
            task = self.get_comprehensive_score(
                stock_code, market_data, position_data
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        scores = {}
        for (stock_code, _, _), result in zip(stock_list, results):
            if isinstance(result, Exception):
                self.logger.error(f"Failed to get score for {stock_code}: {result}")
                scores[stock_code] = self._get_default_score()
            else:
                scores[stock_code] = result

        return scores


# 模型服务器模拟（用于测试）
class ModelServerSimulator:
    """模型服务器模拟器（用于测试）"""

    @staticmethod
    def simulate_score(features: Dict) -> Dict:
        """模拟评分逻辑"""
        import random

        # 简单的规则基础评分
        score = 50.0

        # 价格变化影响
        change_percent = features.get('change_percent', 0)
        score += change_percent * 2

        # 成交量影响
        volume = features.get('volume', 0)
        if volume > 1000000:
            score += 10
        elif volume < 100000:
            score -= 10

        # 买卖压力影响
        bid_ask_pressure = features.get('bid_ask_pressure', 1)
        if bid_ask_pressure > 1.5:
            score += 15
        elif bid_ask_pressure < 0.7:
            score -= 15

        # 持仓盈亏影响
        profit_loss = features.get('profit_loss_percent', 0)
        if profit_loss > 10:
            score -= 20  # 获利了结
        elif profit_loss < -10:
            score -= 30  # 止损

        # 限制在0-100范围
        score = max(0, min(100, score))

        # 添加随机性
        score += random.uniform(-5, 5)

        reasons = []
        if change_percent > 3:
            reasons.append("价格上涨强劲")
        if change_percent < -3:
            reasons.append("价格下跌明显")
        if volume > 1000000:
            reasons.append("成交量活跃")
        if bid_ask_pressure > 1.5:
            reasons.append("买盘强劲")
        if profit_loss > 10:
            reasons.append("建议获利了结")
        if profit_loss < -10:
            reasons.append("建议止损")

        return {
            'score': score,
            'confidence': 0.75 + random.uniform(-0.1, 0.1),
            'reasons': reasons if reasons else ["综合评估"]
        }


# 使用示例
async def example_usage():
    """示例：调用模型API"""
    async with DeepLearningModelClient() as client:
        # 模拟市场数据
        market_data = {
            'current_price': 45.23,
            'change_percent': 2.5,
            'volume': 1234567,
            'high': 46.0,
            'low': 44.5,
            'bid_volumes': [100, 200, 300, 400, 500],
            'ask_volumes': [150, 250, 350, 450, 550],
        }

        # 模拟持仓数据
        position_data = {
            'quantity': 1000,
            'cost_price': 43.50,
            'profit_loss_percent': 3.98,
            'holding_days': 15
        }

        # 获取评分
        score_result = await client.get_comprehensive_score(
            '600483',
            market_data,
            position_data
        )

        print(f"评分: {score_result['score']}")
        print(f"置信度: {score_result['confidence']}")
        print(f"推荐: {score_result['recommendation']}")
        print(f"原因: {', '.join(score_result['reasons'])}")


if __name__ == "__main__":
    asyncio.run(example_usage())