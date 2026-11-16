"""Unit tests for leak-free store/source splitting and perceptual dHash duplicate checks."""
from PIL import Image, ImageDraw

from shelfsense_training.splits import (
    ImageRecord,
    assign_leak_free_splits,
    compute_dhash,
    find_cross_split_leak_pairs,
    hamming_distance,
    infer_source_group,
)


def _make_shelf_image(seed_offset: int, shift_px: int = 0) -> Image.Image:
    """Generates a synthetic shelf pattern image with distinct spatial layouts per seed."""
    img = Image.new("RGB", (160, 120), color=(30, 35, 45))
    draw = ImageDraw.Draw(img)
    for row in range(4):
        y = 10 + row * 28
        for col in range(5):
            # Vary box presence and luminance deterministically by seed_offset.
            h_val = ((seed_offset * 131 + row * 37 + col * 73) ^ (seed_offset * 17)) & 0xFF
            x = 8 + col * 30 + shift_px
            draw.rectangle([x, y, x + 22, y + 22], fill=(h_val, h_val, h_val))
    return img


def test_dhash_near_duplicates_vs_distinct_scenes() -> None:
    """Slight camera shift produces a tiny dHash distance; a different shelf has a large distance."""
    img_a = _make_shelf_image(1, shift_px=0)
    img_a_near = _make_shelf_image(1, shift_px=1)
    img_b = _make_shelf_image(99, shift_px=0)

    hash_a = compute_dhash(img_a)
    hash_a_near = compute_dhash(img_a_near)
    hash_b = compute_dhash(img_b)

    assert hamming_distance(hash_a, hash_a_near) <= 6
    assert hamming_distance(hash_a, hash_b) >= 16


def test_infer_source_group_keeps_planograms_and_sessions_together() -> None:
    """Different camera shots of the same planogram P03 map to the exact same source group."""
    g1 = infer_source_group("grocery", "C1_P03_N1_S4_1.JPG")
    g2 = infer_source_group("grocery", "C2_P03_N2_S4_2.JPG")
    g3 = infer_source_group("grocery", "C1_P09_N1_S4_1.JPG")
    assert g1 == g2 == "grocery:P03"
    assert g1 != g3


def test_assign_leak_free_splits_prevents_store_and_dhash_leaks() -> None:
    """Images from the same store OR with near-identical dHashes never land in different splits."""
    records = [
        # Store 1 (2 images)
        ImageRecord("s1_a", "store_1", dhash=0b10101010_00001111_00000000_11111111_00000000_11110000_10101010_01010101),
        ImageRecord("s1_b", "store_1", dhash=0b01010101_11110000_11111111_00000000_11111111_00001111_01010101_10101010),
        # Store 2 has a near-duplicate of Store 1's first image (1 bit difference)
        ImageRecord("s2_dup", "store_2", dhash=0b10101010_00001111_00000000_11111111_00000000_11110000_10101010_01010100),
        # Distinct stores with well-separated hashes
        ImageRecord("s3_a", "store_3", dhash=0x0000_0000_0000_0000),
        ImageRecord("s4_a", "store_4", dhash=0xFFFF_FFFF_FFFF_FFFF),
        ImageRecord("s5_a", "store_5", dhash=0x0F0F_0F0F_F0F0_F0F0),
        ImageRecord("s6_a", "store_6", dhash=0xF0F0_F0F0_0F0F_0F0F),
    ]

    splits = assign_leak_free_splits(records, max_hamming=8)
    assert set(splits.keys()) == {r.image_id for r in records}
    # Store 1 and Store 2 (linked by near-duplicate) must share the same split.
    assert splits["s1_a"] == splits["s1_b"] == splits["s2_dup"]
    # Zero leaks across splits.
    assert find_cross_split_leak_pairs(records, splits, max_hamming=8) == []
    # All three splits receive data when enough independent clusters exist.
    assert set(splits.values()) == {"train", "val", "test"}


def test_official_split_collision_quarantines_to_train() -> None:
    """If a near-duplicate bridges official 'train' and 'test' images, both go to 'train'."""
    records = [
        ImageRecord("train_01", "sku:train:1", dhash=0xAAAA_AAAA_AAAA_AAAA, official_split="train"),
        ImageRecord("test_99", "sku:test:99", dhash=0xAAAA_AAAA_AAAA_AAAB, official_split="test"),
        ImageRecord("val_01", "sku:val:1", dhash=0x0000_1111_2222_3333, official_split="val"),
        ImageRecord("test_02", "sku:test:2", dhash=0xFFFF_EEEE_DDDD_CCCC, official_split="test"),
    ]
    splits = assign_leak_free_splits(records, max_hamming=8)
    assert splits["train_01"] == "train"
    assert splits["test_99"] == "train"
    assert splits["val_01"] == "val"
    assert splits["test_02"] == "test"
    assert find_cross_split_leak_pairs(records, splits, max_hamming=8) == []
