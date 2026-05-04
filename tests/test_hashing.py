from motorcycle_parts_watcher.schemas import NormalizedListing
from motorcycle_parts_watcher.utils.hashing import compute_content_hash


def test_hash_stable_for_same_content() -> None:
    listing = NormalizedListing(
        source_name="ebay",
        source_item_id="abc",
        bike_key="katana1100",
        title="OEM Front Fork",
        description="Used fork pair",
        url="https://example.com/a",
    )
    assert compute_content_hash(listing) == compute_content_hash(listing)

