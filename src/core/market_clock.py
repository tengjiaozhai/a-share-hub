from datetime import datetime, time

def is_continuous_session(ts: datetime) -> bool:
    """判断是否在连续交易时段（9:30-11:30, 13:00-15:00）"""
    local_time = ts.timetz().replace(tzinfo=None)
    return (
        time(9, 30) <= local_time <= time(11, 30)
        or time(13, 0) <= local_time <= time(15, 0)
    )

def is_am_session(ts: datetime) -> bool:
    """判断是否在上午交易时段"""
    local_time = ts.timetz().replace(tzinfo=None)
    return time(9, 30) <= local_time <= time(11, 30)

def is_pm_session(ts: datetime) -> bool:
    """判断是否在下午交易时段"""
    local_time = ts.timetz().replace(tzinfo=None)
    return time(13, 0) <= local_time <= time(15, 0)
