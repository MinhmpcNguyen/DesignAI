from __future__ import annotations

import os

DEMO_INVENTORY_TENANT_ID = "demo_inventory_test"
DEMO_INVENTORY_ENV_FLAG = "TKNT_DEMO_INVENTORY_ENABLED"
DEMO_INVENTORY_ENV_FLAG_ALIAS = "TKNT_ENABLE_DEMO_INVENTORY"

_TRUE_VALUES = {"1", "true", "yes", "on"}


def is_demo_inventory_enabled() -> bool:
    for env_name in (DEMO_INVENTORY_ENV_FLAG, DEMO_INVENTORY_ENV_FLAG_ALIAS):
        value = os.getenv(env_name)
        if value is not None:
            return value.strip().lower() in _TRUE_VALUES
    return False


def is_demo_inventory_tenant(tenant_id: str | None) -> bool:
    return (tenant_id or "").strip() == DEMO_INVENTORY_TENANT_ID


def is_enabled_demo_inventory_tenant(tenant_id: str | None) -> bool:
    return is_demo_inventory_enabled() and is_demo_inventory_tenant(tenant_id)
