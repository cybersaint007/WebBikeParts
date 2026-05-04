from motorcycle_parts_watcher.utils.similarity import title_similarity


def test_title_similarity_high() -> None:
    score = title_similarity("Suzuki GSX1300R front wheel OEM", "Suzuki GSX1300R front wheel OEM used")
    assert score > 0.85

