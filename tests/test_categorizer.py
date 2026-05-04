from motorcycle_parts_watcher.utils.categorizer import categorize_listing, classify


def test_categorizer_detects_brakes() -> None:
    hit = classify("Front brake caliper GSX1300R", None)
    assert hit.category == "modification"
    assert hit.subcategory == "modification-brakes"


def test_categorizer_falls_back_unknown() -> None:
    assert categorize_listing("Vintage sticker pack", "misc graphics") == "unknown"

