"""
量化交易系统配置模块

包含所有系统配置参数、阈值和常量定义。
"""

from typing import Dict
import os

# ============================================================================
# API配置
# ============================================================================

# 模型API配置（单一API地址）
MODEL_API_URL = os.getenv(
    "MODEL_API_URL",
    "http://localhost:8999/comprehensive_score_custom"
)
MODEL_API_TIMEOUT = 30  # 超时时间（秒）
MODEL_API_RETRY = 3  # 重试次数

# 多模型API配置（各模型使用同一API，通过model_type参数区分）
MODEL_APIS = {
    "v2": {
        "url": os.getenv("MODEL_V2_URL", MODEL_API_URL),
        "timeout": 30,
        "retry": 3,
        "model_type": "v2"
    },
    "sentiment": {
        "url": os.getenv("MODEL_SENTIMENT_URL", MODEL_API_URL),
        "timeout": 30,
        "retry": 3,
        "model_type": "sentiment"
    },
    "improved_refined_v35": {
        "url": os.getenv("MODEL_IMPROVED_URL", MODEL_API_URL),
        "timeout": 30,
        "retry": 3,
        "model_type": "improved_refined_v35"
    }
}

# 模型融合配置
MODEL_FUSION_CONFIG = {
    "enable_fusion": True,  # 是否启用融合（False则使用v2单模型）
    "min_models_required": 2,  # 最少需要几个模型成功
    "use_v2_only_fallback": True,  # 降级时是否使用v2单模型

    # 分层策略阈值（与Go版本一致）
    "strategy_thresholds": {
        "short_term_high": 0.5,      # 短期模型高置信阈值
        "v2_good": 0.5,              # V2良好阈值
        "short_term_mid": 0.45,      # 短期模型中等阈值
        "v2_excellent": 0.6,         # V2优秀阈值
        "v2_superior": 0.7,          # V2极优阈值
        "short_term_ok": 0.4,        # 短期模型可接受阈值
        "high_consistency": 0.7,     # 高度一致性阈值
        "final_score_high": 0.4      # 综合评分高阈值
    },

    # 动态权重配置（与Go版本一致）
    "dynamic_weights": {
        "high_consistency": {  # 一致性 > 0.8
            "v2": 0.4,
            "sentiment": 0.3,
            "improved": 0.3
        },
        "mid_consistency": {   # 一致性 > 0.6
            "v2": 0.35,
            "sentiment": 0.35,
            "improved": 0.3
        },
        "low_consistency": {   # 一致性 <= 0.6
            "v2": 0.33,
            "sentiment": 0.33,
            "improved": 0.34
        }
    }
}

# 腾讯股票API配置
TENCENT_STOCK_API_URL = "http://qt.gtimg.cn/q="
STOCK_API_TIMEOUT = 10
STOCK_API_RETRY = 3

# ============================================================================
# 决策阈值配置
# ============================================================================

# 模型评分阈值 (0-100)
SCORE_THRESHOLDS: Dict[str, float] = {
    "strong_sell": 30,    # <30 强烈卖出
    "sell": 40,           # 30-40 建议卖出
    "hold": 60,           # 40-60 持有观望
    "buy": 80,            # 60-80 可考虑持有
    "strong_buy": 100     # >80 强烈持有
}

# 止损止盈配置
STOP_LOSS = -0.1         # 亏损10%强制止损
STOP_PROFIT = 0.2        # 盈利20%止盈
EMERGENCY_STOP_LOSS = -0.15  # 紧急止损线（亏损15%）

# 持仓时间阈值（天）
HOLDING_DAYS_WARNING = 3  # 持仓超过30天且亏损需警告
HOLDING_DAYS_LONG = 10     # 长期持仓阈值

# ============================================================================
# 风险管理配置
# ============================================================================

# 交易限制
MAX_DAILY_TRADES = 20      # 单日最大交易次数
MAX_POSITION_RATIO = 0.3   # 单只股票最大仓位比例
MIN_TRADE_INTERVAL = 15    # 两次交易最小间隔（秒）

# 资金管理
MAX_SINGLE_TRADE_AMOUNT = 12000  # 单笔最大交易金额（元）
MIN_TRADE_AMOUNT = 4000           # 最小交易金额（元）

