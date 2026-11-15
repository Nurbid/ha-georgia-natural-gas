"""Tests for GNG Store schema migration."""

from custom_components.gng.storage import migrate_storage_data


def test_migrate_v1_adds_price_plan_fields() -> None:
    """Existing v1 billing history gains empty Price Plan fields."""

    migrated = migrate_storage_data(
        1,
        {"records": [{"bill_date": "2026-11-03"}]},
    )

    assert migrated["records"] == [{"bill_date": "2026-11-03"}]
    assert migrated["price_plan_records"] == []
    assert migrated["plan_capability"] == "unknown"


def test_migrate_preserves_existing_v2_fields() -> None:
    """Already-migrated payloads keep Price Plan data intact."""

    migrated = migrate_storage_data(
        2,
        {
            "records": [],
            "price_plan_records": [{"bill_date": "2026-11-03"}],
            "plan_capability": "budget_billing",
        },
    )

    assert migrated["price_plan_records"] == [{"bill_date": "2026-11-03"}]
    assert migrated["plan_capability"] == "budget_billing"


def test_migrate_handles_none_and_non_dict() -> None:
    """Corrupt or empty legacy payloads become a safe empty v2 dict."""

    assert migrate_storage_data(1, None) == {
        "records": [],
        "price_plan_records": [],
        "plan_capability": "unknown",
    }
    assert migrate_storage_data(1, ["bad"]) == {
        "records": [],
        "price_plan_records": [],
        "plan_capability": "unknown",
    }
