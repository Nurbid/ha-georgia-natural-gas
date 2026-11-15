"""Persisted storage helpers for Georgia Natural Gas."""

from .const import PLAN_CAPABILITY_UNKNOWN


def migrate_storage_data(
    old_major_version: int,
    old_data: dict | None,
) -> dict:
    """Upgrade persisted coordinator storage to the current schema."""

    data = dict(old_data) if isinstance(old_data, dict) else {}

    if old_major_version < 2:
        # v1 was {"records": [...]} only.
        data.setdefault("records", [])
        data.setdefault("price_plan_records", [])
        data.setdefault("plan_capability", PLAN_CAPABILITY_UNKNOWN)

    return data
