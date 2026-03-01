"""
数据模型定义

使用Pydantic进行数据验证和序列化。
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


# ==================== 股票基础数据 ====================

class StockQuote(BaseModel):
    """实时行情数据"""
    code: str = Field(..., description="股票代码，如 sh600519")
    name: str = Field(..., description="股票名称")
    price: float = Field(..., description="当前价格")
    change: float = Field(..., description="涨跌额")
    change_percent: float = Field(..., description="涨跌幅（%）")
    open: float = Field(..., description="开盘价")
    high: float = Field(..., description="最高价")
    low: float = Field(..., description="最低价")
    prev_close: float = Field(..., description="昨收价")
    volume: float = Field(..., description="成交量（股）")
    amount: float = Field(..., description="成交额（元）")
    turnover: float = Field(0.0, description="换手率（%）")
    volume_ratio: float = Field(1.0, description="量比")
    time: str = Field(..., description="更新时间")


class StockInfo(BaseModel):
    """股票基本信息"""
    code: str
    name: str
    market_cap: float = Field(0.0, description="总市值（元）")
    circulating_cap: float = Field(0.0, description="流通市值（元）")
    listing_date: Optional[str] = Field(None, description="上市日期")
    is_st: bool = Field(False, description="是否ST股票")


# ==================== 情绪周期 ====================

class SentimentState(BaseModel):
    """市场情绪状态"""
    state: str = Field(..., description="情绪状态: freezing/warming/heating/climax/ebbing")
    limit_up_count: int = Field(..., description="涨停数量")
    avg_change_percent: float = Field(..., description="平均涨幅（%）")
    rising_ratio: float = Field(..., description="上涨股票占比")
    falling_ratio: float = Field(..., description="下跌股票占比")
    volume_ratio: float = Field(1.0, description="市场整体量比")
    confidence: float = Field(..., description="判断置信度 0-1")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    description: str = Field("", description="状态描述")


# ==================== 主线题材 ====================

class ThemeStock(BaseModel):
    """题材内股票"""
    code: str
    name: str
    change_percent: float
    volume_ratio: float
    is_leader: bool = False


class Theme(BaseModel):
    """主线题材"""
    theme_name: str = Field(..., description="题材名称")
    concept_codes: List[str] = Field(default_factory=list, description="概念板块代码列表")
    stocks: List[ThemeStock] = Field(..., description="题材股票列表")
    leader_stock: Optional[ThemeStock] = Field(None, description="龙头股")
    avg_change_percent: float = Field(..., description="题材平均涨幅")
    stock_count: int = Field(..., description="股票数量")
    score: float = Field(..., description="题材强度评分 0-100")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ==================== 选股评分 ====================

class ModelScore(BaseModel):
    """模型评分结果"""
    code: str
    limit_up_prob: float = Field(..., description="涨停概率")
    downside_risk_prob: float = Field(..., description="下跌风险概率")
    chanlun_risk_prob: float = Field(..., description="缠论风险概率")
    short_term_risk: float = Field(..., description="短期风险")
    total_score: float = Field(..., description="综合分数")


class StockCandidate(BaseModel):
    """选股候选"""
    code: str
    name: str
    price: float
    change_percent: float
    volume_ratio: float
    turnover: float
    market_cap: float

    # 模型评分
    limit_up_prob: float
    downside_risk: float
    chanlun_risk: float

    # 综合评分
    final_score: float = Field(..., description="最终评分 0-100")
    signal: str = Field(..., description="信号: strong_buy/buy/watch/ignore")

    # 所属题材
    theme: Optional[str] = Field(None, description="所属主线题材")
    is_leader: bool = Field(False, description="是否龙头股")

    # 情绪加成
    sentiment_bonus: float = Field(0.0, description="情绪周期加成")

    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ==================== API请求/响应 ====================

class SentimentResponse(BaseModel):
    """情绪周期API响应"""
    success: bool = True
    sentiment: SentimentState
    message: str = ""


class ThemesResponse(BaseModel):
    """主线题材API响应"""
    success: bool = True
    themes: List[Theme]
    top_theme: Optional[Theme] = None
    message: str = ""


class CandidatesRequest(BaseModel):
    """选股候选请求"""
    limit: int = Field(20, description="返回数量上限", ge=1, le=100)
    min_score: float = Field(65.0, description="最低评分", ge=0, le=100)
    exclude_codes: List[str] = Field(default_factory=list, description="排除股票代码列表")


class CandidatesResponse(BaseModel):
    """选股候选API响应"""
    success: bool = True
    candidates: List[StockCandidate]
    sentiment_state: str = Field("", description="当前情绪状态")
    total_count: int = Field(0, description="候选总数")
    message: str = ""
