"""
智能选股模块

提供多维度股票筛选功能：
1. 基于深度学习模型评分选股
2. 技术指标筛选（量比、换手率、资金流）
3. 风险过滤（ST股、停牌股、涨跌停）
4. 优先级排序
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

try:
    from .market_data_client import MarketDataClient, StockData
    from .model_client import ModelClient, ModelScore
    from .config_quant import (
        BLACKLIST_STOCKS,
        ST_STOCK_PREFIX,
        BUY_STRATEGY_CONFIG,
        STOCK_SELECTION_CONFIG
    )
except ImportError:
    from market_data_client import MarketDataClient, StockData
    from model_client import ModelClient, ModelScore
    from config_quant import (
        BLACKLIST_STOCKS,
        ST_STOCK_PREFIX,
        BUY_STRATEGY_CONFIG,
        STOCK_SELECTION_CONFIG
    )

logger = logging.getLogger(__name__)


class StockType(Enum):
    """股票类型"""
    GROWTH = "成长股"        # 高增长潜力
    VALUE = "价值股"         # 低估值
    MOMENTUM = "动量股"      # 强势上涨
    TURNAROUND = "反转股"    # 超跌反弹


@dataclass
class CandidateStock:
    """候选股票"""
    code: str                           # 股票代码
    name: str                           # 股票名称
    score: float                        # 综合评分 (0-100)
    model_score: Optional[float] = None  # 模型评分
    technical_score: float = 0.0        # 技术指标评分
    fundamental_score: float = 0.0      # 基本面评分
    current_price: float = 0.0          # 当前价
    change_percent: float = 0.0         # 涨跌幅
    volume_ratio: float = 0.0           # 量比
    turnover_rate: float = 0.0          # 换手率
    pe_ratio: float = 0.0               # 市盈率
    market_cap: float = 0.0             # 流通市值（万）
    stock_type: Optional[StockType] = None  # 股票类型
    reasons: List[str] = field(default_factory=list)  # 选中理由
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "code": self.code,
            "name": self.name,
            "score": self.score,
            "model_score": self.model_score,
            "technical_score": self.technical_score,
            "current_price": self.current_price,
            "change_percent": self.change_percent,
            "volume_ratio": self.volume_ratio,
            "stock_type": self.stock_type.value if self.stock_type else None,
            "reasons": self.reasons
        }


class StockSelector:
    """
    智能选股器

    整合多维度数据源进行股票筛选和排序
    """

    def __init__(self):
        """初始化选股器"""
        self.market_client = MarketDataClient()
        self.model_client = ModelClient()
        self.config = BUY_STRATEGY_CONFIG

        logger.info("选股器初始化完成")

    def get_candidate_stocks(
        self,
        stock_pool: Optional[List[str]] = None,
        max_count: int = 20
    ) -> List[CandidateStock]:
        """
        获取候选股票池

        Args:
            stock_pool: 股票池（如果为None则使用默认股票池）
            max_count: 最大返回数量

        Returns:
            候选股票列表（按评分排序）
        """
        logger.info(f"开始选股，目标数量: {max_count}")

        # 1. 获取股票池
        if stock_pool is None:
            stock_pool = self._get_default_stock_pool()

        logger.info(f"股票池规模: {len(stock_pool)} 只")

        # 2. 获取市场数据
        market_data_dict = self.market_client.get_batch_stock_data(stock_pool)

        # 3. 获取模型评分
        model_scores_dict = self._get_model_scores(stock_pool, market_data_dict)

        # 4. 构建候选股票列表
        candidates = []
        for code in stock_pool:
            market_data = market_data_dict.get(code)
            model_score = model_scores_dict.get(code)

            if not market_data:
                logger.debug(f"跳过 {code}: 无市场数据")
                continue

            candidate = self._build_candidate_stock(code, market_data, model_score)
            if candidate:
                candidates.append(candidate)

        logger.info(f"初步筛选: {len(candidates)} 只候选股票")

        # 5. 风险过滤
        candidates = self.filter_by_risk(candidates)
        logger.info(f"风险过滤后: {len(candidates)} 只候选股票")

        # 6. 质量筛选
        candidates = self._filter_by_quality(candidates)
        logger.info(f"质量筛选后: {len(candidates)} 只候选股票")

        # 7. 优先级排序
        candidates = self.rank_by_priority(candidates)

        # 8. 返回Top N
        top_candidates = candidates[:max_count]
        logger.info(f"最终筛选: {len(top_candidates)} 只股票")

        return top_candidates

    def _get_default_stock_pool(self) -> List[str]:
        """
        获取默认股票池

        使用近2年涨停次数排名靠前的股票池
        数据来源：近2年涨停次数统计（完整版）

        股票池特点：
        1. 高活跃度 - 近2年涨停次数>=21次
        2. 强势股为主 - 具有较强的上涨动能
        3. 适合短线交易 - 波动较大，机会较多

        注意：原始数据中的股票代码已全部转换为标准6位格式
        """
        # 近2年涨停次数>=21次的完整股票池（按原始数据顺序）
        # 格式：深圳股票补齐到6位（前面补0），上海股票保持原样
        default_pool = [
            # 原始数据完整转换
            "002052", "000908", "600289", "600165", "603389",
            "000609", "002289", "000506", "002808", "603007",
            "002713", "603377", "000691", "603959", "603559",
            "002141", "002742", "603828", "603843", "002656",
            "002822", "002569", "002490", "600234", "000615",
            "002650", "002693", "002868", "002199", "002717",
            "002816", "600381", "002217", "603879", "600696",
            "002305", "600589", "000004", "002058", "002951",
            "600421", "002005", "002309", "600599", "603268",
            "002310", "002528", "000638", "000669", "000889",
            "603398", "000981", "002586", "600107", "002168",
            "002251", "002485", "600360", "600608", "603021",
            "002272", "600715", "000668", "000820", "603557",
            "000793", "002197", "002789", "600193", "000656",
            "002076", "600355", "603256", "603261", "603716",
            "603813", "002231", "002898", "002647", "002861",
            "600777", "603778", "002313", "600678", "001270",
            "002306", "002620", "002640", "600228", "600303",
            "603516", "603900", "000070", "000564", "000620",
            "002759", "600136", "603958", "605255", "000752",
            "000859", "002047", "002403", "002848", "600735",
            "600889", "603363", "603626", "605178", "000608",
            "002347", "002427", "002471", "002549", "002592",
            "002931", "002952", "600629", "603825", "000016",
            "000504", "002529", "002583", "600568", "600579",
            "600693", "000536", "000595", "000880", "001298",
            "002094", "002298", "002611", "600243", "600358",
            "600410", "600666", "601086", "603030", "603038",
            "603106", "000796", "002131", "600340", "600530",
            "600593", "603598", "605188", "000062", "000592",
            "000903", "002211", "002682", "002685", "002691",
            "002915", "600192", "600650", "603721", "000158",
            "000628", "000678", "000759", "000892", "002175",
            "002177", "002369", "002418", "002542", "002735",
            "002796", "600281", "600375", "600403", "600610",
            "600619", "600828", "601606", "603011", "603023",
            "603955", "000972", "002181", "002207", "002213",
            "002512", "002513", "002630", "002636", "002667",
            "002862", "600172", "600187", "600203", "600376",
            "603838", "603988", "000017", "000809", "000953",
            "000980", "002115", "002200", "002564", "002769",
            "003029", "600622", "600841", "600843", "603278",
            "603580", "603657", "603803", "605398", "000056",
            "000525", "000566", "002122", "002165", "002173",
            "002178", "002229", "002278", "002364", "002596",
            "002629", "002730", "002762", "002792", "002846",
            "002878", "600506", "600550", "600793", "601929",
            "603083", "603117", "603122", "603286", "603359",
            "603789", "605303", "605488", "000520", "000572",
            "000679", "000695", "001212", "001339", "002031",
            "002196", "002208", "002259", "002265", "002342",
            "002657", "002829", "600250", "600734", "603316",
            "603332", "603667", "603767", "000670", "000890",
            "000909", "001239", "001379", "002021", "002253",
            "002323", "002361", "002520", "002700", "600280",
            "600302", "600365", "600408", "600571", "600624",
            "600753", "600881", "603188", "603232", "603333",
            "603390", "603608", "603696", "603928", "001267",
            "001316", "002103", "002187", "002261", "002388",
            "002474", "002565", "002639", "002651", "002779",
            "002786", "002975", "002981", "002995", "600053",
            "600105", "600246", "600345", "600543", "600686",
            "600807", "600892", "603015", "603280", "603366",
            "603839", "603978", "605069", "605081", "605100",
            "605179", "605298", "000020", "000518", "000710",
            "000736", "001331", "001696", "002085", "002086",
            "002163", "002164", "002269", "002354", "002425",
            "002501", "002553", "002581", "002622", "002718",
            "002748", "002805", "002811", "002888", "003005",
            "600475", "600601", "600676", "600698", "601869",
            "601933", "603163", "603166", "603607", "603686",
            "603863", "603933", "605277", "000510", "000637",
            "000692", "000702", "001255", "001309", "002009",
            "002104", "002413", "002453", "002547", "002607",
            "002645", "002757", "002767", "002865", "002882",
            "002900", "002940", "002969", "003004", "600078",
            "600156", "600337", "600520", "600774", "601069",
            "603032", "603042", "603052", "603196", "603221",
            "603353", "603929", "603991", "000677", "000737",
            "000815", "000826", "000833", "000882", "001330",
            "002046", "002055", "002124", "002190", "002201",
            "002227", "002248", "002277", "002285", "002290",
            "002316", "002514", "002575", "002593", "002602",
            "002670", "002689", "002721", "002725", "002741",
            "003021", "003042", "600198", "600545", "600590",
            "600611", "600654", "600714", "600831", "600865",
            "603090", "603095", "603123", "603660", "603679",
            "603773", "603887", "605033", "605598",
        ]

        logger.info(f"使用高频涨停股票池，共 {len(default_pool)} 只股票")
        logger.info(f"股票池特点：近2年涨停次数>=21次，具有较强上涨动能")

        return default_pool

    def _get_model_scores(
        self,
        stock_codes: List[str],
        market_data_dict: Dict[str, StockData]
    ) -> Dict[str, ModelScore]:
        """获取模型评分"""
        positions_data = {}

        for code in stock_codes:
            market_data = market_data_dict.get(code)
            if market_data:
                positions_data[code] = {
                    "current_price": market_data.current_price,
                    "holding_days": 0,  # 新股票，持仓天数为0
                    "profit_loss_ratio": 0.0
                }

        return self.model_client.get_batch_scores(stock_codes, positions_data)

    def _build_candidate_stock(
        self,
        code: str,
        market_data: StockData,
        model_score: Optional[ModelScore]
    ) -> Optional[CandidateStock]:
        """
        构建候选股票对象

        Args:
            code: 股票代码
            market_data: 市场数据
            model_score: 模型评分

        Returns:
            CandidateStock对象或None
        """
        try:
            reasons = []

            # 计算技术指标评分
            technical_score = self._calculate_technical_score(market_data, reasons)

            # 计算基本面评分
            fundamental_score = self._calculate_fundamental_score(market_data, reasons)

            # 综合评分
            # 权重: 模型评分 50%, 技术指标 30%, 基本面 20%
            if model_score and model_score.score > 0:
                score = (
                    model_score.score * 0.5 +
                    technical_score * 0.3 +
                    fundamental_score * 0.2
                )
            else:
                # 没有模型评分时，提高技术和基本面权重
                score = (
                    technical_score * 0.6 +
                    fundamental_score * 0.4
                )

            # 判断股票类型
            stock_type = self._classify_stock_type(market_data, model_score)

            candidate = CandidateStock(
                code=code,
                name=market_data.name,
                score=score,
                model_score=model_score.score if model_score else None,
                technical_score=technical_score,
                fundamental_score=fundamental_score,
                current_price=market_data.current_price,
                change_percent=market_data.change_percent,
                volume_ratio=market_data.volume / 100000 if market_data.volume else 0,
                turnover_rate=market_data.turnover_rate,
                pe_ratio=market_data.pe_ratio,
                market_cap=market_data.circulation_market_cap,
                stock_type=stock_type,
                reasons=reasons
            )

            return candidate

        except Exception as e:
            logger.error(f"构建候选股票失败 {code}: {e}")
            return None

    def _calculate_technical_score(
        self,
        market_data: StockData,
        reasons: List[str]
    ) -> float:
        """
        计算技术指标评分 (0-100)

        考虑因素：
        - 涨跌幅
        - 量比
        - 换手率
        - 价格位置
        - 内外盘比例
        """
        score = 50.0  # 基础分

        # 涨跌幅评分 (权重30%)
        if market_data.change_percent > 5:
            score += 15
            reasons.append(f"强势上涨 ({market_data.change_percent:+.2f}%)")
        elif market_data.change_percent > 2:
            score += 10
            reasons.append(f"温和上涨 ({market_data.change_percent:+.2f}%)")
        elif market_data.change_percent > -2:
            score += 5
        elif market_data.change_percent < -5:
            score -= 10
            reasons.append(f"大幅下跌 ({market_data.change_percent:+.2f}%)")

        # 量比评分 (权重25%)
        volume_ratio = market_data.volume / 100000 if market_data.volume else 0
        if volume_ratio > 2.0:
            score += 15
            reasons.append(f"放量明显 (量比{volume_ratio:.1f})")
        elif volume_ratio > 1.5:
            score += 10
            reasons.append(f"成交活跃 (量比{volume_ratio:.1f})")
        elif volume_ratio < 0.5:
            score -= 10

        # 换手率评分 (权重25%)
        if market_data.turnover_rate > 8:
            score += 12
            reasons.append(f"高换手率 ({market_data.turnover_rate:.1f}%)")
        elif market_data.turnover_rate > 5:
            score += 8
        elif market_data.turnover_rate < 1:
            score -= 8

        # 价格位置评分 (权重20%)
        price_position = market_data.get_price_position()
        if 0.3 <= price_position <= 0.7:
            score += 10
            reasons.append(f"价格位置适中 ({price_position:.1%})")
        elif price_position > 0.9:
            score -= 5
            reasons.append("价格接近日内高点")

        return max(0, min(100, score))

    def _calculate_fundamental_score(
        self,
        market_data: StockData,
        reasons: List[str]
    ) -> float:
        """
        计算基本面评分 (0-100)

        考虑因素：
        - 市盈率
        - 市值规模
        - 流动性
        """
        score = 50.0  # 基础分

        # 市盈率评分 (权重40%)
        if market_data.pe_ratio > 0:
            if 10 <= market_data.pe_ratio <= 30:
                score += 20
                reasons.append(f"估值合理 (PE={market_data.pe_ratio:.1f})")
            elif market_data.pe_ratio < 10:
                score += 15
                reasons.append(f"低估值 (PE={market_data.pe_ratio:.1f})")
            elif market_data.pe_ratio > 50:
                score -= 15
                reasons.append(f"高估值 (PE={market_data.pe_ratio:.1f})")

        # 市值规模评分 (权重30%)
        if market_data.circulation_market_cap > 0:
            market_cap = market_data.circulation_market_cap / 10000  # 转换为亿
            if market_cap >= 100:
                score += 15
                reasons.append("大盘股，流动性好")
            elif market_cap >= 50:
                score += 10
            elif market_cap < 20:
                score -= 10
                reasons.append("小盘股，流动性风险")

        # 成交额评分 (权重30%)
        if market_data.turnover >= 10000:  # 成交额 >= 1亿
            score += 15
            reasons.append("成交额充足")
        elif market_data.turnover >= 5000:
            score += 10
        elif market_data.turnover < 1000:
            score -= 15
            reasons.append("成交额不足")

        return max(0, min(100, score))

    def _classify_stock_type(
        self,
        market_data: StockData,
        model_score: Optional[ModelScore]
    ) -> StockType:
        """分类股票类型"""
        # 成长股：高评分 + 高换手
        if model_score and model_score.score >= 80 and market_data.turnover_rate > 5:
            return StockType.GROWTH

        # 价值股：低PE + 大市值
        if market_data.pe_ratio > 0 and market_data.pe_ratio < 15 and \
           market_data.circulation_market_cap > 500000:
            return StockType.VALUE

        # 动量股：强势上涨 + 放量
        if market_data.change_percent > 5 and market_data.volume > 100000:
            return StockType.MOMENTUM

        # 反转股：超跌 + 模型评分回升
        if market_data.change_percent < -3 and model_score and model_score.score >= 70:
            return StockType.TURNAROUND

        return StockType.GROWTH  # 默认成长股

    def filter_by_risk(self, candidates: List[CandidateStock]) -> List[CandidateStock]:
        """
        风险过滤

        过滤掉：
        1. ST股票
        2. 涨停/跌停股票
        3. 黑名单股票
        4. 流动性不足的股票
        """
        filtered = []

        for candidate in candidates:
            # 黑名单检查
            if candidate.code in BLACKLIST_STOCKS:
                logger.debug(f"过滤 {candidate.code}: 黑名单股票")
                continue

            # ST股检查
            if any(candidate.name.startswith(prefix) for prefix in ST_STOCK_PREFIX):
                logger.debug(f"过滤 {candidate.code}: ST股票")
                continue

            # 涨跌停检查
            if abs(candidate.change_percent) >= 9.9:
                logger.debug(f"过滤 {candidate.code}: 涨跌停股票")
                continue

            # 流动性检查（成交额至少1000万）
            market_data_check = self.market_client.get_stock_data(candidate.code)
            if market_data_check and market_data_check.turnover < 1000:
                logger.debug(f"过滤 {candidate.code}: 流动性不足")
                continue

            filtered.append(candidate)

        return filtered

    def _filter_by_quality(self, candidates: List[CandidateStock]) -> List[CandidateStock]:
        """
        弹性质量筛选（三级降级策略）

        策略：
        1. 严格模式：综合评分>=56, 模型评分>=70
        2. 宽松模式：综合评分>=40, 模型评分>=50
        3. Top N兜底：按评分排序，强制取Top 10（评分>=30）

        返回：符合质量要求的候选股票列表（至少10只）
        """
        selection_config = STOCK_SELECTION_CONFIG
        filter_mode = selection_config.get("filter_mode", "auto")
        verbose = selection_config.get("verbose_logging", True)

        # 如果候选股票太少，直接返回
        if len(candidates) < 10:
            if verbose:
                logger.warning(f"候选股票数量不足10只({len(candidates)}只)，跳过质量筛选")
            return candidates

        # 模式1: 严格筛选
        if filter_mode in ["auto", "strict"]:
            strict = selection_config.get("strict_thresholds", {})
            strict_filtered = self._apply_quality_filter(
                candidates,
                min_score=strict.get("min_score", 56),
                min_model_score=strict.get("min_model_score", 70),
                label="严格模式"
            )

            if len(strict_filtered) >= 10:
                if verbose:
                    logger.info(f"✓ 严格模式通过: {len(strict_filtered)} 只股票符合条件")
                return strict_filtered
            elif verbose:
                logger.info(f"严格模式筛选结果不足: {len(strict_filtered)} 只 < 10只")

        # 模式2: 宽松筛选（降级）
        if filter_mode in ["auto", "relaxed"]:
            relaxed = selection_config.get("relaxed_thresholds", {})
            relaxed_filtered = self._apply_quality_filter(
                candidates,
                min_score=relaxed.get("min_score", 40),
                min_model_score=relaxed.get("min_model_score", 50),
                label="宽松模式"
            )

            if len(relaxed_filtered) >= 10:
                if verbose:
                    logger.warning(f"⚠ 降级到宽松模式: {len(relaxed_filtered)} 只股票符合条件")
                return relaxed_filtered
            elif verbose:
                logger.info(f"宽松模式筛选结果不足: {len(relaxed_filtered)} 只 < 10只")

        # 模式3: Top N 兜底（最终保障）
        fallback = selection_config.get("fallback_config", {})
        if not fallback.get("enabled", True):
            logger.warning("兜底模式已禁用，返回宽松筛选结果")
            return relaxed_filtered if filter_mode == "auto" else candidates

        min_count = fallback.get("min_count", 10)
        absolute_min_score = fallback.get("absolute_min_score", 30)

        # 按评分排序
        sorted_candidates = sorted(candidates, key=lambda c: c.score, reverse=True)

        # 取Top N，但要满足绝对最低分
        fallback_filtered = []
        for candidate in sorted_candidates:
            if len(fallback_filtered) >= min_count:
                break
            if candidate.score >= absolute_min_score:
                fallback_filtered.append(candidate)

        if verbose:
            if fallback.get("warn_on_fallback", True):
                logger.warning(
                    f"⚠⚠ 触发Top N兜底模式: 强制返回Top {len(fallback_filtered)} 只股票 "
                    f"(评分范围: {fallback_filtered[-1].score:.1f} - {fallback_filtered[0].score:.1f})"
                )

        return fallback_filtered

    def _apply_quality_filter(
        self,
        candidates: List[CandidateStock],
        min_score: float,
        min_model_score: float,
        label: str = ""
    ) -> List[CandidateStock]:
        """
        应用质量筛选阈值

        Args:
            candidates: 候选股票列表
            min_score: 最低综合评分
            min_model_score: 最低模型评分
            label: 筛选模式标签（用于日志）

        Returns:
            筛选后的股票列表
        """
        filtered = []
        for candidate in candidates:
            # 综合评分检查
            if candidate.score < min_score:
                logger.debug(
                    f"[{label}] 过滤 {candidate.code}: "
                    f"综合评分过低 ({candidate.score:.1f} < {min_score})"
                )
                continue

            # 模型评分检查（如果有）
            if candidate.model_score is not None and candidate.model_score < min_model_score:
                logger.debug(
                    f"[{label}] 过滤 {candidate.code}: "
                    f"模型评分过低 ({candidate.model_score:.1f} < {min_model_score})"
                )
                continue

            filtered.append(candidate)

        return filtered

    def rank_by_priority(self, candidates: List[CandidateStock]) -> List[CandidateStock]:
        """
        按优先级排序

        排序规则：
        1. 综合评分（主要）
        2. 模型评分（次要）
        3. 技术指标评分（辅助）
        """
        candidates.sort(
            key=lambda c: (
                c.score,
                c.model_score if c.model_score else 0,
                c.technical_score
            ),
            reverse=True
        )

        # 打印Top 10
        logger.info("Top 10 候选股票:")
        for i, candidate in enumerate(candidates[:10], 1):
            # 格式化模型评分（处理None值）
            model_score_str = f"{candidate.model_score:.1f}" if candidate.model_score is not None else "N/A"
            stock_type_str = candidate.stock_type.value if candidate.stock_type else "N/A"

            logger.info(
                f"{i}. {candidate.name} ({candidate.code}) - "
                f"综合评分: {candidate.score:.1f}, "
                f"模型评分: {model_score_str}, "
                f"类型: {stock_type_str}"
            )

        return candidates


# ============================================================================
# 使用示例和测试
# ============================================================================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建选股器
    selector = StockSelector()

    # 测试选股
    print("\n=== 测试智能选股 ===")
    candidates = selector.get_candidate_stocks(max_count=10)

    print(f"\n选出 {len(candidates)} 只候选股票：")
    for i, candidate in enumerate(candidates, 1):
        # 格式化模型评分和股票类型（处理None值）
        model_score_str = f"{candidate.model_score:.1f}" if candidate.model_score is not None else "N/A"
        stock_type_str = candidate.stock_type.value if candidate.stock_type else "N/A"

        print(f"\n{i}. {candidate.name} ({candidate.code})")
        print(f"   综合评分: {candidate.score:.1f}")
        print(f"   模型评分: {model_score_str}")
        print(f"   当前价: {candidate.current_price:.2f}元")
        print(f"   涨跌幅: {candidate.change_percent:+.2f}%")
        print(f"   股票类型: {stock_type_str}")
        print(f"   选中理由:")
        for reason in candidate.reasons[:3]:  # 显示前3条理由
            print(f"     - {reason}")
