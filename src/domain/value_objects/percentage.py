from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class Percentage:
    """百分比值对象"""

    value: Decimal

    def __post_init__(self):
        if not isinstance(self.value, Decimal):
            object.__setattr__(self, 'value', Decimal(str(self.value)))

        if self.value < 0 or self.value > 100:
            raise ValueError(f"百分比必须在0-100之间: {self.value}")

    @classmethod
    def create(cls, value: float) -> 'Percentage':
        """创建Percentage实例"""
        return cls(Decimal(str(value)))

    @classmethod
    def from_ratio(cls, ratio: float) -> 'Percentage':
        """从比率创建百分比（0.5 -> 50%）"""
        return cls(Decimal(str(ratio * 100)))

    @classmethod
    def zero(cls) -> 'Percentage':
        """创建零百分比"""
        return cls(Decimal("0"))

    @classmethod
    def hundred(cls) -> 'Percentage':
        """创建100%"""
        return cls(Decimal("100"))

    @property
    def ratio(self) -> Decimal:
        """转换为比率（0-1）"""
        return self.value / 100

    @property
    def is_zero(self) -> bool:
        """是否为零"""
        return self.value == 0

    @property
    def is_hundred(self) -> bool:
        """是否为100%"""
        return self.value == 100

    def add(self, other: 'Percentage') -> 'Percentage':
        """加法"""
        result = self.value + other.value
        if result > 100:
            raise ValueError(f"结果超过100%: {result}")
        return Percentage(result)

    def subtract(self, other: 'Percentage') -> 'Percentage':
        """减法"""
        result = self.value - other.value
        if result < 0:
            raise ValueError(f"结果低于0%: {result}")
        return Percentage(result)

    def multiply(self, factor: float) -> 'Percentage':
        """乘法"""
        result = self.value * Decimal(str(factor))
        if result > 100:
            raise ValueError(f"结果超过100%: {result}")
        return Percentage(result)

    def apply_to(self, amount: Decimal) -> Decimal:
        """应用百分比到金额"""
        return amount * self.ratio

    def round(self, places: int = 2) -> 'Percentage':
        """四舍五入"""
        quantize = Decimal(10) ** -places
        return Percentage(self.value.quantize(quantize, rounding=ROUND_HALF_UP))

    def __str__(self) -> str:
        return f"{self.value}%"

    def __repr__(self) -> str:
        return f"Percentage(value={self.value})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Percentage):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __lt__(self, other: 'Percentage') -> bool:
        return self.value < other.value

    def __le__(self, other: 'Percentage') -> bool:
        return self.value <= other.value

    def __gt__(self, other: 'Percentage') -> bool:
        return self.value > other.value

    def __ge__(self, other: 'Percentage') -> bool:
        return self.value >= other.value
