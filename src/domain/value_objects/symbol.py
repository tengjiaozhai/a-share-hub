import re
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class Symbol:
    """股票代码值对象"""

    value: str

    # 股票代码格式：6位数字 + 后缀
    PATTERN: ClassVar[re.Pattern] = re.compile(r'^[0-9]{6}\.(SH|SZ|BJ)$')

    def __post_init__(self):
        if not self.value:
            raise ValueError("股票代码不能为空")

        if not self.PATTERN.match(self.value):
            raise ValueError(f"无效的股票代码格式: {self.value}。期望格式: 600519.SH")

    @classmethod
    def create(cls, code: str, market: str) -> 'Symbol':
        """创建Symbol实例"""
        return cls(f"{code}.{market}")

    @property
    def code(self) -> str:
        """获取股票代码部分"""
        return self.value.split('.')[0]

    @property
    def market(self) -> str:
        """获取市场部分"""
        return self.value.split('.')[1]

    @property
    def is_shanghai(self) -> bool:
        """是否是上海市场"""
        return self.market == 'SH'

    @property
    def is_shenzhen(self) -> bool:
        """是否是深圳市场"""
        return self.market == 'SZ'

    @property
    def is_beijing(self) -> bool:
        """是否是北京市场"""
        return self.market == 'BJ'

    def __str__(self) -> str:
        return self.value
