from __future__ import annotations

from app.services import vision_rules


def test_map_class_filters_whitelist_in_kitchen() -> None:
    assert vision_rules.map_class("knife", 0.8, zone="kitchen") is None


def test_map_class_reports_knife_in_corridor() -> None:
    assert vision_rules.map_class("knife", 0.8, zone="corridor") == ("hygiene", "medium")


def test_map_class_filters_person_in_office() -> None:
    assert vision_rules.map_class("person", 0.9, zone="office") is None


def test_map_class_returns_none_for_non_mvp_class() -> None:
    assert vision_rules.map_class("laptop", 0.9, zone=None) is None


def test_map_class_vehicle_outside_whitelist() -> None:
    assert vision_rules.map_class("car", 0.6, zone="loading_area") == ("access_control", "negligible")
