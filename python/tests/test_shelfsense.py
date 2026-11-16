"""Unit tests for shelf row clustering, empty-gap detection, CLI, and FastAPI batch endpoints."""
from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
from shelfsense.api import _read_validated_image, create_app
from shelfsense.cli import main as cli_main
from shelfsense.detector import ShelfDetector, decode_predictions, letterbox_image
from shelfsense.gaps import Box, cluster_shelf_rows, detect_shelf_gaps
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageDraw


def _create_synthetic_shelf_photo() -> Image.Image:
    """Draws two shelf rows with 5 bright items total and a wide gap on the top row."""
    img = Image.new("RGB", (400, 240), color=(25, 28, 34))
    draw = ImageDraw.Draw(img)
    # Row 1: items at x=[20..60], x=[70..110], then a 110px gap, then x=[220..260]
    for x1 in (20, 70, 220):
        draw.rectangle([x1, 30, x1 + 40, 90], fill=(235, 235, 240))
    # Row 2: items at x=[20..60], x=[72..112]
    for x1 in (20, 72):
        draw.rectangle([x1, 140, x1 + 40, 200], fill=(230, 230, 235))
    return img


def test_cluster_rows_and_detect_empty_gaps() -> None:
    """Row clustering separates top and bottom shelves and flags the wide horizontal void."""
    boxes = [
        Box(20, 30, 60, 90),
        Box(70, 32, 110, 92),
        Box(220, 29, 260, 89),  # 110px gap after x=110 (median width is 40px -> ~3 missing items)
        Box(20, 140, 60, 200),
        Box(72, 142, 112, 202),
    ]
    rows = cluster_shelf_rows(boxes)
    assert len(rows) == 2
    assert len(rows[0]) == 3
    assert len(rows[1]) == 2

    gaps = detect_shelf_gaps(boxes, gap_multiplier=1.35)
    assert len(gaps) == 1
    g = gaps[0]
    assert g.row_index == 0
    assert g.x1 == 110.0
    assert g.x2 == 220.0
    assert g.estimated_missing_items == 3


def test_letterbox_and_decode_predictions() -> None:
    """Letterbox pads to (1, 3, S, S) and decode_predictions maps boxes back to original pixels."""
    img = Image.new("RGB", (800, 400), color=(100, 100, 100))
    tensor, scale, pad = letterbox_image(img, input_size=640)
    assert tensor.shape == (1, 3, 640, 640)
    assert scale == 0.8
    assert pad == (0, 160)

    # Simulate a predicted box centered in the padded 640x640 input: xc=320, yc=320, w=80, h=80, conf=0.9
    raw = np.array([[[320.0, 320.0, 80.0, 80.0, 0.9, 1.0]]], dtype=np.float32)
    decoded = decode_predictions(raw, orig_width=800, orig_height=400, scale=scale, pad=pad)
    assert len(decoded) == 1
    b = decoded[0]
    assert round(b.x1, 1) == 350.0
    assert round(b.y1, 1) == 150.0
    assert round(b.width, 1) == 100.0
    assert round(b.height, 1) == 100.0


def test_cli_count_command_outputs_json_and_text(tmp_path: Path, capsys) -> None:
    """`shelfsense count photo.jpg` runs detection, prints counts/gaps, and supports --json."""
    photo_path = tmp_path / "shelf.png"
    _create_synthetic_shelf_photo().save(photo_path)

    code = cli_main(["count", str(photo_path), "--threshold", "8", "--json"])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 5
    assert out["low_stock"] is True
    assert len(out["gaps"]) == 1
    assert out["estimated_missing_total"] >= 2

    code_txt = cli_main(["count", str(photo_path), "--threshold", "3"])
    assert code_txt == 0
    txt_out = capsys.readouterr().out
    assert "5 items detected" in txt_out
    assert "status: OK" in txt_out


def test_fastapi_health_single_and_batch_count() -> None:
    """FastAPI endpoints validate uploads and return item counts, gaps, and low-stock flags."""
    app = create_app()
    routes = {getattr(r, "path", ""): getattr(r, "endpoint", None) for r in app.routes}
    assert "/health" in routes
    assert "/v1/count" in routes
    assert "/v1/batch-count" in routes

    health_res = routes["/health"]()
    assert health_res["status"] == "ok"

    buf = io.BytesIO()
    _create_synthetic_shelf_photo().save(buf, format="PNG")
    png_bytes = buf.getvalue()

    upload_single = UploadFile(filename="aisle1.png", file=io.BytesIO(png_bytes), headers={"content-type": "image/png"})
    body = routes["/v1/count"](file=upload_single, low_stock_threshold=6)
    assert body["count"] == 5
    assert body["low_stock"] is True
    assert len(body["gaps"]) == 1

    u1 = UploadFile(filename="s1.png", file=io.BytesIO(png_bytes), headers={"content-type": "image/png"})
    u2 = UploadFile(filename="s2.png", file=io.BytesIO(png_bytes), headers={"content-type": "image/png"})
    batch_body = routes["/v1/batch-count"](files=[u1, u2], low_stock_threshold=4)
    assert batch_body["total_images"] == 2
    assert batch_body["total_items"] == 10
    assert batch_body["low_stock_shelves"] == 0

    # Reject non-image uploads with 415.
    bad_upload = UploadFile(filename="notes.txt", file=io.BytesIO(b"not an image"), headers={"content-type": "text/plain"})
    try:
        _read_validated_image(bad_upload)
        assert False, "Expected HTTPException for unsupported MIME type"
    except HTTPException as exc:
        assert exc.status_code == 415

