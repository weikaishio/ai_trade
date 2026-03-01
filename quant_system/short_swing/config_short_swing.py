"""
超短线交易系统配置文件

所有参数集中管理，禁止在代码中硬编码。
"""

# ==================== 情绪周期判断阈值 ====================

# 情绪状态判断阈值（基于涨停数量和涨幅分布）
SENTIMENT_THRESHOLDS = {
    "freezing": {  # 冰点期
        "limit_up_count": 10,  # 涨停数量 < 10
        "avg_change_percent": 0.5,  # 平均涨幅 < 0.5%
        "rising_ratio": 0.3,  # 上涨股票占比 < 30%
    },
    "warming": {  # 回暖期
        "limit_up_count": 30,  # 涨停数量 10-30
        "avg_change_percent": 1.0,  # 平均涨幅 0.5%-1.5%
        "rising_ratio": 0.45,  # 上涨股票占比 30%-45%
    },
    "heating": {  # 升温期
        "limit_up_count": 60,  # 涨停数量 30-60
        "avg_change_percent": 1.8,  # 平均涨幅 1.5%-2.5%
        "rising_ratio": 0.6,  # 上涨股票占比 45%-60%
    },
    "climax": {  # 高潮期
        "limit_up_count": 100,  # 涨停数量 > 60
        "avg_change_percent": 2.5,  # 平均涨幅 > 2.5%
        "rising_ratio": 0.65,  # 上涨股票占比 > 60%
    },
    "ebbing": {  # 退潮期（高位放量下跌）
        "limit_up_count": 40,  # 涨停数量快速回落
        "avg_change_percent": 0.5,  # 平均涨幅快速回落
        "falling_ratio": 0.55,  # 下跌股票占比 > 50%
        "volume_ratio": 1.5,  # 成交量放大 > 1.5倍
    },
}

# 情绪周期连续性要求（避免误判）
SENTIMENT_CONTINUITY = {
    "min_consecutive_days": 2,  # 至少连续2天符合条件才确认状态
    "lookback_days": 5,  # 回溯5天判断趋势
}

# ==================== 主线题材识别参数 ====================

# 题材聚类参数
THEME_DETECTION = {
    "min_stocks_per_theme": 2,  # 题材至少包含2只股票（降低阈值，提高检测灵敏度）
    "leader_score_threshold": 80,  # 龙头股评分阈值（模型分数）
    "concept_correlation_threshold": 0.7,  # 概念相关性阈值
    "min_avg_change_percent": 2.5,  # 题材平均涨幅阈值 > 2.5%（降低阈值，提高检测灵敏度）
}

# 龙头股识别标准
LEADER_CRITERIA = {
    "limit_up_first": True,  # 优先涨停
    "min_volume_ratio": 2.0,  # 成交量放大 > 2倍
    "min_turnover": 5.0,  # 换手率 > 5%
    "price_range": (5.0, 50.0),  # 价格区间 5-50元
    "market_cap_range": (10e8, 100e8),  # 市值区间 10亿-100亿
}

# ==================== 选股评分权重 ====================

# 综合评分权重（总和为1.0）
STOCK_SCORING_WEIGHTS = {
    "limit_up_prob": 0.4,  # 涨停概率（来自模型）
    "downside_risk": -0.3,  # 下跌风险（负权重）
    "chanlun_risk": -0.2,  # 缠论风险（负权重）
    "sentiment_bonus": 0.1,  # 情绪周期加成
}

# 超短线选股过滤条件
SHORT_SWING_FILTERS = {
    "max_price": 30.0,  # 价格 <= 30元（低价股）
    "min_volume_ratio": 1.2,  # 成交量放大 > 1.2倍
    "min_turnover": 3.0,  # 换手率 > 3%
    "market_cap_range": (10e8, 100e8),  # 市值 10亿-100亿
    "exclude_st": True,  # 排除ST股票
    "exclude_new_stock_days": 60,  # 排除上市60天内新股
}

# 评分阈值
SCORE_THRESHOLDS = {
    "strong_buy": 85,  # 强烈建议 >= 85分
    "buy": 75,  # 建议买入 >= 75分
    "watch": 65,  # 关注 >= 65分
    "ignore": 0,  # 忽略 < 65分
}

# ==================== 风控参数 ====================

# 仓位管理
POSITION_MANAGEMENT = {
    "max_position_per_stock": 0.5,  # 单只股票最大仓位 50%
    "max_total_position": 1.0,  # 总仓位上限 100%
    "default_position_size": 0.3,  # 默认单股仓位 30%
}

# 止损止盈
STOP_LOSS_PROFIT = {
    "stop_loss": -0.05,  # 止损 -5%
    "stop_profit": 0.10,  # 止盈 +10%（超短线快速止盈）
}

# 熔断机制
CIRCUIT_BREAKER = {
    "daily_loss_limit": -0.03,  # 单日亏损 -3% 触发熔断
    "max_daily_trades": 10,  # 单日最多交易10次
}

# ==================== 数据源配置 ====================

# 东方财富API配置
EASTMONEY_API = {
    "base_url": "https://push2.eastmoney.com/api",
    "quote_url": "https://push2.eastmoney.com/api/qt/clist/get",
    "timeout": 10,  # 请求超时时间（秒）
    "retry_times": 3,  # 重试次数
    "retry_delay": 1,  # 重试延迟（秒）
}

# 模型服务配置
MODEL_SERVICE = {
    "base_url": "http://localhost:8999",
    "comprehensive_score_endpoint": "/comprehensive_score_custom",
    "timeout": 30,  # 模型推理可能较慢
}

# ==================== 缓存配置 ====================

CACHE_CONFIG = {
    "db_path": "quant_system/short_swing/short_swing.db",
    "ttl": {
        "market_data": 60,  # 市场数据缓存60秒
        "model_score": 300,  # 模型评分缓存5分钟
        "stock_info": 3600,  # 股票基本信息缓存1小时
    },
}

# ==================== 交易时间配置 ====================

TRADING_HOURS = {
    "morning": ("09:30", "11:30"),  # 早盘
    "afternoon": ("13:00", "15:00"),  # 午盘
    "pre_market": ("08:30", "09:15"),  # 盘前准备
    "auction": ("09:15", "09:25"),  # 集合竞价
}

# ==================== 日志配置 ====================

LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "log_file": "quant_system/logs/short_swing.log",
    "max_bytes": 10 * 1024 * 1024,  # 10MB
    "backup_count": 5,
}

# ==================== API服务配置 ====================

API_CONFIG = {
    "host": "0.0.0.0",
    "port": 8001,  # 避免与其他服务冲突
    "debug": False,  # 生产环境设为False
    "cors_origins": ["http://localhost:3000", "http://localhost:5173"],  # Vue开发服务器
}