# 风控熔断
DAILY_LOSS_LIMIT = -0.2   # 单日最大亏损5%触发熔断
CIRCUIT_BREAKER_COOLDOWN = 3600  # 熔断冷却时间（秒）

# ============================================================================
# 交易时间配置
# ============================================================================

# 交易时间段（仅工作日）
TRADING_HOURS = [
    ("09:30", "11:30"),   # 上午
    ("13:00", "15:00")    # 下午
]

# 避开集合竞价时间
AVOID_TIMES = [
    ("09:15", "09:25"),   # 开盘集合竞价
    ("14:57", "15:00")    # 尾盘集合竞价
]

# ============================================================================
# 系统运行配置
# ============================================================================

# 自动监控间隔
AUTO_CHECK_INTERVAL = 300  # 自动检查间隔（秒）5分钟
POSITION_REFRESH_INTERVAL = 600  # 持仓刷新间隔（秒）10分钟

# 自动化模式
AUTOMATION_MODE = True  # True: 完全自动化运行，无需人工交互
AUTO_OCR_ENABLED = True  # True: 自动使用OCR识别持仓
AUTO_TRADING_ENABLED = True  # True: 自动执行交易（生产环境谨慎启用）
AUTO_LOGIN_IF_NEEDED = True  # True: 需要时自动登录

# 非交易时间准备设置
PREPARE_BEFORE_TRADING = True  # 非交易时间是否准备系统（检查登录、获取持仓等）
PREPARE_CHECK_INTERVAL = 3600  # 准备检查间隔（秒，默认1小时）

# 测试配置
FORCE_TRADING_TIME = False  # 强制模拟交易时间（仅用于测试）

# 日志配置
LOG_LEVEL = "INFO"
LOG_FILE = "logs/quant_system.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# 数据缓存配置
CACHE_ENABLED = True
CACHE_TTL = 60  # 缓存有效期（秒）

# ============================================================================
# 决策权重配置
# ============================================================================

# 综合决策权重
DECISION_WEIGHTS = {
    "model_score": 0.5,      # 模型评分权重50%
    "price_trend": 0.2,      # 价格趋势权重20%
    "profit_loss": 0.2,      # 盈亏状态权重20%
    "holding_time": 0.1      # 持仓时间权重10%
}

# ============================================================================
# 告警配置
# ============================================================================

# 告警阈值
ALERT_THRESHOLDS = {
    "high_loss": -0.08,      # 高额亏损告警（亏损8%）
    "circuit_breaker": True,  # 熔断告警
    "api_failure": 3,        # API连续失败次数告警
}

# 告警方式（预留）
ALERT_METHODS = {
    "console": True,
    "log": True,
    "email": False,
    "sms": False
}

# ============================================================================
# 特殊股票配置
# ============================================================================

# 黑名单（永不交易）
BLACKLIST_STOCKS = [
    # "600000",  # 示例：浦发银行
]

# 白名单（优先关注）
WHITELIST_STOCKS = [
    # "600483",  # 示例：福能股份
]

# ST股票特殊处理
ST_STOCK_PREFIX = ["ST", "*ST", "S*ST"]
ST_STOCK_MAX_RATIO = 0.1  # ST股票最大仓位10%

# ============================================================================
# 买入策略配置
# ============================================================================

# 买入策略配置
BUY_STRATEGY_CONFIG = {
    # 选股参数
    "min_model_score": 45,          # 最低模型评分
    "min_volume_ratio": 1.5,        # 最低量比
    "max_pe_ratio": 50,             # 最高市盈率
    "min_roe": 10,                  # 最低ROE (%)
    "min_turnover": 1000,           # 最低成交额（万元）

    # 仓位管理
    "max_positions": 10,            # 最大持仓数
    "max_single_position": 0.2,     # 单股最大仓位（20%）
    "max_industry_concentration": 0.4,  # 行业最大集中度（40%）
    "min_position_value": 5000,     # 最小持仓金额（元）
    "cash_reserve_ratio": 0.1,      # 现金保留比例（10%）

    # 买入时机
    "buy_time_windows": [
        ("09:35", "10:00"),         # 早盘买入窗口
        ("14:00", "14:30"),         # 尾盘买入窗口
    ],

    # 风险控制
    "max_daily_buy_count": 5,       # 单日最大买入笔数
    "min_buy_interval": 60,         # 买入间隔（秒）
    "stop_loss_ratio": -0.08,       # 止损比例（-8%）
    "max_new_position_ratio": 0.5,  # 单日新增仓位最大占比（50%）
}

