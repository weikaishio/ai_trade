"""
交易时间判断工具

判断当前是否处于交易时间，用于区分实时数据和历史数据获取逻辑。
"""

import logging
from datetime import datetime, time
from typing import Tuple

from ..config_short_swing import TRADING_HOURS

logger = logging.getLogger(__name__)


def is_trading_day(date: datetime = None) -> bool:
    """
    判断是否为交易日（简化版：仅判断是否为工作日）

    注意：此方法不考虑节假日。完整实现需要接入交易日历API。

    Args:
        date: 要检查的日期，默认为今天

    Returns:
        是否为交易日（工作日）
    """
    if date is None:
        date = datetime.now()

    # 0=周一, 6=周日
    weekday = date.weekday()
    is_weekday = weekday < 5  # 周一到周五

    logger.debug(f"Date {date.date()} is {'a' if is_weekday else 'not a'} weekday")
    return is_weekday


def is_trading_time(dt: datetime = None) -> Tuple[bool, str]:
    """
    判断当前是否为交易时间

    Args:
        dt: 要检查的时间，默认为当前时间

    Returns:
        (是否为交易时间, 所处阶段描述)
        阶段: "pre_market" | "auction" | "morning" | "noon_break" | "afternoon" | "after_market" | "non_trading_day"
    """
    if dt is None:
        dt = datetime.now()

    # 首先检查是否为交易日
    if not is_trading_day(dt):
        return False, "non_trading_day"

    current_time = dt.time()

    # 解析配置中的时间
    def parse_time(time_str: str) -> time:
        h, m = map(int, time_str.split(':'))
        return time(hour=h, minute=m)

    # 盘前准备 08:30-09:15
    pre_market_start = parse_time(TRADING_HOURS["pre_market"][0])
    pre_market_end = parse_time(TRADING_HOURS["pre_market"][1])

    # 集合竞价 09:15-09:25
    auction_start = parse_time(TRADING_HOURS["auction"][0])
    auction_end = parse_time(TRADING_HOURS["auction"][1])

    # 早盘 09:30-11:30
    morning_start = parse_time(TRADING_HOURS["morning"][0])
    morning_end = parse_time(TRADING_HOURS["morning"][1])

    # 午盘 13:00-15:00
    afternoon_start = parse_time(TRADING_HOURS["afternoon"][0])
    afternoon_end = parse_time(TRADING_HOURS["afternoon"][1])

    # 判断所处阶段
    if pre_market_start <= current_time < pre_market_end:
        return False, "pre_market"
    elif auction_start <= current_time < auction_end:
        return False, "auction"
    elif morning_start <= current_time <= morning_end:
        return True, "morning"
    elif morning_end < current_time < afternoon_start:
        return False, "noon_break"
    elif afternoon_start <= current_time <= afternoon_end:
        return True, "afternoon"
    else:
        return False, "after_market"


def get_last_trading_close_time() -> datetime:
    """
    获取最近一个交易日的收盘时间

    Returns:
        最近交易日的15:00时间点
    """
    now = datetime.now()

    # 从今天开始往回找最近的交易日
    for days_ago in range(7):  # 最多回溯7天（覆盖周末+节假日）
        check_date = datetime(now.year, now.month, now.day) - timedelta(days=days_ago)

        if is_trading_day(check_date):
            # 如果是交易日，返回15:00
            close_time = datetime.combine(
                check_date.date(),
                time(hour=15, minute=0)
            )
            logger.info(f"Last trading close time: {close_time}")
            return close_time

    # 理论上不会到这里（7天内必有交易日）
    logger.warning("Could not find trading day in last 7 days")
    return now


def should_use_cached_data() -> bool:
    """
    判断是否应该使用缓存的交易日数据

    规则：
    - 交易时间内 → 使用实时数据（返回False）
    - 非交易时间 → 使用缓存数据（返回True）

    Returns:
        是否应该使用缓存数据
    """
    is_trading, stage = is_trading_time()

    if is_trading:
        logger.info(f"Currently in trading time ({stage}), use real-time data")
        return False
    else:
        logger.info(f"Currently not in trading time ({stage}), use cached data")
        return True


# 导入timedelta（上面用到了但忘记导入）
from datetime import timedelta
