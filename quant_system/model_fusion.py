"""
多模型融合引擎模块

实现三模型（v2、improved_refined_v35、sentiment）的融合评分策略，
参考 Go 版本的分层筛选和动态权重计算。
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """模型类型枚举"""
    V2 = "v2"
    SENTIMENT = "sentiment"
    IMPROVED_REFINED = "improved_refined"  # 新增: improved基础版
    IMPROVED_V35 = "improved_refined_v35"  # 重命名: improved v35版

    # 为了向后兼容，保留IMPROVED别名
    IMPROVED = "improved_refined_v35"


@dataclass
class ModelScore:
    """单个模型的评分结果"""
    model_type: ModelType
    score: float  # 0-1范围，归一化评分
    confidence: float  # 置信度 0-1
    raw_data: Dict  # 原始API返回数据

    def __post_init__(self):
        """验证评分范围"""
        if not 0 <= self.score <= 1:
            logger.warning(
                f"{self.model_type.value} score {self.score} out of range, clamping to [0,1]"
            )
            self.score = max(0.0, min(1.0, self.score))


@dataclass
class FusionResult:
    """融合后的综合评分结果"""
    final_score: float  # 融合后的综合评分 0-1
    consistency: float  # 模型一致性 0-1
    strategy_name: str  # 触发的策略名称
    model_scores: Dict[ModelType, ModelScore]  # 各模型评分
    total_score: float  # 0-100范围（兼容旧版）
    recommendation: str  # 推荐操作
    passed_filter: bool  # 是否通过分层筛选
    filter_details: str  # 筛选详情

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "final_score": self.final_score,
            "consistency": self.consistency,
            "strategy_name": self.strategy_name,
            "total_score": self.total_score,
            "recommendation": self.recommendation,
            "passed_filter": self.passed_filter,
            "filter_details": self.filter_details,
            "model_scores": {
                model_type.value: {
                    "score": score.score,
                    "confidence": score.confidence
                }
                for model_type, score in self.model_scores.items()
            }
        }


class ModelFusionEngine:
    """
    多模型融合引擎

    实现三模型融合策略：
    1. 计算模型一致性（基于标准差）
    2. 动态权重计算综合评分
    3. 分层策略筛选
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化融合引擎

        Args:
            config: 融合配置字典，包含阈值和权重配置
        """
        self.config = config or self._get_default_config()

        # 提取阈值配置
        thresholds = self.config.get("strategy_thresholds", {})
        self.threshold_short_term_high = thresholds.get("short_term_high", 0.5)
        self.threshold_v2_good = thresholds.get("v2_good", 0.5)
        self.threshold_short_term_mid = thresholds.get("short_term_mid", 0.45)
        self.threshold_v2_excellent = thresholds.get("v2_excellent", 0.6)
        self.threshold_v2_superior = thresholds.get("v2_superior", 0.7)
        self.threshold_short_term_ok = thresholds.get("short_term_ok", 0.4)
        self.threshold_high_consistency = thresholds.get("high_consistency", 0.7)
        self.threshold_final_score_high = thresholds.get("final_score_high", 0.4)

        # 提取权重配置
        self.dynamic_weights = self.config.get("dynamic_weights", {})

        logger.info("模型融合引擎初始化完成")

    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "strategy_thresholds": {
                "short_term_high": 0.5,
                "v2_good": 0.5,
                "short_term_mid": 0.45,
                "v2_excellent": 0.6,
                "v2_superior": 0.7,
                "short_term_ok": 0.4,
                "high_consistency": 0.7,
                "final_score_high": 0.4
            },
            "dynamic_weights": {
                "high_consistency": {"v2": 0.4, "sentiment": 0.3, "improved": 0.3},
                "mid_consistency": {"v2": 0.35, "sentiment": 0.35, "improved": 0.3},
                "low_consistency": {"v2": 0.33, "sentiment": 0.33, "improved": 0.34}
            }
        }

    def calculate_consistency(self, scores: List[float]) -> float:
        """
        计算模型一致性（基于标准差）

        Args:
            scores: 模型评分列表（已归一化到0-1）

        Returns:
            一致性 0-1，越接近1表示越一致
        """
        if len(scores) < 2:
            return 1.0  # 单模型默认完全一致

        # 计算均值
        mean = sum(scores) / len(scores)

        # 计算方差（简化版，不开平方）
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)

        # 标准差越小，一致性越高
        # 标准差0.1 → 一致性约0.8
        # 标准差0.3 → 一致性约0.4
        consistency = 1.0 - variance * 2.0

        # 限制在 [0, 1] 范围
        consistency = max(0.0, min(1.0, consistency))

        logger.debug(
            f"一致性计算: scores={scores}, mean={mean:.3f}, "
            f"variance={variance:.3f}, consistency={consistency:.3f}"
        )

        return consistency

    def calculate_final_score(
        self,
        sentiment: float,
        improved: float,
        v2_score: float,
        consistency: float
    ) -> float:
        """
        根据一致性动态计算综合评分

        Args:
            sentiment: 情绪模型评分 0-1
            improved: 技术面模型评分 0-1
            v2_score: V2模型评分 0-1
            consistency: 模型一致性 0-1

        Returns:
            综合评分 0-1
        """
        # 根据一致性选择权重策略
        if consistency > 0.8:
            # 高度一致: V2权重加大（关注中长期收益）
            weights = self.dynamic_weights.get("high_consistency", {})
            w_sentiment = weights.get("sentiment", 0.3)
            w_improved = weights.get("improved", 0.3)
            w_v2 = weights.get("v2", 0.4)
            base_score = sentiment * w_sentiment + improved * w_improved + v2_score * w_v2
            logger.debug(
                f"高度一致策略: weights=[S:{w_sentiment}, I:{w_improved}, V2:{w_v2}]"
            )

        elif consistency > 0.6:
            # 中等一致: 均衡权重
            weights = self.dynamic_weights.get("mid_consistency", {})
            w_sentiment = weights.get("sentiment", 0.35)
            w_improved = weights.get("improved", 0.35)
            w_v2 = weights.get("v2", 0.3)
            base_score = sentiment * w_sentiment + improved * w_improved + v2_score * w_v2
            logger.debug(
                f"中等一致策略: weights=[S:{w_sentiment}, I:{w_improved}, V2:{w_v2}]"
            )

        else:
            # 分歧较大: 平均值（避免异常值影响）
            base_score = (sentiment + improved + v2_score) / 3
            logger.debug("低一致性策略: 使用平均值")

        # 一致性加成: 模型越一致，越可信
        final_score = base_score * (0.8 + 0.2 * consistency)

        logger.debug(
            f"综合评分计算: base={base_score:.3f}, consistency_bonus={consistency:.3f}, "
            f"final={final_score:.3f}"
        )

        return final_score

    def apply_filter_strategies(
        self,
        sentiment: float,
        improved: float,
        v2_score: float,
        final_score: float,
        consistency: float
    ) -> Tuple[bool, str]:
        """
        应用分层筛选策略

        四个策略（满足任一即通过）：
        1. 任一短期模型高置信(>=0.5) + V2不太差(>=0.5)
        2. 双短期模型中等(>=0.45) + V2优秀(>=0.6)
        3. V2极优(>=0.7) + 任一短期不太差(>=0.4)
        4. 三模型高度一致(>=0.7) + 综合评分高(>=0.4)

        Args:
            sentiment: 情绪模型评分 0-1
            improved: 技术面模型评分 0-1
            v2_score: V2模型评分 0-1
            final_score: 综合评分 0-1
            consistency: 模型一致性 0-1

        Returns:
            (是否通过, 触发的策略名称)
        """
        # 策略1: 任一短期模型高置信 + V2不太差
        if ((sentiment >= self.threshold_short_term_high or
             improved >= self.threshold_short_term_high) and
            v2_score >= self.threshold_v2_good):
            return (
                True,
                f"短期模型高置信+V2良好 (S:{sentiment:.2f}/I:{improved:.2f}/V2:{v2_score:.2f})"
            )

        # 策略2: 双短期模型中等 + V2优秀
        if ((sentiment >= self.threshold_short_term_mid and
             improved >= self.threshold_short_term_mid) and
            v2_score >= self.threshold_v2_excellent):
            return (
                True,
                f"双短期中等+V2优秀 (S:{sentiment:.2f}/I:{improved:.2f}/V2:{v2_score:.2f})"
            )

        # 策略3: V2极优 + 任一短期模型不太差
        if (v2_score >= self.threshold_v2_superior and
            (sentiment >= self.threshold_short_term_ok or
             improved >= self.threshold_short_term_ok)):
            return (
                True,
                f"V2极优+短期不差 (V2:{v2_score:.2f}/S:{sentiment:.2f}/I:{improved:.2f})"
            )

        # 策略4: 三模型高度一致且综合评分高
        if (consistency >= self.threshold_high_consistency and
            final_score >= self.threshold_final_score_high):
            return (
                True,
                f"三模型高度一致 (一致性:{consistency:.2f}/综合:{final_score:.2f})"
            )

        # 所有策略都不满足
        return (
            False,
            f"未通过筛选 (S:{sentiment:.2f}/I:{improved:.2f}/V2:{v2_score:.2f}/"
            f"一致性:{consistency:.2f}/综合:{final_score:.2f})"
        )

    def fuse(
        self,
        model_scores: Dict[ModelType, ModelScore],
        stock_code: Optional[str] = None
    ) -> FusionResult:
        """
        执行模型融合（灵活支持不同模型组合）

        Args:
            model_scores: 各模型的评分字典
            stock_code: 股票代码（可选，用于日志）

        Returns:
            FusionResult融合结果对象
        """
        # 构建日志前缀
        log_prefix = f"[{stock_code}] " if stock_code else ""

        # 灵活提取各模型评分（支持不同组合）
        # V2模型（必需）
        v2_score_obj = model_scores.get(ModelType.V2)
        v2_score = v2_score_obj.score if v2_score_obj else 0.0

        # Sentiment模型（可选）
        sentiment_score = model_scores.get(ModelType.SENTIMENT)
        sentiment = sentiment_score.score if sentiment_score else 0.0

        # Improved模型组（优先使用v35，其次refined，最后IMPROVED别名）
        improved_score = (
            model_scores.get(ModelType.IMPROVED_V35) or
            model_scores.get(ModelType.IMPROVED_REFINED) or
            model_scores.get(ModelType.IMPROVED)
        )
        improved = improved_score.score if improved_score else 0.0

        # 仅在确实缺少所有improved变体时才警告
        has_any_improved = any([
            model_scores.get(ModelType.IMPROVED_V35),
            model_scores.get(ModelType.IMPROVED_REFINED),
            model_scores.get(ModelType.IMPROVED)
        ])

        # 记录缺失的关键模型（仅当少于2个模型时才警告）
        available_count = sum([
            v2_score_obj is not None,
            sentiment_score is not None,
            has_any_improved
        ])

        if available_count < 2:
            missing = []
            if not v2_score_obj:
                missing.append("v2")
            if not sentiment_score:
                missing.append("sentiment")
            if not has_any_improved:
                missing.append("improved系列")
            logger.warning(f"{log_prefix}模型数量不足 ({available_count}/3): 缺失 {', '.join(missing)}")

        # 计算模型一致性
        available_scores = [
            s.score for s in model_scores.values() if s is not None
        ]
        consistency = self.calculate_consistency(available_scores)

        # 计算综合评分
        final_score = self.calculate_final_score(
            sentiment, improved, v2_score, consistency
        )

        # 应用分层筛选策略
        passed, strategy_name = self.apply_filter_strategies(
            sentiment, improved, v2_score, final_score, consistency
        )

        # 转换为0-100范围（兼容旧版）
        total_score = final_score * 100

        # 根据评分推导推荐操作
        recommendation = self._get_recommendation(total_score)

        # 构建融合结果
        fusion_result = FusionResult(
            final_score=final_score,
            consistency=consistency,
            strategy_name=strategy_name,
            model_scores=model_scores,
            total_score=total_score,
            recommendation=recommendation,
            passed_filter=passed,
            filter_details=strategy_name
        )

        logger.info(
            f"{log_prefix}融合结果: 评分={total_score:.2f}, 一致性={consistency:.2f}, "
            f"策略={strategy_name} (S:{sentiment:.3f}/I:{improved:.3f}/V2:{v2_score:.3f}), "
            f"通过={passed}"
        )

        return fusion_result

    def _get_recommendation(self, score: float) -> str:
        """
        根据评分获取推荐操作

        Args:
            score: 评分 0-100

        Returns:
            推荐操作字符串
        """
        if score < 30:
            return "strong_sell"
        elif score < 40:
            return "sell"
        elif score < 60:
            return "hold"
        elif score < 80:
            return "buy"
        else:
            return "strong_buy"


# ============================================================================
# 使用示例和测试
# ============================================================================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建融合引擎
    engine = ModelFusionEngine()

    print("\n=== 测试1: 三模型高度一致 ===")
    scores1 = {
        ModelType.SENTIMENT: ModelScore(
            model_type=ModelType.SENTIMENT,
            score=0.75,
            confidence=0.85,
            raw_data={}
        ),
        ModelType.IMPROVED: ModelScore(
            model_type=ModelType.IMPROVED,
            score=0.78,
            confidence=0.82,
            raw_data={}
        ),
        ModelType.V2: ModelScore(
            model_type=ModelType.V2,
            score=0.72,
            confidence=0.88,
            raw_data={}
        )
    }
    result1 = engine.fuse(scores1)
    print(f"结果: {result1.to_dict()}")

    print("\n=== 测试2: 短期高置信+V2良好 ===")
    scores2 = {
        ModelType.SENTIMENT: ModelScore(
            model_type=ModelType.SENTIMENT,
            score=0.65,
            confidence=0.75,
            raw_data={}
        ),
        ModelType.IMPROVED: ModelScore(
            model_type=ModelType.IMPROVED,
            score=0.42,
            confidence=0.68,
            raw_data={}
        ),
        ModelType.V2: ModelScore(
            model_type=ModelType.V2,
            score=0.55,
            confidence=0.70,
            raw_data={}
        )
    }
    result2 = engine.fuse(scores2)
    print(f"结果: {result2.to_dict()}")

    print("\n=== 测试3: 模型分歧较大 ===")
    scores3 = {
        ModelType.SENTIMENT: ModelScore(
            model_type=ModelType.SENTIMENT,
            score=0.35,
            confidence=0.60,
            raw_data={}
        ),
        ModelType.IMPROVED: ModelScore(
            model_type=ModelType.IMPROVED,
            score=0.82,
            confidence=0.85,
            raw_data={}
        ),
        ModelType.V2: ModelScore(
            model_type=ModelType.V2,
            score=0.45,
            confidence=0.65,
            raw_data={}
        )
    }
    result3 = engine.fuse(scores3)
    print(f"结果: {result3.to_dict()}")

    print("\n=== 测试4: 缺失部分模型 ===")
    scores4 = {
        ModelType.SENTIMENT: ModelScore(
            model_type=ModelType.SENTIMENT,
            score=0.70,
            confidence=0.80,
            raw_data={}
        ),
        ModelType.V2: ModelScore(
            model_type=ModelType.V2,
            score=0.68,
            confidence=0.75,
            raw_data={}
        )
        # 缺失 IMPROVED 模型
    }
    result4 = engine.fuse(scores4)
    print(f"结果: {result4.to_dict()}")
