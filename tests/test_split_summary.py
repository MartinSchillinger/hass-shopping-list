"""Unit tests for voice summary split / store helpers."""

from __future__ import annotations

import pytest

from custom_components.hass_shopping_list.split_summary import (
    extract_store_from_summary,
    parse_voice_item_summary,
    resolve_store_id,
    split_item_summary,
)


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        ("Milch", ["Milch"]),
        ("Butter und Milch", ["Butter", "Milch"]),
        ("Butter AND Milch", ["Butter", "Milch"]),
        ("Butter Und Milch", ["Butter", "Milch"]),
        ("Eier, Mehl und Zucker", ["Eier", "Mehl", "Zucker"]),
        ("Eier,Mehl,Zucker", ["Eier", "Mehl", "Zucker"]),
        ("Ben & Jerry's", ["Ben & Jerry's"]),
        ("Salt and pepper", ["Salt", "pepper"]),
        ("  Butter  und  Milch  ", ["Butter", "Milch"]),
        ("Butter,", ["Butter"]),
        ("Butter und", ["Butter"]),
        ("", [""]),
        ("   ", ["   "]),
    ],
)
def test_split_item_summary(summary: str, expected: list[str]) -> None:
    """Helper splits on commas / und / and, not on &."""
    assert split_item_summary(summary) == expected


@pytest.mark.parametrize(
    ("summary", "stores", "expected_text", "expected_store"),
    [
        ("Eier und Butter im Aldi", ["Aldi", "Lidl"], "Eier und Butter", "Aldi"),
        ("Eier und Butter im Aldi kaufen", ["Aldi"], "Eier und Butter", "Aldi"),
        ("Milch bei aldi", ["Aldi"], "Milch", "Aldi"),
        ("Milch vom Aldi", ["Aldi"], "Milch", "Aldi"),
        ("Milch von Aldi", ["Aldi"], "Milch", "Aldi"),
        ("Milch aus Aldi", ["Aldi"], "Milch", "Aldi"),
        ("Milch aus dem Aldi", ["Aldi"], "Milch", "Aldi"),
        ("Milch für Aldi", ["Aldi"], "Milch", "Aldi"),
        ("Milk at Aldi", ["Aldi"], "Milk", "Aldi"),
        ("Milk from Aldi", ["Aldi"], "Milk", "Aldi"),
        ("Milch holen bei Aldi", ["Aldi"], "Milch holen", "Aldi"),
        ("Milch im Aldi holen", ["Aldi"], "Milch", "Aldi"),
        # Unknown store: leave text unchanged
        ("Milch im Aldi", ["Lidl"], "Milch im Aldi", None),
        ("Milch im Aldi", [], "Milch im Aldi", None),
        # No phrase
        ("Milch", ["Aldi"], "Milch", None),
        # Longest store name wins
        ("Brot bei Aldi Süd", ["Aldi", "Aldi Süd"], "Brot", "Aldi Süd"),
    ],
)
def test_extract_store_from_summary(
    summary: str,
    stores: list[str],
    expected_text: str,
    expected_store: str | None,
) -> None:
    """Strip trailing store phrases only when the store exists."""
    assert extract_store_from_summary(summary, stores) == (
        expected_text,
        expected_store,
    )


def test_parse_voice_item_summary_combines_split_and_store() -> None:
    """Store strip happens before und/comma split."""
    names, store = parse_voice_item_summary(
        "Eier und Butter im Aldi kaufen", ["Aldi", "Lidl"]
    )
    assert names == ["Eier", "Butter"]
    assert store == "Aldi"


def test_parse_voice_unknown_store_keeps_phrase_and_splits() -> None:
    """Unknown store phrase stays in text and may split oddly — no store set."""
    names, store = parse_voice_item_summary("Butter und Milch im Rewe", ["Aldi"])
    assert store is None
    assert names == ["Butter", "Milch im Rewe"]


def test_resolve_store_id_case_insensitive() -> None:
    """Map matched name to store_id."""
    stores = [
        {"store_id": "s1", "name": "Aldi"},
        {"store_id": "s2", "name": "Lidl"},
    ]
    assert resolve_store_id("aldi", stores) == "s1"
    assert resolve_store_id(None, stores) is None
    assert resolve_store_id("Rewe", stores) is None
