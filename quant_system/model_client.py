"""
深度学习模型客户端模块

连接到深度学习模型API，获取股票综合评分和交易建议。
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from .config_quant import (
        MODEL_API_URL,
        MODEL_API_TIMEOUT,
        MODEL_API_RETRY,
        CACHE_ENABLED,
        CACHE_TTL,
        get_decision_level
    )
except ImportError:
    from config_quant import (
        MODEL_API_URL,
        MODEL_API_TIMEOUT,
        MODEL_API_RETRY,
        CACHE_ENABLED,
        CACHE_TTL,
        get_decision_level
    )

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class ModelScore:
    """模型评分结果"""
    stock_code: str              # 股票代码
    score: float                 # 综合评分 (0-100)
    recommendation: str          # 推荐操作: strong_sell, sell, hold, buy, strong_buy
    confidence: float            # 置信度 (0-1)
    factors: Dict[str, float]    # 各因子得分（可选）
    timestamp: datetime          # 评分时间

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "stock_code": self.stock_code,
            "score": self.score,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "factors": self.factors,
            "timestamp": self.timestamp.isoformat()
        }

    def is_strong_sell_signal(self) -> bool:
        """是否为强烈卖出信号"""
        return self.recommendation == "strong_sell" and self.confidence > 0.7

    def is_sell_signal(self) -> bool:
        """是否为卖出信号"""
        return self.recommendation in ["strong_sell", "sell"] and self.confidence > 0.6


class ModelClient:
    """
    深度学习模型客户端

    连接到 server_v2.py 的 comprehensive_score_custom_api
    获取股票综合评分和交易建议
    """

    def __init__(
        self,
        api_url: str = MODEL_API_URL,
        enable_cache: bool = CACHE_ENABLED,
        cache_ttl: int = CACHE_TTL
    ):
        """
        初始化模型客户端

        Args:
            api_url: 模型API地址
            enable_cache: 是否启用缓存
            cache_ttl: 缓存有效期（秒）
        """
        self.api_url = api_url
        self.timeout = MODEL_API_TIMEOUT
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[ModelScore, datetime]] = {}

        # 配置请求会话（支持重试）
        self.session = requests.Session()
        retry_strategy = Retry(
            total=MODEL_API_RETRY,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        logger.info(f"模型客户端初始化完成: {self.api_url}")

    def get_score(
        self,
        stock_code: str,
        current_price: Optional[float] = None,
        holding_days: Optional[int] = None,
        profit_loss_ratio: Optional[float] = None,
        use_cache: bool = True
    ) -> Optional[ModelScore]:
        """
        获取股票综合评分

        Args:
            stock_code: 股票代码
            current_price: 当前价格（可选）
            holding_days: 持仓天数（可选）
            profit_loss_ratio: 盈亏比例（可选）
            use_cache: 是否使用缓存

        Returns:
            ModelScore对象，失败返回None
        """
        # 检查缓存
        cache_key = self._generate_cache_key(
            stock_code, current_price, holding_days, profit_loss_ratio
        )

        if use_cache and self.enable_cache:
            cached_score = self._get_from_cache(cache_key)
            if cached_score:
                logger.debug(f"从缓存获取 {stock_code} 评分")
                return cached_score

        try:
            # 构造请求数据
            # 注意：API期望的格式是 {"codes": ["600483"], "model_type": "sentiment"}
            request_data = {
                "codes": [stock_code],  # 必须是数组格式
                "model_type": "v2"  # 使用默认模型类型
            }

            # 注意：当前API不支持这些参数，它们被忽略
            # if current_price is not None:
            #     request_data["current_price"] = current_price
            # if holding_days is not None:
            #     request_data["holding_days"] = holding_days
            # if profit_loss_ratio is not None:
            #     request_data["profit_loss_ratio"] = profit_loss_ratio

            logger.debug(f"请求模型评分: {request_data}")

            # 发起请求
            response = self.session.post(
                self.api_url,
                json=request_data,
                timeout=self.timeout
            )
            response.raise_for_status()

            # 解析响应
            result = response.json()
            model_score = self._parse_response(result, stock_code)

            if model_score:
                # 缓存结果
                if self.enable_cache:
                    self._save_to_cache(cache_key, model_score)

                logger.info(
                    f"成功获取 {stock_code} 评分: {model_score.score:.2f} "
                    f"({model_score.recommendation}, 置信度: {model_score.confidence:.2%})"
                )
                return model_score
            else:
                logger.warning(f"解析 {stock_code} 评分失败")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"请求 {stock_code} 评分超时")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"请求 {stock_code} 评分失败: {e}")
            return None
        except Exception as e:
            logger.error(f"获取 {stock_code} 评分异常: {e}", exc_info=True)
            return None

    def get_batch_scores(
        self,
        stock_codes: List[str],
        positions_data: Optional[Dict[str, Dict]] = None,
        use_cache: bool = True
    ) -> Dict[str, Optional[ModelScore]]:
        """
        批量获取股票评分

        Args:
            stock_codes: 股票代码列表
            positions_data: 持仓数据字典 {code: {current_price, holding_days, profit_loss_ratio}}
            use_cache: 是否使用缓存

        Returns:
            {股票代码: ModelScore对象} 字典
        """
        result = {}

        for code in stock_codes:
            # 获取该股票的持仓数据
            position_info = positions_data.get(code, {}) if positions_data else {}

            current_price = position_info.get("current_price")
            holding_days = position_info.get("holding_days")
            profit_loss_ratio = position_info.get("profit_loss_ratio")

            # 获取评分
            score = self.get_score(
                stock_code=code,
                current_price=current_price,
                holding_days=holding_days,
                profit_loss_ratio=profit_loss_ratio,
                use_cache=use_cache
            )

            result[code] = score

            # 避免请求过快
            if score:
                time.sleep(0.1)

        logger.info(f"批量获取 {len(stock_codes)} 只股票评分完成")
        return result

    def _parse_response(self, response_data: Dict, stock_code: str) -> Optional[ModelScore]:
        """
        解析模型API响应

        实际API响应格式：
        {
            "result": [
                {
                    "code": "600483",
                    "total_score": 85.6,
                    "limit_up_prob": 0.75,
                    "downside_risk_prob": 0.25,
                    "chanlun_risk_prob": 0.20,
                    "short_term_risk": 0.15
                }
            ]
        }

        Args:
            response_data: API响应数据
            stock_code: 股票代码

        Returns:
            ModelScore对象或None
        """
        try:
            # 提取result数组
            result_list = response_data.get("result", [])
            if not result_list:
                logger.warning(f"{stock_code} 评分结果为空")
                return None

            # 找到对应股票代码的结果
            stock_result = None
            for item in result_list:
                # 处理股票代码格式（可能是字符串或整数）
                item_code = str(item.get("code", "")).zfill(6)
                if item_code == stock_code or item_code == stock_code.lstrip("0"):
                    stock_result = item
                    break

            if not stock_result:
                logger.warning(f"未找到 {stock_code} 的评分结果")
                return None

            # 提取total_score作为主评分
            score = float(stock_result.get("total_score", 0))

            # 根据评分推导推荐操作
            recommendation = get_decision_level(score)

            # 使用limit_up_prob作为置信度
            confidence = float(stock_result.get("limit_up_prob", 0.5))

            # 提取其他因子
            factors = {
                "limit_up_prob": float(stock_result.get("limit_up_prob", 0)),
                "downside_risk_prob": float(stock_result.get("downside_risk_prob", 0)),
                "chanlun_risk_prob": float(stock_result.get("chanlun_risk_prob", 0)),
                "short_term_risk": float(stock_result.get("short_term_risk", 0))
            }

            # 创建ModelScore对象
            model_score = ModelScore(
                stock_code=stock_code,
                score=score,
                recommendation=recommendation,
                confidence=confidence,
                factors=factors,
                timestamp=datetime.now()
            )

            return model_score

        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"解析 {stock_code} 评分响应失败: {e}")
            logger.debug(f"响应数据: {response_data}")
            return None

    def _generate_cache_key(
        self,
        stock_code: str,
        current_price: Optional[float],
        holding_days: Optional[int],
        profit_loss_ratio: Optional[float]
    ) -> str:
        """生成缓存键"""
        parts = [stock_code]
        if current_price is not None:
            parts.append(f"p{current_price:.2f}")
        if holding_days is not None:
            parts.append(f"d{holding_days}")
        if profit_loss_ratio is not None:
            parts.append(f"r{profit_loss_ratio:.4f}")
        return "_".join(parts)

    def _get_from_cache(self, cache_key: str) -> Optional[ModelScore]:
        """从缓存获取评分"""
        if cache_key in self._cache:
            model_score, cache_time = self._cache[cache_key]
            # 检查缓存是否过期
            if datetime.now() - cache_time < timedelta(seconds=self.cache_ttl):
                return model_score
            else:
                # 删除过期缓存
                del self._cache[cache_key]
        return None

    def _save_to_cache(self, cache_key: str, model_score: ModelScore) -> None:
        """保存评分到缓存"""
        self._cache[cache_key] = (model_score, datetime.now())

    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        logger.info("模型评分缓存已清空")

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

    def health_check(self) -> bool:
        """
        健康检查 - 测试模型API是否可用

        Returns:
            bool: API是否可用
        """
        try:
            # 发送测试请求
            test_data = {
                "stock_code": "000001",
                "current_price": 10.0
            }

            response = self.session.post(
                self.api_url,
                json=test_data,
                timeout=5
            )

            # 检查状态码
            if response.status_code == 200:
                logger.info("模型API健康检查通过")
                return True
            else:
                logger.warning(f"模型API健康检查失败: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"模型API健康检查异常: {e}")
            return False


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
    client = ModelClient()

    # 健康检查
    print("\n=== 模型API健康检查 ===")
    is_healthy = client.health_check()
    print(f"API状态: {'正常' if is_healthy else '异常'}")

    if not is_healthy:
        print("警告: 模型API不可用，以下测试将使用模拟数据")

        # 模拟评分数据用于测试
        class MockModelClient(ModelClient):
            def get_score(self, stock_code, **kwargs):
                """模拟返回评分"""
                import random
                score = random.uniform(20, 90)
                return ModelScore(
                    stock_code=stock_code,
                    score=score,
                    recommendation=get_decision_level(score),
                    confidence=random.uniform(0.6, 0.95),
                    factors={
                        "technical": random.uniform(0, 100),
                        "fundamental": random.uniform(0, 100),
                        "sentiment": random.uniform(0, 100)
                    },
                    timestamp=datetime.now()
                )

        client = MockModelClient()

    # 测试单个股票评分
    print("\n=== 测试单个股票评分 ===")
    score = client.get_score(
        stock_code="600483",
        current_price=24.5,
        holding_days=10,
        profit_loss_ratio=-0.05
    )

    if score:
        print(f"股票代码: {score.stock_code}")
        print(f"综合评分: {score.score:.2f}")
        print(f"推荐操作: {score.recommendation}")
        print(f"置信度: {score.confidence:.2%}")
        print(f"因子得分: {score.factors}")
        print(f"强烈卖出信号: {score.is_strong_sell_signal()}")
        print(f"卖出信号: {score.is_sell_signal()}")

    # 测试批量评分
    print("\n=== 测试批量评分 ===")
    codes = ["600483", "603993", "000001"]
    positions_data = {
        "600483": {"current_price": 24.5, "holding_days": 10, "profit_loss_ratio": -0.05},
        "603993": {"current_price": 6.8, "holding_days": 25, "profit_loss_ratio": 0.03},
        "000001": {"current_price": 10.5, "holding_days": 5, "profit_loss_ratio": 0.10}
    }

    batch_scores = client.get_batch_scores(codes, positions_data)

    for code, score in batch_scores.items():
        if score:
            print(f"{code}: {score.score:.2f} ({score.recommendation}) - 置信度: {score.confidence:.2%}")
        else:
            print(f"{code}: 获取失败")

    # 测试缓存
    print("\n=== 测试缓存 ===")
    print("缓存统计:", client.get_cache_stats())

    # 再次查询（应该命中缓存）
    print("\n再次查询（使用缓存）...")
    score2 = client.get_score("600483", current_price=24.5, use_cache=True)
    if score2:
        print(f"缓存评分: {score2.score:.2f}")

    print("\n缓存统计:", client.get_cache_stats())
