"""
量化交易系统配置模块

包含所有系统配置参数、阈值和常量定义。
"""

from typing import Dict
import os

# ============================================================================
# API配置
# ============================================================================

# 模型API配置
MODEL_API_URL = os.getenv(
    "MODEL_API_URL",
    "http://localhost:8999/comprehensive_score_custom"
)
MODEL_API_TIMEOUT = 30  # 超时时间（秒）
MODEL_API_RETRY = 3  # 重试次数

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
DAILY_LOSS_LIMIT = -0.05   # 单日最大亏损5%触发熔断
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
# 测试模式配置
# ============================================================================

# 测试模式开关
TEST_MODE = True  # True: 模拟运行不实际交易
DRY_RUN = True    # True: 所有交易仅记录不执行

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
