from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TenantContext:
    user_id: str

    def __post_init__(self) -> None:
        if not self.user_id.strip():
            raise ValueError("user_id is required")


SYSTEM_TENANT = TenantContext("system")
