"""Leak-free dataset splitting by store/source and perceptual near-duplicate detection.

Ensures that images from the same store, capture session, or visual scene never
straddle train, validation, and test splits.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image


@dataclass(frozen=True)
class ImageRecord:
    """Represents a single shelf image with its source group and perceptual hash."""

    image_id: str
    source_group: str
    dhash: int
    official_split: str | None = None


@dataclass(frozen=True)
class DuplicatePair:
    """Two images whose perceptual hashes are within the leak threshold."""

    first_id: str
    first_split: str
    second_id: str
    second_split: str
    hamming_distance: int


def compute_dhash(image: Image.Image, hash_size: int = 8) -> int:
    """Computes a 64-bit horizontal difference hash (dHash) for an image.

    Resizes to (hash_size + 1, hash_size) in grayscale and compares adjacent
    horizontal pixels so brightness/scale shifts do not alter the hash.
    """
    gray = image.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
    width = hash_size + 1
    pixels = list(gray.tobytes())
    bits = 0
    for row in range(hash_size):
        row_offset = row * width
        for col in range(hash_size):
            bits = (bits << 1) | (1 if pixels[row_offset + col] > pixels[row_offset + col + 1] else 0)
    return bits


def compute_dhash_file(path: Path, hash_size: int = 8) -> int:
    """Loads an image from disk and returns its 64-bit dHash."""
    with Image.open(path) as img:
        return compute_dhash(img, hash_size=hash_size)


def hamming_distance(hash_a: int, hash_b: int) -> int:
    """Returns the number of differing bits between two integer hashes."""
    return (hash_a ^ hash_b).bit_count()


# Patterns used to extract a store, planogram, or capture session prefix from filenames.
_PLANOGRAM_RE = re.compile(r"^(C\d+_P\d+)", re.IGNORECASE)
_SKU_SPLIT_RE = re.compile(r"^(train|val|test)_(\d+)", re.IGNORECASE)
_SESSION_PREFIX_RE = re.compile(r"^([a-zA-Z0-9]+_[a-zA-Z0-9]+)_")


def infer_source_group(dataset_key: str, filename: str) -> str:
    """Extracts the store, planogram, or capture group identifier from an image name."""
    stem = Path(filename).stem
    m_plan = _PLANOGRAM_RE.match(stem)
    if m_plan:
        # Group by planogram P<id> across all cameras so the same shelf stays together.
        planogram = m_plan.group(1).split("_")[1].upper()
        return f"{dataset_key}:{planogram}"

    m_sku = _SKU_SPLIT_RE.match(stem)
    if m_sku:
        split_name = m_sku.group(1).lower()
        return f"{dataset_key}:{split_name}:{stem}"

    m_sess = _SESSION_PREFIX_RE.match(stem)
    if m_sess:
        return f"{dataset_key}:{m_sess.group(1).lower()}"

    return f"{dataset_key}:{stem.lower()}"


class _UnionFind:
    """Disjoint-set structure for merging groups that share near-duplicate images."""

    def __init__(self, items: Iterable[str]) -> None:
        self.parent = {x: x for x in items}

    def find(self, x: str) -> str:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while x != root:
            nxt = self.parent[x]
            self.parent[x] = root
            x = nxt
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            if ra < rb:
                self.parent[rb] = ra
            else:
                self.parent[ra] = rb


def assign_leak_free_splits(
    records: Sequence[ImageRecord],
    ratios: tuple[float, float, float] = (0.70, 0.15, 0.15),
    max_hamming: int = 8,
    seed: str = "shelfsense-v1",
) -> dict[str, str]:
    """Assigns each image to 'train', 'val', or 'test' with zero group or near-duplicate leaks.

    1. Images sharing a `source_group` are locked into the same cluster.
    2. Any two images whose dHash Hamming distance is <= `max_hamming` merge their
       clusters so visual near-duplicates cannot cross splits.
    3. If a cluster carries a single unanimous `official_split` (and does not collide
       with another official split), it keeps that split; if near-duplicates bridge
       two official splits, the whole merged cluster goes to 'train' so 'val' and
       'test' remain strictly uncontaminated.
    """
    if not records:
        return {}
    if abs(sum(ratios) - 1.0) > 1e-6:
        raise ValueError(f"Split ratios must sum to 1.0, got {ratios}")

    uf = _UnionFind(r.image_id for r in records)

    # Step 1: union by source_group.
    by_group: dict[str, list[str]] = {}
    for rec in records:
        by_group.setdefault(rec.source_group, []).append(rec.image_id)
    for members in by_group.values():
        first = members[0]
        for other in members[1:]:
            uf.union(first, other)

    # Step 2: union any pair within max_hamming dHash distance.
    n = len(records)
    for i in range(n):
        hi = records[i].dhash
        idi = records[i].image_id
        for j in range(i + 1, n):
            if hamming_distance(hi, records[j].dhash) <= max_hamming:
                uf.union(idi, records[j].image_id)

    clusters: dict[str, list[ImageRecord]] = {}
    for rec in records:
        clusters.setdefault(uf.find(rec.image_id), []).append(rec)

    assignments: dict[str, str] = {}
    unassigned_clusters: list[tuple[str, list[ImageRecord]]] = []

    for cid, members in sorted(clusters.items()):
        official = {m.official_split for m in members if m.official_split in {"train", "val", "test"}}
        if len(official) == 1:
            chosen = next(iter(official))
            for m in members:
                assignments[m.image_id] = chosen
        elif len(official) > 1:
            # A cross-split duplicate bridged two official splits; quarantine to train
            # so evaluation splits never see leaked training scenes.
            for m in members:
                assignments[m.image_id] = "train"
        else:
            unassigned_clusters.append((cid, members))

    if unassigned_clusters:
        # Sort deterministically by SHA-256 of (seed + cluster id), then allocate
        # greedily to stay closest to target ratios while ensuring non-empty splits
        # when at least 3 clusters exist.
        def _rank(item: tuple[str, list[ImageRecord]]) -> str:
            return hashlib.sha256(f"{seed}:{item[0]}".encode("utf-8")).hexdigest()

        ordered = sorted(unassigned_clusters, key=_rank)
        total_unassigned = sum(len(m) for _, m in ordered)
        targets = {
            "train": ratios[0] * total_unassigned,
            "val": ratios[1] * total_unassigned,
            "test": ratios[2] * total_unassigned,
        }
        counts = {"train": 0, "val": 0, "test": 0}

        for idx, (_, members) in enumerate(ordered):
            # Guarantee val and test each get at least one cluster when >= 3 clusters exist.
            if len(ordered) >= 3 and idx == len(ordered) - 2 and counts["val"] == 0:
                chosen = "val"
            elif len(ordered) >= 3 and idx == len(ordered) - 1 and counts["test"] == 0:
                chosen = "test"
            else:
                # Pick split with largest remaining deficit relative to target.
                chosen = max(("train", "val", "test"), key=lambda s: targets[s] - counts[s])
            counts[chosen] += len(members)
            for m in members:
                assignments[m.image_id] = chosen

    return assignments


def find_cross_split_leak_pairs(
    records: Sequence[ImageRecord],
    assignments: dict[str, str],
    max_hamming: int = 8,
) -> list[DuplicatePair]:
    """Audits split assignments and returns any cross-split near-duplicate or group leaks."""
    leaks: list[DuplicatePair] = []
    n = len(records)
    for i in range(n):
        ri = records[i]
        si = assignments[ri.image_id]
        for j in range(i + 1, n):
            rj = records[j]
            sj = assignments[rj.image_id]
            if si == sj:
                continue
            dist = hamming_distance(ri.dhash, rj.dhash)
            if ri.source_group == rj.source_group or dist <= max_hamming:
                leaks.append(
                    DuplicatePair(
                        first_id=ri.image_id,
                        first_split=si,
                        second_id=rj.image_id,
                        second_split=sj,
                        hamming_distance=dist,
                    )
                )
    return leaks
