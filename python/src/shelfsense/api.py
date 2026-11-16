"""FastAPI batch service for ShelfSense shelf counting and gap detection."""
from __future__ import annotations

import io
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from PIL import Image, UnidentifiedImageError

from shelfsense import __version__
from shelfsense.detector import ShelfDetector

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB per image
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


def create_app(model_path: Path | str | None = None) -> FastAPI:
    """Creates the FastAPI application wired to a ShelfDetector instance."""
    resolved_model = model_path or os.environ.get("SHELFSENSE_MODEL_PATH")
    detector = ShelfDetector(model_path=resolved_model)

    app = FastAPI(
        title="ShelfSense Batch Counter API",
        version=__version__,
        description="Counts shelf products, finds empty row gaps, and flags low stock from uploaded photos.",
    )

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "version": __version__,
            "onnx_loaded": detector.session is not None,
        }

    @app.post("/v1/count")
    def count_single(
        file: UploadFile = File(...),
        low_stock_threshold: int = Query(default=10, ge=1, le=1000),
    ) -> dict:
        img = _read_validated_image(file)
        analysis = detector.analyze(img, low_stock_threshold=low_stock_threshold)
        payload = analysis.to_dict()
        payload["filename"] = file.filename or "upload.jpg"
        return payload

    @app.post("/v1/batch-count")
    def count_batch(
        files: list[UploadFile] = File(...),
        low_stock_threshold: int = Query(default=10, ge=1, le=1000),
    ) -> dict:
        if not files:
            raise HTTPException(status_code=400, detail="At least one image file is required.")
        if len(files) > 20:
            raise HTTPException(status_code=400, detail="Batch size cannot exceed 20 images per request.")

        results = []
        for upload in files:
            img = _read_validated_image(upload)
            analysis = detector.analyze(img, low_stock_threshold=low_stock_threshold)
            item = analysis.to_dict()
            item["filename"] = upload.filename or "upload.jpg"
            results.append(item)

        return {
            "total_images": len(results),
            "total_items": sum(r["count"] for r in results),
            "low_stock_shelves": sum(1 for r in results if r["low_stock"]),
            "results": results,
        }

    return app


def _read_validated_image(upload: UploadFile) -> Image.Image:
    """Validates MIME type, file size, and image decoding for an uploaded file."""
    if upload.content_type and upload.content_type.lower() not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type {upload.content_type!r}. Use JPEG, PNG, or WebP.",
        )
    raw = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 10 MB upload limit.")
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
        return img
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Invalid or corrupted image file.") from exc


app = create_app()
