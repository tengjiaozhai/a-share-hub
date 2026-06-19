from datetime import time
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")
US_EASTERN_TZ = ZoneInfo("America/New_York")

MARKET_TIMEZONES = {
    "a": CN_TZ,
    "us": US_EASTERN_TZ,
}

MARKET_SESSIONS = {
    "a": (time(9, 30), time(15, 0)),
    "us": (time(9, 30), time(16, 0)),
}

DAILY_RUN_TIMES_CN = {
    "a": time(9, 15),
    "us": time(21, 15),
}

A_SHARE_HOLIDAYS = {
    "2026-01-01": "A股元旦休市",
    "2026-02-16": "A股春节休市",
    "2026-02-17": "A股春节休市",
    "2026-02-18": "A股春节休市",
    "2026-02-19": "A股春节休市",
    "2026-02-20": "A股春节休市",
    "2026-04-06": "A股清明节休市",
    "2026-05-01": "A股劳动节休市",
    "2026-06-19": "A股端午节休市",
    "2026-09-25": "A股中秋节休市",
    "2026-10-01": "A股国庆节休市",
    "2026-10-02": "A股国庆节休市",
    "2026-10-05": "A股国庆节休市",
    "2026-10-06": "A股国庆节休市",
    "2026-10-07": "A股国庆节休市",
}

US_HOLIDAYS = {
    "2026-01-01": "US market New Year's Day closure",
    "2026-01-19": "US market Martin Luther King Jr. Day closure",
    "2026-02-16": "US market Presidents' Day closure",
    "2026-04-03": "US market Good Friday closure",
    "2026-05-25": "US market Memorial Day closure",
    "2026-06-19": "US market Juneteenth closure",
    "2026-07-03": "US market Independence Day observed closure",
    "2026-09-07": "US market Labor Day closure",
    "2026-11-26": "US market Thanksgiving Day closure",
    "2026-12-25": "US market Christmas Day closure",
}

MARKET_HOLIDAYS = {
    "a": A_SHARE_HOLIDAYS,
    "us": US_HOLIDAYS,
}
