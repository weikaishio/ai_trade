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
        MODEL_APIS,
        MODEL_FUSION_CONFIG,
        get_decision_level
    )
    from .model_fusion import (
        ModelFusionEngine,
        FusionResult,
        ModelType,
        ModelScore as FusionModelScore
    )
except ImportError:
    from config_quant import (
        MODEL_API_URL,
        MODEL_API_TIMEOUT,
        MODEL_API_RETRY,
        CACHE_ENABLED,
        CACHE_TTL,
        MODEL_APIS,
        MODEL_FUSION_CONFIG,
        get_decision_level
    )
    from model_fusion import (
        ModelFusionEngine,
        FusionResult,
        ModelType,
        ModelScore as FusionModelScore
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
        cache_ttl: int = CACHE_TTL,
        enable_fusion: bool = None
    ):
        """
        初始化模型客户端

        Args:
            api_url: 模型API地址
            enable_cache: 是否启用缓存
            cache_ttl: 缓存有效期（秒）
            enable_fusion: 是否启用模型融合（None则使用配置）
        """
        self.api_url = api_url
        self.timeout = MODEL_API_TIMEOUT
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[ModelScore, datetime]] = {}
        self._fusion_cache: Dict[str, Tuple[FusionResult, datetime]] = {}

        # 模型融合配置
        self.fusion_config = MODEL_FUSION_CONFIG
        self.enable_fusion = (
            enable_fusion if enable_fusion is not None
            else self.fusion_config.get("enable_fusion", True)
        )

        # 创建融合引擎
        if self.enable_fusion:
            self.fusion_engine = ModelFusionEngine(self.fusion_config)
            logger.info("模型融合已启用")
        else:
            self.fusion_engine = None
            logger.info("模型融合已禁用，使用v2单模型")

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
        获取股票综合评分（支持融合评分，保持向后兼容）

        Args:
            stock_code: 股票代码
            current_price: 当前价格（可选）
            holding_days: 持仓天数（可选）
            profit_loss_ratio: 盈亏比例（可选）
            use_cache: 是否使用缓存

        Returns:
            ModelScore对象，失败返回None
        """
        # 如果启用融合，使用融合评分
        if self.enable_fusion:
            fusion_result = self.get_fusion_score(stock_code, use_cache)
            if fusion_result:
                # 转换为旧格式 ModelScore
                return self._convert_fusion_to_model_score(
                    stock_code, fusion_result
                )
            else:
                logger.warning(f"融合评分失败，尝试v2单模型: {stock_code}")
                # 降级尝试v2单模型
                return self._get_v2_legacy_score(stock_code, use_cache)
        else:
            # 未启用融合，使用原有逻辑（v2单模型）
            return self._get_v2_legacy_score(stock_code, use_cache)

    def _get_v2_legacy_score(
        self,
        stock_code: str,
        use_cache: bool = True
    ) -> Optional[ModelScore]:
        """
        原有的v2单模型评分方法（保持向后兼容）

        Args:
            stock_code: 股票代码
            use_cache: 是否使用缓存

        Returns:
            ModelScore对象或None
        """
        # 检查缓存
        cache_key = f"legacy_{stock_code}"

        if use_cache and self.enable_cache:
            cached_score = self._get_from_cache(cache_key)
            if cached_score:
                logger.debug(f"从缓存获取 {stock_code} v2评分")
                return cached_score

        try:
            # 构造请求数据
            request_data = {
                "codes": [stock_code],
                "model_type": "v2"
            }

            logger.debug(f"请求v2模型评分: {request_data}")

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
                    f"成功获取 {stock_code} v2评分: {model_score.score:.2f} "
                    f"({model_score.recommendation}, 置信度: {model_score.confidence:.2%})"
                )
                return model_score
            else:
                logger.warning(f"解析 {stock_code} v2评分失败")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"请求 {stock_code} v2评分超时")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"请求 {stock_code} v2评分失败: {e}")
            return None
        except Exception as e:
            logger.error(f"获取 {stock_code} v2评分异常: {e}", exc_info=True)
            return None

    def _convert_fusion_to_model_score(
        self,
        stock_code: str,
        fusion_result: FusionResult
    ) -> ModelScore:
        """
        将融合结果转换为旧格式 ModelScore（向后兼容）

        Args:
            stock_code: 股票代码
            fusion_result: 融合结果

        Returns:
            ModelScore对象
        """
        # 提取各模型评分
        v2_score = fusion_result.model_scores.get(ModelType.V2)
        sentiment_score = fusion_result.model_scores.get(ModelType.SENTIMENT)
        improved_score = fusion_result.model_scores.get(ModelType.IMPROVED)

        # 构建因子字典
        factors = {
            "v2_score": v2_score.score if v2_score else 0.0,
            "sentiment_score": sentiment_score.score if sentiment_score else 0.0,
            "improved_score": improved_score.score if improved_score else 0.0,
            "consistency": fusion_result.consistency,
            "strategy": fusion_result.strategy_name,
            "passed_filter": fusion_result.passed_filter,
            "filter_details": fusion_result.filter_details
        }

        # 如果有原始数据，也添加进去
        if v2_score:
            factors.update({
                "limit_up_prob": v2_score.raw_data.get("limit_up_prob", 0),
                "downside_risk_prob": v2_score.raw_data.get("downside_risk_prob", 0),
                "chanlun_risk_prob": v2_score.raw_data.get("chanlun_risk_prob", 0),
                "short_term_risk": v2_score.raw_data.get("short_term_risk", 0)
            })

        # 创建旧格式 ModelScore
        model_score = ModelScore(
            stock_code=stock_code,
            score=fusion_result.total_score,  # 0-100范围
            recommendation=fusion_result.recommendation,
            confidence=fusion_result.consistency,  # 使用一致性作为置信度
            factors=factors,
            timestamp=datetime.now()
        )

        return model_score

    def get_batch_scores(
        self,
        stock_codes: List[str],
        positions_data: Optional[Dict[str, Dict]] = None,
        use_cache: bool = True,
        use_batch_api: Optional[bool] = None
    ) -> Dict[str, Optional[ModelScore]]:
        """
        批量获取股票评分（支持批量API优化）

        Args:
            stock_codes: 股票代码列表
            positions_data: 持仓数据字典 {code: {current_price, holding_days, profit_loss_ratio}}
            use_cache: 是否使用缓存
            use_batch_api: 是否使用批量API（None则使用配置）

        Returns:
            {股票代码: ModelScore对象} 字典
        """
        # 确定是否使用批量API
        if use_batch_api is None:
            use_batch_api = self.fusion_config.get(
                "batch_processing", {}
            ).get("enabled", True)

        if use_batch_api and self.enable_fusion:
            # 使用批量API模式（性能优化）
            logger.info(f"使用批量API模式获取 {len(stock_codes)} 只股票评分")

            fusion_results = self.get_batch_fusion_scores(
                stock_codes,
                use_cache=use_cache
            )

            # 转换为ModelScore格式（兼容性）
            result = {}
            for code, fusion_result in fusion_results.items():
                if fusion_result:
                    result[code] = self._convert_fusion_to_model_score(
                        code,
                        fusion_result
                    )
                else:
                    result[code] = None

            logger.info(
                f"批量API模式完成: "
                f"{len([r for r in result.values() if r])}/{len(stock_codes)} 只股票成功"
            )

            return result

        else:
            # 原有逐个调用模式（兼容性保留）
            logger.info(f"使用串行模式获取 {len(stock_codes)} 只股票评分")

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

            logger.info(f"串行模式完成: {len(stock_codes)} 只股票评分")
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

    def get_single_model_score(
        self,
        stock_code: str,
        model_type: str,
        use_cache: bool = True
    ) -> Optional[FusionModelScore]:
        """
        获取单个模型的评分

        Args:
            stock_code: 股票代码
            model_type: 模型类型 (v2, sentiment, improved_refined_v35)
            use_cache: 是否使用缓存

        Returns:
            FusionModelScore对象或None
        """
        # 检查缓存
        cache_key = f"{stock_code}_{model_type}"
        if use_cache and self.enable_cache:
            cached = self._get_single_model_from_cache(cache_key)
            if cached:
                logger.debug(f"从缓存获取 {stock_code} {model_type} 评分")
                return cached

        try:
            # 获取模型配置
            model_config = MODEL_APIS.get(model_type)
            if not model_config:
                logger.error(f"未知的模型类型: {model_type}")
                return None

            # 构造请求
            request_data = {
                "codes": [stock_code],
                "model_type": model_config["model_type"]
            }

            api_url = model_config["url"]
            timeout = model_config["timeout"]

            logger.debug(f"请求 {model_type} 模型评分: {request_data}")

            # 发起请求
            response = self.session.post(
                api_url,
                json=request_data,
                timeout=timeout
            )
            response.raise_for_status()

            # 解析响应
            result = response.json()
            result_list = result.get("result", [])

            if not result_list:
                logger.warning(f"{stock_code} {model_type} 评分结果为空")
                return None

            # 查找对应股票的结果
            stock_result = None
            for item in result_list:
                item_code = str(item.get("code", "")).zfill(6)
                if item_code == stock_code or item_code == stock_code.lstrip("0"):
                    stock_result = item
                    break

            if not stock_result:
                logger.warning(f"未找到 {stock_code} {model_type} 评分")
                return None

            # 提取评分（归一化到0-1）
            # total_score 范围是 0-100
            total_score = float(stock_result.get("total_score", 0))
            normalized_score = total_score / 100.0

            # 使用 limit_up_prob 作为置信度
            confidence = float(stock_result.get("limit_up_prob", 0.5))

            # 创建模型评分对象
            model_score = FusionModelScore(
                model_type=ModelType(model_type),
                score=normalized_score,
                confidence=confidence,
                raw_data=stock_result
            )

            # 缓存结果
            if self.enable_cache:
                self._save_single_model_to_cache(cache_key, model_score)

            logger.info(
                f"{model_type} 模型评分: {stock_code} = {total_score:.2f} "
                f"(归一化: {normalized_score:.3f}, 置信度: {confidence:.2%})"
            )

            return model_score

        except requests.exceptions.Timeout:
            logger.error(f"请求 {stock_code} {model_type} 评分超时")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"请求 {stock_code} {model_type} 评分失败: {e}")
            return None
        except Exception as e:
            logger.error(f"获取 {stock_code} {model_type} 评分异常: {e}", exc_info=True)
            return None

    def get_multi_model_scores(
        self,
        stock_code: str,
        model_types: Optional[List[str]] = None,
        use_cache: bool = True
    ) -> Dict[str, Optional[FusionModelScore]]:
        """
        获取多个模型的评分

        Args:
            stock_code: 股票代码
            model_types: 模型类型列表（None则从配置读取活动组合）
            use_cache: 是否使用缓存

        Returns:
            {模型类型: FusionModelScore对象} 字典
        """
        if model_types is None:
            # 从配置读取当前活动的模型组合
            active_combination = self.fusion_config.get("active_combination", "default")
            combinations = self.fusion_config.get("model_combinations", {})
            model_types = combinations.get(
                active_combination,
                ["v2", "sentiment", "improved_refined_v35"]  # 默认组合
            )

        results = {}
        for model_type in model_types:
            score = self.get_single_model_score(stock_code, model_type, use_cache)
            results[model_type] = score

        return results

    def get_fusion_score(
        self,
        stock_code: str,
        use_cache: bool = True
    ) -> Optional[FusionResult]:
        """
        获取融合后的综合评分

        Args:
            stock_code: 股票代码
            use_cache: 是否使用缓存

        Returns:
            FusionResult对象或None
        """
        # 如果未启用融合，降级到v2单模型
        if not self.enable_fusion:
            logger.debug(f"融合已禁用，使用v2单模型: {stock_code}")
            return self._get_v2_fallback_score(stock_code, use_cache)

        # 检查缓存
        cache_key = f"fusion_{stock_code}"
        if use_cache and self.enable_cache:
            cached = self._get_fusion_from_cache(cache_key)
            if cached:
                logger.debug(f"从缓存获取 {stock_code} 融合评分")
                return cached

        # 获取多模型评分（从配置读取模型组合）
        model_scores_dict = self.get_multi_model_scores(
            stock_code,
            model_types=None,  # None = 使用配置中的活动组合
            use_cache=use_cache
        )

        # 转换为 ModelType 键的字典
        fusion_scores = {}
        for model_type_str, score in model_scores_dict.items():
            if score:
                fusion_scores[ModelType(model_type_str)] = score

        # 检查最少模型数量
        min_required = self.fusion_config.get("min_models_required", 2)
        if len(fusion_scores) < min_required:
            logger.warning(
                f"{stock_code} 可用模型数量不足 ({len(fusion_scores)}/{min_required})"
            )

            # 降级处理
            if self.fusion_config.get("use_v2_only_fallback", True):
                logger.info(f"降级到v2单模型: {stock_code}")
                return self._get_v2_fallback_score(stock_code, use_cache)
            else:
                return None

        # 执行融合（传递股票代码用于日志）
        try:
            fusion_result = self.fusion_engine.fuse(fusion_scores, stock_code=stock_code)

            # 缓存结果
            if self.enable_cache:
                self._save_fusion_to_cache(cache_key, fusion_result)

            return fusion_result

        except Exception as e:
            logger.error(f"融合评分失败 {stock_code}: {e}", exc_info=True)

            # 降级处理
            if self.fusion_config.get("use_v2_only_fallback", True):
                logger.info(f"融合失败，降级到v2单模型: {stock_code}")
                return self._get_v2_fallback_score(stock_code, use_cache)
            else:
                return None

    def _get_v2_fallback_score(
        self,
        stock_code: str,
        use_cache: bool = True
    ) -> Optional[FusionResult]:
        """
        降级方案：使用v2单模型

        Args:
            stock_code: 股票代码
            use_cache: 是否使用缓存

        Returns:
            FusionResult对象或None（模拟融合结果格式）
        """
        v2_score = self.get_single_model_score(stock_code, "v2", use_cache)

        if not v2_score:
            return None

        # 构造模拟的融合结果
        model_scores = {ModelType.V2: v2_score}
        total_score = v2_score.score * 100

        fusion_result = FusionResult(
            final_score=v2_score.score,
            consistency=1.0,  # 单模型一致性为1
            strategy_name="v2单模型（降级）",
            model_scores=model_scores,
            total_score=total_score,
            recommendation=self._get_recommendation(total_score),
            passed_filter=True,  # 单模型不做筛选
            filter_details="v2单模型降级，跳过筛选"
        )

        return fusion_result

    def _get_recommendation(self, score: float) -> str:
        """根据评分获取推荐操作"""
        return get_decision_level(score)

    def _get_single_model_from_cache(
        self,
        cache_key: str
    ) -> Optional[FusionModelScore]:
        """从缓存获取单模型评分"""
        if cache_key in self._cache:
            # 复用旧缓存结构（需要转换）
            pass
        return None

    def _save_single_model_to_cache(
        self,
        cache_key: str,
        model_score: FusionModelScore
    ) -> None:
        """保存单模型评分到缓存（简化实现）"""
        pass

    def _get_fusion_from_cache(self, cache_key: str) -> Optional[FusionResult]:
        """从缓存获取融合评分"""
        if cache_key in self._fusion_cache:
            fusion_result, cache_time = self._fusion_cache[cache_key]
            if datetime.now() - cache_time < timedelta(seconds=self.cache_ttl):
                return fusion_result
            else:
                del self._fusion_cache[cache_key]
        return None

    def _save_fusion_to_cache(
        self,
        cache_key: str,
        fusion_result: FusionResult
    ) -> None:
        """保存融合评分到缓存"""
        self._fusion_cache[cache_key] = (fusion_result, datetime.now())

    def _call_batch_model_api(
        self,
        stock_codes: List[str],
        model_type: str
    ) -> Dict[str, Dict]:
        """
        批量调用模型API

        Args:
            stock_codes: 股票代码列表
            model_type: 模型类型 (v2, sentiment, improved_refined_v35)

        Returns:
            {股票代码: API返回数据} 字典
        """
        try:
            # 获取模型配置
            model_config = MODEL_APIS.get(model_type)
            if not model_config:
                logger.error(f"未找到模型配置: {model_type}")
                return {}

            # 构造批量请求
            request_data = {
                "codes": stock_codes,
                "model_type": model_config["model_type"]
            }

            logger.debug(
                f"批量请求 {model_type} 模型: {len(stock_codes)} 只股票"
            )

            # 发送请求
            response = self.session.post(
                model_config["url"],
                json=request_data,
                timeout=model_config["timeout"]
            )
            response.raise_for_status()

            # 解析响应
            result = response.json()
            result_list = result.get("result", [])

            if not result_list:
                logger.warning(f"批量请求 {model_type} 返回空结果")
                return {}

            # 构建代码->数据的映射
            result_dict = {}
            for item in result_list:
                code = str(item.get("code", "")).zfill(6)
                result_dict[code] = item

            logger.info(
                f"批量获取 {model_type} 评分成功: "
                f"{len(result_dict)}/{len(stock_codes)} 只股票"
            )

            return result_dict

        except requests.exceptions.Timeout:
            logger.error(f"批量调用 {model_type} 模型超时")
            return {}
        except requests.exceptions.RequestException as e:
            logger.error(f"批量调用 {model_type} 模型失败: {e}")
            return {}
        except Exception as e:
            logger.error(
                f"批量调用 {model_type} 模型异常: {e}",
                exc_info=True
            )
            return {}

    def get_batch_single_model_scores(
        self,
        stock_codes: List[str],
        model_type: str,
        batch_size: Optional[int] = None,
        use_cache: bool = True
    ) -> Dict[str, Optional[FusionModelScore]]:
        """
        批量获取单个模型的评分（性能优化）

        Args:
            stock_codes: 股票代码列表
            model_type: 模型类型 (v2, sentiment, improved_refined_v35)
            batch_size: 每批处理的股票数量（None则使用配置）
            use_cache: 是否使用缓存

        Returns:
            {股票代码: FusionModelScore对象} 字典
        """
        if batch_size is None:
            batch_size = self.fusion_config.get(
                "batch_processing", {}
            ).get("batch_size", 50)

        results = {}
        codes_to_fetch = []

        # 1. 检查缓存
        if use_cache and self.enable_cache:
            for code in stock_codes:
                cache_key = f"{code}_{model_type}"
                cached = self._get_single_model_from_cache(cache_key)
                if cached:
                    results[code] = cached
                    logger.debug(f"从缓存获取 {code} {model_type} 评分")
                else:
                    codes_to_fetch.append(code)
        else:
            codes_to_fetch = stock_codes

        # 2. 分批处理未缓存的股票
        if codes_to_fetch:
            # 分批
            for i in range(0, len(codes_to_fetch), batch_size):
                batch_codes = codes_to_fetch[i:i+batch_size]

                # 批量API调用
                batch_results = self._call_batch_model_api(
                    batch_codes,
                    model_type
                )

                # 3. 解析响应并创建模型评分对象
                for code in batch_codes:
                    stock_result = batch_results.get(code)

                    if not stock_result:
                        logger.warning(f"未找到 {code} {model_type} 评分")
                        results[code] = None
                        continue

                    try:
                        # 提取评分（归一化到0-1）
                        total_score = float(stock_result.get("total_score", 0))
                        normalized_score = total_score / 100.0

                        # 使用 limit_up_prob 作为置信度
                        confidence = float(
                            stock_result.get("limit_up_prob", 0.5)
                        )

                        # 创建模型评分对象
                        model_score = FusionModelScore(
                            model_type=ModelType(model_type),
                            score=normalized_score,
                            confidence=confidence,
                            raw_data=stock_result
                        )

                        results[code] = model_score

                        # 4. 缓存结果
                        if self.enable_cache:
                            cache_key = f"{code}_{model_type}"
                            self._save_single_model_to_cache(
                                cache_key,
                                model_score
                            )

                    except (KeyError, ValueError, TypeError) as e:
                        logger.error(
                            f"解析 {code} {model_type} 评分失败: {e}"
                        )
                        results[code] = None

        logger.info(
            f"批量获取 {model_type} 模型评分完成: "
            f"{len([r for r in results.values() if r])}/{len(stock_codes)} 只股票成功"
        )

        return results

    def get_batch_fusion_scores(
        self,
        stock_codes: List[str],
        batch_size: Optional[int] = None,
        use_cache: bool = True
    ) -> Dict[str, Optional[FusionResult]]:
        """
        批量获取融合评分（性能优化）

        策略：
        1. 批量调用v2模型API（一次获取所有股票）
        2. 批量调用sentiment模型API
        3. 批量调用improved_refined_v35模型API
        4. 融合每只股票的结果

        性能提升：
        - 之前：N只股票 × 3个模型 × 17秒/次 = N×51秒
        - 之后：3个模型 × 17秒/次 = 51秒（不论N多大）
        - 提升：约N倍

        Args:
            stock_codes: 股票代码列表
            batch_size: 每批处理的股票数量（None则使用配置）
            use_cache: 是否使用缓存

        Returns:
            {股票代码: FusionResult对象} 字典
        """
        if batch_size is None:
            batch_size = self.fusion_config.get(
                "batch_processing", {}
            ).get("batch_size", 50)

        results = {}
        codes_to_fetch = []

        # 1. 检查缓存
        if use_cache and self.enable_cache:
            for code in stock_codes:
                cache_key = f"fusion_{code}"
                cached = self._get_fusion_from_cache(cache_key)
                if cached:
                    results[code] = cached
                    logger.debug(f"从缓存获取 {code} 融合评分")
                else:
                    codes_to_fetch.append(code)
        else:
            codes_to_fetch = stock_codes

        if not codes_to_fetch:
            logger.info(f"所有股票均命中缓存: {len(stock_codes)} 只")
            return results

        # 2. 分批处理
        for i in range(0, len(codes_to_fetch), batch_size):
            batch_codes = codes_to_fetch[i:i+batch_size]
            logger.info(
                f"批量融合评分: 批次 {i//batch_size + 1}, "
                f"{len(batch_codes)} 只股票"
            )

            # 3. 批量获取模型评分（从配置读取模型组合）
            active_combination = self.fusion_config.get("active_combination", "default")
            combinations = self.fusion_config.get("model_combinations", {})
            model_types = combinations.get(
                active_combination,
                ["v2", "sentiment", "improved_refined_v35"]
            )
            logger.info(f"使用模型组合 '{active_combination}': {model_types}")
            all_model_scores = {}

            for model_type in model_types:
                batch_scores = self.get_batch_single_model_scores(
                    batch_codes,
                    model_type,
                    batch_size=len(batch_codes),  # 不再分批
                    use_cache=use_cache
                )
                all_model_scores[model_type] = batch_scores

            # 4. 融合每只股票的结果
            for code in batch_codes:
                # 收集该股票的所有模型评分
                fusion_scores = {}

                for model_type in model_types:
                    score = all_model_scores[model_type].get(code)
                    if score:
                        fusion_scores[ModelType(model_type)] = score

                # 检查最少模型数量
                min_required = self.fusion_config.get("min_models_required", 2)
                if len(fusion_scores) < min_required:
                    logger.warning(
                        f"{code} 可用模型数量不足 "
                        f"({len(fusion_scores)}/{min_required})"
                    )

                    # 降级处理
                    if self.fusion_config.get("use_v2_only_fallback", True):
                        logger.info(f"降级到v2单模型: {code}")
                        fallback_result = self._get_v2_fallback_score(
                            code,
                            use_cache=False  # 已经尝试过缓存了
                        )
                        results[code] = fallback_result
                    else:
                        results[code] = None
                    continue

                # 执行融合（传递股票代码用于日志）
                try:
                    if not self.fusion_engine:
                        logger.error("融合引擎未初始化")
                        results[code] = None
                        continue

                    fusion_result = self.fusion_engine.fuse(fusion_scores, stock_code=code)

                    # 缓存结果
                    if self.enable_cache:
                        cache_key = f"fusion_{code}"
                        self._save_fusion_to_cache(cache_key, fusion_result)

                    results[code] = fusion_result

                except Exception as e:
                    logger.error(f"融合评分失败 {code}: {e}", exc_info=True)

                    # 降级处理
                    if self.fusion_config.get("use_v2_only_fallback", True):
                        logger.info(f"融合失败，降级到v2单模型: {code}")
                        fallback_result = self._get_v2_fallback_score(
                            code,
                            use_cache=False
                        )
                        results[code] = fallback_result
                    else:
                        results[code] = None

        success_count = len([r for r in results.values() if r])
        logger.info(
            f"批量融合评分完成: {success_count}/{len(stock_codes)} 只股票成功"
        )

        return results


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
