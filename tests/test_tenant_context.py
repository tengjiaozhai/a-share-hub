import pytest

from src.core.tenant import SYSTEM_TENANT, TenantContext


def test_tenant_context_rejects_empty_user_id():
    with pytest.raises(ValueError, match="user_id is required"):
        TenantContext("")


def test_system_tenant_is_explicit():
    assert SYSTEM_TENANT.user_id == "system"