# ============================================================================
# 测试模式配置
# ============================================================================

# 测试模式开关
TEST_MODE = False  # True: 模拟运行不实际交易
DRY_RUN = False    # True: 所有交易仅记录不执行

# 模拟数据
MOCK_DATA_ENABLED = False  # 使用模拟数据测试
MOCK_POSITIONS = [
    {
        "code": "002532",
        "name": "天山钻业",
        "quantity": 400,
        "cost_price": 19.64,
        "holding_days": 1
    },
    {
        "code": "301026",
        "name": "洗通科技",
        "quantity": 100,
        "cost_price": 34.19,
        "holding_days": 1
    },
    {
        "code": "603993",
        "name": "洛阳钼业",
        "quantity": 400,
        "cost_price": 26.17,
        "holding_days": 1
    }
]

# ============================================================================
# FastAPI配置
# ============================================================================

API_HOST = "0.0.0.0"
API_PORT = 8000
API_TITLE = "智能量化交易系统 API"
API_VERSION = "1.0.0"
API_DESCRIPTION = """
智能量化交易系统RESTful API

功能：
- 实时市场数据获取
- 深度学习模型评分
- 智能持仓分析
- 自动交易执行
"""

# API认证（预留）
API_KEY_ENABLED = False
API_KEY = "your-secret-key-here"

# ============================================================================
# 辅助函数
# ============================================================================

def get_decision_level(score: float) -> str:
    """
    根据评分获取决策级别

    Args:
        score: 模型评分 (0-100)

    Returns:
        决策级别: strong_sell, sell, hold, buy, strong_buy
    """
    if score < SCORE_THRESHOLDS["strong_sell"]:
        return "strong_sell"
    elif score < SCORE_THRESHOLDS["sell"]:
        return "sell"
    elif score < SCORE_THRESHOLDS["hold"]:
        return "hold"
    elif score < SCORE_THRESHOLDS["buy"]:
        return "buy"
    else:
        return "strong_buy"


def is_trading_time() -> bool:
    """
    判断当前是否在交易时间内

    Returns:
        bool: 是否在交易时间
    """
    # 如果强制交易时间模式，直接返回True（测试用）
    if FORCE_TRADING_TIME:
        return True

    from datetime import datetime, time

    now = datetime.now()

    # 检查是否为工作日（周一到周五）
    if now.weekday() >= 5:
        return False

    current_time = now.time()

    # 检查是否在交易时间段内
    for start_str, end_str in TRADING_HOURS:
        start_time = time.fromisoformat(start_str)
        end_time = time.fromisoformat(end_str)
        if start_time <= current_time <= end_time:
            # 检查是否在避开时间内
            for avoid_start_str, avoid_end_str in AVOID_TIMES:
                avoid_start = time.fromisoformat(avoid_start_str)
                avoid_end = time.fromisoformat(avoid_end_str)
                if avoid_start <= current_time <= avoid_end:
                    return False
            return True

    return False


def format_stock_code(code: str) -> str:
    """
    格式化股票代码为腾讯API格式

    Args:
        code: 股票代码（6位数字）

    Returns:
        格式化后的代码（如：sh600483, sz000001）
    """
    code = code.strip()

    # 上海交易所：60开头
    if code.startswith('60'):
        return f"sh{code}"
    # 深圳交易所：00、30开头
    elif code.startswith('00') or code.startswith('30'):
        return f"sz{code}"
    else:
        raise ValueError(f"无法识别的股票代码: {code}")


if __name__ == "__main__":
    # 配置测试
    print(f"模型API地址: {MODEL_API_URL}")
    print(f"决策阈值: {SCORE_THRESHOLDS}")
    print(f"止损线: {STOP_LOSS*100}%")
    print(f"止盈线: {STOP_PROFIT*100}%")
    print(f"当前是否交易时间: {is_trading_time()}")
    print(f"测试模式: {TEST_MODE}")

    # 测试代码格式化
    test_codes = ["002532", "301026", "603993"]
    for code in test_codes:
        print(f"{code} -> {format_stock_code(code)}")
