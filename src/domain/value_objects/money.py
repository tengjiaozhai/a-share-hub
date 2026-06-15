from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import ClassVar


@dataclass(frozen=True)
class Money:
    """金额值对象"""

    amount: Decimal
    currency: str = "CNY"

    # 支持的货币
    SUPPORTED_CURRENCIES: ClassVar[set[str]] = {"CNY", "USD", "HKD"}

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, 'amount', Decimal(str(self.amount)))

        if self.currency not in self.SUPPORTED_CURRENCIES:
            raise ValueError(f"不支持的货币: {self.currency}")

        if self.amount < 0:
            raise ValueError("金额不能为负数")

    @classmethod
    def create(cls, amount: float, currency: str = "CNY") -> 'Money':
        """创建Money实例"""
        return cls(Decimal(str(amount)), currency)

    @classmethod
    def zero(cls, currency: str = "CNY") -> 'Money':
        """创建零金额"""
        return cls(Decimal("0"), currency)

    def add(self, other: 'Money') -> 'Money':
        """加法"""
        if self.currency != other.currency:
            raise ValueError(f"货币不匹配: {self.currency} vs {other.currency}")
        return Money(self.amount + other.amount, self.currency)

    def subtract(self, other: 'Money') -> 'Money':
        """减法"""
        if self.currency != other.currency:
            raise ValueError(f"货币不匹配: {self.currency} vs {other.currency}")
        result = self.amount - other.amount
        if result < 0:
            raise ValueError("结果不能为负数")
        return Money(result, self.currency)

    def multiply(self, factor: float) -> 'Money':
        """乘法"""
        return Money(self.amount * Decimal(str(factor)), self.currency)

    def divide(self, divisor: float) -> 'Money':
        """除法"""
        if divisor == 0:
            raise ValueError("除数不能为零")
        return Money(self.amount / Decimal(str(divisor)), self.currency)

    def round(self, places: int = 2) -> 'Money':
        """四舍五入"""
        quantize = Decimal(10) ** -places
        return Money(self.amount.quantize(quantize, rounding=ROUND_HALF_UP), self.currency)

    @property
    def is_zero(self) -> bool:
        """是否为零"""
        return self.amount == 0

    @property
    def is_positive(self) -> bool:
        """是否为正数"""
        return self.amount > 0

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"

    def __repr__(self) -> str:
        return f"Money(amount={self.amount}, currency='{self.currency}')"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Money):
            return False
        return self.amount == other.amount and self.currency == other.currency

    def __hash__(self) -> int:
        return hash((self.amount, self.currency))

    def __lt__(self, other: 'Money') -> bool:
        if self.currency != other.currency:
            raise ValueError(f"货币不匹配: {self.currency} vs {other.currency}")
        return self.amount < other.amount

    def __le__(self, other: 'Money') -> bool:
        if self.currency != other.currency:
            raise ValueError(f"货币不匹配: {self.currency} vs {other.currency}")
        return self.amount <= other.amount

    def __gt__(self, other: 'Money') -> bool:
        if self.currency != other.currency:
            raise ValueError(f"货币不匹配: {self.currency} vs {other.currency}")
        return self.amount > other.amount

    def __ge__(self, other: 'Money') -> bool:
        if self.currency != other.currency:
            raise ValueError(f"货币不匹配: {self.currency} vs {other.currency}")
        return self.amount >= other.amount
