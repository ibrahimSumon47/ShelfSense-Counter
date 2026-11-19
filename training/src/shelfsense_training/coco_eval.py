"""Official pycocotools average precision for the single-class shelf detector.

`max_dets` is applied the way a detector postprocessor applies it: keep only the
highest-scoring boxes of each image before matching. COCOeval's own `maxDets`
truncates the list too, so both are set to the same number and the number appears
in every report, because a cap of 100 silently limits counts on dense shelves.
"""
from __future__ import annotations

import contextlib
import io
from typing import Sequence

from shelfsense_training.metrics import ImageEvalInput


def coco_ap(inputs: Sequence[ImageEvalInput], max_dets: int = 1000) -> dict[str, float | int]:
    """Runs `pycocotools.cocoeval.COCOeval` (bbox, single class) and returns AP, AP50, AP75.

    Raises ImportError instead of falling back to a local approximation: a reported
    number must come from the official evaluator.
    """
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval

    images: list[dict[str, object]] = []
    annotations: list[dict[str, object]] = []
    detections: list[dict[str, object]] = []
    ann_id = 1
    for idx, item in enumerate(inputs):
        image_id = idx + 1
        width = max([b.x2 for b in item.ground_truth] + [1.0])
        height = max([b.y2 for b in item.ground_truth] + [1.0])
        images.append({"id": image_id, "file_name": item.image_id, "width": width, "height": height})
        for gt in item.ground_truth:
            w = max(1.0, gt.x2 - gt.x1)
            h = max(1.0, gt.y2 - gt.y1)
            annotations.append(
                {
                    "id": ann_id,
                    "image_id": image_id,
                    "category_id": 1,
                    "bbox": [gt.x1, gt.y1, w, h],
                    "area": w * h,
                    "iscrowd": 0,
                }
            )
            ann_id += 1
        # Sort by score and truncate, matching what the model's own postprocessor does.
        ranked = sorted(item.predictions, key=lambda b: b.score, reverse=True)[:max_dets]
        for pred in ranked:
            detections.append(
                {
                    "image_id": image_id,
                    "category_id": 1,
                    "bbox": [pred.x1, pred.y1, max(1.0, pred.x2 - pred.x1), max(1.0, pred.y2 - pred.y1)],
                    "score": float(pred.score),
                }
            )

    if not annotations or not detections:
        return {
            "map": 0.0,
            "map50": 0.0,
            "map75": 0.0,
            "max_dets": max_dets,
            "num_gt": len(annotations),
            "num_dt": len(detections),
        }

    with contextlib.redirect_stdout(io.StringIO()):
        gt = COCO()
        gt.dataset = {"images": images, "annotations": annotations, "categories": [{"id": 1, "name": "item"}]}
        gt.createIndex()
        dt = gt.loadRes(detections)
        evaluator = COCOeval(gt, dt, iouType="bbox")
        evaluator.params.maxDets = [max_dets, max_dets, max_dets]
        evaluator.evaluate()
        evaluator.accumulate()

    # COCOeval.summarize() always reports AP at maxDets=100, which it cannot find in a
    # params list that only holds 1000 and then returns -1. Read the precision array
    # directly at the cap we actually used, over all 10 IoU thresholds and the "all" area range.
    precision = evaluator.eval["precision"]  # (T, R, K, A, M)
    det_index = len(evaluator.params.maxDets) - 1
    per_iou = []
    for t in range(precision.shape[0]):
        values = precision[t, :, 0, 0, det_index]
        values = values[values > -1]
        per_iou.append(float(values.mean()) if values.size else 0.0)
    mean_over_thresholds = sum(per_iou) / len(per_iou) if per_iou else 0.0

    return {
        "map": round(mean_over_thresholds, 4),
        "map50": round(per_iou[0], 4),
        "map75": round(per_iou[5], 4),
        "max_dets": max_dets,
        "num_gt": len(annotations),
        "num_dt": len(detections),
    }
