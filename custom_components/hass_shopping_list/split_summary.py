"""Split spoken/typed todo summaries and extract store phrases."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import re

# Commas, or the whole words "und" / "and" (any case). Do not split on "&".
_SPLIT_RE = re.compile(r"\s*,\s*|\s+\b(?:und|and)\b\s*", re.IGNORECASE)

# Longer phrases first ("aus dem" before "aus").
_STORE_PREP = r"(?:aus dem|im|bei|vom|von|aus|für|at|from)"
_TRAILING_VERB = r"(?:kaufen|holen)"


def split_item_summary(summary: str) -> list[str]:
    """Split a summary on commas and und/and into trimmed non-empty names.

    Examples:
        "Butter und Milch" -> ["Butter", "Milch"]
        "Eier, Mehl und Zucker" -> ["Eier", "Mehl", "Zucker"]
        "Ben & Jerry's" -> ["Ben & Jerry's"]
        "Milch" -> ["Milch"]

    Empty / whitespace-only input returns a single entry so create behavior
    stays unchanged for blank summaries.
    """
    text = summary or ""
    parts = [part.strip() for part in _SPLIT_RE.split(text) if part.strip()]
    return parts if parts else [text]


def extract_store_from_summary(
    summary: str, store_names: Sequence[str]
) -> tuple[str, str | None]:
    """Strip a trailing store phrase if it names an existing store.

    Recognizes phrases such as ``im Aldi``, ``bei Aldi``, ``vom Aldi``,
    ``von Aldi``, ``aus Aldi``, ``aus dem Aldi``, ``für Aldi``, ``at Aldi``,
    ``from Aldi``, optionally followed by ``kaufen`` / ``holen``.

    Returns ``(cleaned_summary, canonical_store_name)``. When no existing
    store matches, returns ``(summary, None)`` unchanged (no stripping).
    """
    text = summary or ""
    if not text or not store_names:
        return text, None

    # Longest name first so "Aldi Süd" wins over "Aldi".
    canonical_by_lower: dict[str, str] = {}
    for name in store_names:
        if not name or not str(name).strip():
            continue
        stripped = str(name).strip()
        canonical_by_lower.setdefault(stripped.casefold(), stripped)
    if not canonical_by_lower:
        return text, None

    sorted_names = sorted(canonical_by_lower.values(), key=len, reverse=True)
    names_pat = "|".join(re.escape(n) for n in sorted_names)
    pattern = re.compile(
        rf"^(?P<head>.*?)\s+{_STORE_PREP}\s+(?P<store>{names_pat})"
        rf"(?:\s+{_TRAILING_VERB})?\s*$",
        re.IGNORECASE,
    )
    match = pattern.match(text)
    if not match:
        return text, None

    store_key = match.group("store").casefold()
    canonical = canonical_by_lower.get(store_key)
    if canonical is None:
        return text, None

    head = match.group("head").strip()
    # Preserve blank-summary behavior for the follow-on split when head empty.
    return (head if head else ""), canonical


def parse_voice_item_summary(
    summary: str, store_names: Sequence[str] | None = None
) -> tuple[list[str], str | None]:
    """Extract optional store, then split remaining text into item names.

    Returns ``(item_names, matched_store_name_or_none)``.
    """
    cleaned, store = extract_store_from_summary(summary or "", store_names or ())
    return split_item_summary(cleaned), store


def resolve_store_id(
    store_name: str | None, stores: Iterable[Mapping[str, object]]
) -> str | None:
    """Map a canonical store name to ``store_id`` (case-insensitive)."""
    if not store_name:
        return None
    needle = store_name.casefold()
    for store in stores:
        name = store.get("name")
        if isinstance(name, str) and name.casefold() == needle:
            store_id = store.get("store_id")
            return str(store_id) if store_id is not None else None
    return None
