"""
量化交易系统

智能量化交易系统，集成实时行情、深度学习模型和自动交易。
"""

__version__ = "1.0.0"
__author__ = "Auto Trade System"

from .market_data_client import MarketDataClient, StockData
from .model_client import ModelClient, ModelScore
from .decision_engine import DecisionEngine, Position, TradeSignal, TradeAction, Priority
from .risk_manager import RiskManager, RiskReport, RiskLevel
from .config_quant import *

__all__ = [
    # 客户端
    "MarketDataClient",
    "ModelClient",

    # 核心引擎
    "DecisionEngine",
    "RiskManager",

    # 数据模型
    "StockData",
    "ModelScore",
    "Position",
    "TradeSignal",
    "RiskReport",

    # 枚举
    "TradeAction",
    "Priority",
    "RiskLevel",
]
