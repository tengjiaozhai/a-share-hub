def can_sell_position_same_day(market: str) -> bool:
    """A股T+1规则：当天买入的股票不能当天卖出"""
    if market == "CN_A":
        return False
    return True

def get_price_limit_ratio(stock_type: str) -> float:
    """获取涨跌停比例"""
    if stock_type == "ST":
        return 0.05  # ST股涨跌停5%
    return 0.10  # 普通股涨跌停10%

def is_tradable(status: str) -> bool:
    """判断股票是否可交易"""
    tradable_statuses = ["正常交易", "trading"]
    return status in tradable_statuses
