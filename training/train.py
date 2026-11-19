"""One resumable training run for the ShelfSense detector.

Trains a COCO-pretrained, anchor-free `fcos_resnet50_fpn` (BSD-3-Clause, 32.06M parameters)
on a SKU-110K subset plus the CC0 Supermarket Shelves train split, then reports from the
exported ONNX file itself so the numbers describe exactly what ships.

Design rules that came out of the first, fragile runs:
  - A checkpoint is written every epoch and the best one separately, before any export or
    evaluation, so a crash later in the run never costs the training.
  - Export, evaluation and metrics writing are independent try/except blocks with their own
    `<block>-error.txt`, so one failing step still leaves the rest of the run reportable.
  - The epoch count comes from the images per second measured on the first 50 batches and a
    GPU-time budget, because Kaggle's free GPU is a weekly quota.
  - Thresholds for score and NMS are tuned on validation only, on the exported ONNX file.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR / "src") not in sys.path:
    sys.path.insert(0, str(_THIS_DIR / "src"))

import numpy as np
from PIL import Image

from shelfsense_training import data as ds
from shelfsense_training.coco_eval import coco_ap
from shelfsense_training.export import export_fcos_onnx, measure_cpu_latency, quantize_int8_dynamic
from shelfsense_training.metrics import (
    bootstrap_confidence_intervals,
    evaluate_by_density,
    evaluate_predictions,
)
from shelfsense_training.onnx_eval import (
    best_threshold_row,
    make_session,
    run_raw_candidates,
    sweep_thresholds,
    to_eval_inputs,
)

THROUGHPUT_BATCHES = 50


def write_json(path: Path, payload) -> None:
    """Writes indented JSON, creating the parent folder."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def record_error(output_dir: Path, block: str, exc_text: str) -> None:
    """Writes `<block>-error.txt` so a failure is visible without reading stdout."""
    (output_dir / f"{block}-error.txt").write_text(exc_text, encoding="utf-8")
    print(f"[{block}] FAILED, see {block}-error.txt:\n{exc_text.strip().splitlines()[-1]}")


def plan_epochs(
    images_per_second: float,
    num_images: int,
    budget_seconds: float,
    reserve_seconds: float,
    min_epochs: int,
    max_epochs: int,
) -> int:
    """Epochs that fit the GPU budget at the measured speed, clamped to [min_epochs, max_epochs].

    reserve_seconds covers validation passes, the ONNX export and the final evaluation.
    """
    if images_per_second <= 0 or num_images <= 0:
        return min_epochs
    affordable = int((budget_seconds - reserve_seconds) * images_per_second / num_images)
    return max(min_epochs, min(max_epochs, affordable))


def build_model(cfg: dict):
    """COCO-pretrained FCOS with the classification head swapped for background + item."""
    import torch
    from torchvision.models.detection import FCOS_ResNet50_FPN_Weights, fcos_resnet50_fpn
    from torchvision.models.detection.fcos import FCOSClassificationHead

    input_size = int(cfg["input_size"])
    model = fcos_resnet50_fpn(
        weights=FCOS_ResNet50_FPN_Weights.DEFAULT,
        min_size=input_size,
        max_size=input_size,
        detections_per_img=int(cfg.get("detections_per_img", 1000)),
        topk_candidates=int(cfg.get("topk_candidates", 1500)),
        score_thresh=float(cfg.get("score_thresh", 0.25)),
        nms_thresh=float(cfg.get("nms_thresh", 0.45)),
    )
    model.head.classification_head = FCOSClassificationHead(
        in_channels=model.backbone.out_channels,
        num_anchors=model.head.classification_head.num_anchors,
        num_classes=2,
    )
    return model


def load_batch(samples, indices, input_size: int, device, torch):
    """Loads a batch of (image tensor in [0, 1], targets) pairs, skipping annotation-free images."""
    images = []
    targets = []
    for idx in indices:
        path, ann = samples[int(idx)]
        with Image.open(path) as raw:
            rgb = raw.convert("RGB").resize((input_size, input_size), Image.Resampling.BILINEAR)
            orig_w, orig_h = raw.size
        arr = np.asarray(rgb, dtype=np.float32) / 255.0
        image_t = torch.from_numpy(np.transpose(arr, (2, 0, 1)).copy()).to(device)
        sx, sy = input_size / max(1.0, float(orig_w)), input_size / max(1.0, float(orig_h))
        boxes = [
            [b.x1 * sx, b.y1 * sy, b.x2 * sx, b.y2 * sy]
            for b in ann.boxes
            if (b.x2 - b.x1) * sx >= 2.0 and (b.y2 - b.y1) * sy >= 2.0
        ]
        if not boxes:
            continue
        images.append(image_t)
        boxes_t = torch.tensor(boxes, dtype=torch.float32, device=device)
        targets.append({"boxes": boxes_t, "labels": torch.ones((boxes_t.shape[0],), dtype=torch.int64, device=device)})
    return images, targets


def run_torch_inference(model, samples, input_size: int, device, torch):
    """Runs the PyTorch model over samples and returns evaluation inputs in original pixels."""
    model.eval()
    eval_inputs = []
    with torch.no_grad():
        for path, ann in samples:
            with Image.open(path) as raw:
                orig_w, orig_h = raw.size
                rgb = raw.convert("RGB").resize((input_size, input_size), Image.Resampling.BILINEAR)
            arr = np.asarray(rgb, dtype=np.float32) / 255.0
            image_t = torch.from_numpy(np.transpose(arr, (2, 0, 1)).copy()).to(device)
            out = model([image_t])[0]
            boxes = out["boxes"].detach().cpu().numpy()
            scores = out["scores"].detach().cpu().numpy()
            sx, sy = float(orig_w) / input_size, float(orig_h) / input_size
            preds = tuple(
                ds_box(b[0] * sx, b[1] * sy, b[2] * sx, b[3] * sy, s) for b, s in zip(boxes, scores)
            )
            gts = tuple(ds_box(b.x1, b.y1, b.x2, b.y2, 1.0) for b in ann.boxes)
            eval_inputs.append(eval_input(name=ann.image_name, gt=gts, preds=preds))
    return eval_inputs


def ds_box(x1, y1, x2, y2, score):
    """Small wrapper so the imports at the top stay readable."""
    from shelfsense_training.metrics import DetectionBox

    return DetectionBox(float(x1), float(y1), float(x2), float(y2), float(score))


def eval_input(name, gt, preds):
    """Small wrapper so the imports at the top stay readable."""
    from shelfsense_training.metrics import ImageEvalInput

    return ImageEvalInput(name, gt, preds)


def summary_block(eval_inputs) -> dict:
    """AP from pycocotools at a 1000-detection cap plus count error, bootstrap interval and buckets."""
    summary = evaluate_predictions(eval_inputs)
    coco = coco_ap(eval_inputs, max_dets=1000)
    return {
        "num_images": summary.num_images,
        "map50": coco["map50"],
        "map50_95": coco["map"],
        "count_mae": summary.count_mae,
        "count_mape_pct": summary.count_mape_pct,
        "gt_count_total": coco["num_gt"],
        "pred_count_total": coco["num_dt"],
        "evaluated_once": True,
        "bootstrap_95_ci": bootstrap_confidence_intervals(eval_inputs, n_resamples=500, seed=42),
        "by_density": {
            name: {
                "num_images": value.num_images,
                "map50": value.map50,
                "count_mae": value.count_mae,
                "count_mape_pct": value.count_mape_pct,
            }
            for name, value in evaluate_by_density(eval_inputs).items()
        },
        "per_image": [
            {
                "image_id": item.image_id,
                "gt_count": len(item.ground_truth),
                "pred_count": len(item.predictions),
                "abs_error": abs(len(item.predictions) - len(item.ground_truth)),
            }
            for item in eval_inputs
        ],
    }


def save_predictions(path: Path, eval_inputs, params: dict, model_file: str) -> dict:
    """Writes gzipped prediction boxes so anyone can recompute the reported numbers."""
    import gzip

    payload = {
        "model_file": model_file,
        "params": params,
        "images": [
            {
                "image_id": item.image_id,
                "ground_truth": [[round(b.x1, 3), round(b.y1, 3), round(b.x2, 3), round(b.y2, 3)] for b in item.ground_truth],
                "predictions": [
                    [round(b.x1, 3), round(b.y1, 3), round(b.x2, 3), round(b.y2, 3), round(float(b.score), 5)]
                    for b in item.predictions
                ],
            }
            for item in eval_inputs
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(filename=str(path), mode="wb", mtime=0) as fh:
        fh.write(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return {"path": str(path), "size_bytes": path.stat().st_size}


def train(config_path: Path, cc0_dir: Path, sku_dir: Path, output_dir: Path, resume: bool, eval_test_once: bool) -> dict:
    """Runs the whole pipeline and returns the report. Each late step is independently guarded."""
    import torch

    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    run_id = cfg["run_id"]
    input_size = int(cfg["input_size"])
    output_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir = output_dir / "checkpoints"
    ckpt_dir.mkdir(exist_ok=True)

    seed = int(cfg.get("seed", 42))
    torch.manual_seed(seed)
    np.random.seed(seed)
    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    gpu_name = torch.cuda.get_device_name(0) if use_cuda else "CPU"
    if use_cuda:
        torch.backends.cudnn.benchmark = True
    print(f"[{run_id}] device={device} gpu={gpu_name}")

    # --- Data -------------------------------------------------------------------------
    cc0_items = ds.load_cc0_supermarket(cc0_dir)
    if not cc0_items:
        raise RuntimeError(f"CC0 Supermarket Shelves not found under {cc0_dir}")
    cc0_train, cc0_val, cc0_test, cc0_leaks = ds.split_cc0(cc0_items)
    sku_train = ds.load_sku110k_split(sku_dir, "train", int(cfg["sku110k_train_subset"]))
    sku_val = ds.load_sku110k_split(sku_dir, "val", int(cfg["sku110k_val_subset"]))
    sku_test = ds.load_sku110k_split(sku_dir, "test", int(cfg["sku110k_test_subset"]))
    train_samples = cc0_train + sku_train
    print(
        f"[{run_id}] train={len(train_samples)} (cc0={len(cc0_train)} sku110k={len(sku_train)}) "
        f"val_cc0={len(cc0_val)} val_sku110k={len(sku_val)} test_sku110k={len(sku_test)}",
        flush=True,
    )
    if len(sku_train) < 1000:
        print(f"[{run_id}] WARNING: only {len(sku_train)} SKU-110K training images were found", flush=True)

    # --- Model, optimiser, AMP --------------------------------------------------------
    model = build_model(cfg).to(device)
    total_params = sum(p.numel() for p in model.parameters())
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=float(cfg["learning_rate"]),
        weight_decay=float(cfg["weight_decay"]),
    )
    amp_enabled = bool(cfg.get("amp", True)) and use_cuda
    scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled)
    batch_size = int(cfg.get("batch_size", 8))
    validate_every = int(cfg.get("validate_every", 2))
    budget = float(cfg.get("gpu_budget_seconds", 10800))
    reserve = round(budget * 0.2)

    state = {
        "run_id": run_id,
        "config": cfg,
        "gpu_name": gpu_name,
        "total_parameters": total_params,
        "amp": amp_enabled,
        "loss_curve": [],
        "val_history": [],
        "images_per_second": None,
        "planned_epochs": None,
        "planned_epochs_reason": None,
        "best": None,
        "start_epoch": 1,
    }
    start_epoch = 1
    last_path = ckpt_dir / "last.pt"
    if resume and last_path.is_file():
        checkpoint = torch.load(last_path, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        scaler.load_state_dict(checkpoint["scaler"])
        start_epoch = int(checkpoint["epoch"]) + 1
        for key in ("loss_curve", "val_history", "images_per_second", "planned_epochs", "planned_epochs_reason", "best"):
            if key in checkpoint:
                state[key] = checkpoint[key]
        print(f"[{run_id}] resumed from {last_path.name} at epoch {start_epoch}", flush=True)

    planned = int(state["planned_epochs"] or cfg.get("min_epochs", 12))
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, planned), eta_min=float(cfg["learning_rate"]) * 0.05)
    rng = np.random.default_rng(seed)

    def save_checkpoint(epoch: int, tag: str) -> Path:
        """Writes model + optimiser + AMP scaler + history so a lost session can resume."""
        payload = {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "scaler": scaler.state_dict(),
            "epoch": epoch,
            "config": cfg,
            "loss_curve": state["loss_curve"],
            "val_history": state["val_history"],
            "images_per_second": state["images_per_second"],
            "planned_epochs": planned,
            "planned_epochs_reason": state["planned_epochs_reason"],
            "best": state["best"],
            "rng": rng.bit_generator.state,
        }
        target = ckpt_dir / f"{tag}.pt"
        torch.save(payload, target)
        return target

    # --- Training ---------------------------------------------------------------------
    train_started = time.perf_counter()
    for epoch in range(start_epoch, planned + 1):
        model.train()
        order = rng.permutation(len(train_samples))
        epoch_losses: list[float] = []
        epoch_started = time.perf_counter()
        images_done = 0
        for batch_index, offset in enumerate(range(0, len(order), batch_size)):
            images, targets = load_batch(train_samples, order[offset : offset + batch_size], input_size, device, torch)
            if not images:
                continue
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=amp_enabled):
                loss_dict = model(images, targets)
                loss = sum(loss_dict.values())
            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=10.0)
            scaler.step(optimizer)
            scaler.update()
            epoch_losses.append(float(loss.detach().item()))
            images_done += len(images)

            # Measure real training speed once, then fix the epoch count to the GPU budget.
            if state["planned_epochs"] is None and batch_index + 1 >= THROUGHPUT_BATCHES:
                elapsed = time.perf_counter() - epoch_started
                state["images_per_second"] = round(images_done / elapsed, 2)
                planned = plan_epochs(
                    state["images_per_second"],
                    len(train_samples),
                    budget,
                    reserve,
                    int(cfg.get("min_epochs", 12)),
                    int(cfg.get("max_epochs", 20)),
                )
                state["planned_epochs"] = planned
                state["planned_epochs_reason"] = (
                    f"{state['images_per_second']} images/s measured on {images_done} images in the first "
                    f"{THROUGHPUT_BATCHES} batches; ({budget:.0f}s budget - {reserve}s reserve) * "
                    f"{state['images_per_second']} / {len(train_samples)} images = "
                    f"{int((budget - reserve) * state['images_per_second'] / max(1, len(train_samples)))} epochs, "
                    f"clamped to [{cfg.get('min_epochs', 12)}, {cfg.get('max_epochs', 20)}]"
                )
                scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                    optimizer, T_max=max(1, planned), eta_min=float(cfg["learning_rate"]) * 0.05
                )
                for _ in range(epoch - 1):
                    scheduler.step()
                print(f"[{run_id}] {state['planned_epochs_reason']}", flush=True)

        scheduler.step()
        epoch_seconds = round(time.perf_counter() - epoch_started, 1)
        mean_loss = round(float(np.mean(epoch_losses)), 4) if epoch_losses else 0.0
        state["loss_curve"].append(
            {"epoch": epoch, "mean_loss": mean_loss, "num_batches": len(epoch_losses), "seconds": epoch_seconds}
        )
        print(
            f"[{run_id}] epoch {epoch}/{planned} loss={mean_loss} batches={len(epoch_losses)} "
            f"lr={optimizer.param_groups[0]['lr']:.6f} {epoch_seconds}s",
            flush=True,
        )
        # Checkpoint before any validation or export so the weights can never be lost.
        save_checkpoint(epoch, f"epoch-{epoch:02d}")
        save_checkpoint(epoch, "last")
        write_json(output_dir / "run-state.json", state)

        should_validate = epoch % validate_every == 0 or epoch == planned
        if not should_validate:
            continue
        try:
            val_sku = run_torch_inference(model, sku_val, input_size, device, torch) if sku_val else []
            val_cc0 = run_torch_inference(model, cc0_val, input_size, device, torch) if cc0_val else []
            entry = {"epoch": epoch}
            if val_sku:
                entry["val_sku110k_map50"] = evaluate_predictions(val_sku).map50
            if val_cc0:
                entry["val_cc0_map50"] = evaluate_predictions(val_cc0).map50
            primary = entry.get("val_sku110k_map50", entry.get("val_cc0_map50", 0.0))
            entry["primary_map50"] = primary
            state["val_history"].append(entry)
            if state["best"] is None or primary > float(state["best"]["primary_map50"]):
                state["best"] = {"epoch": epoch, "primary_map50": primary, "checkpoint": f"best.pt"}
                save_checkpoint(epoch, "best")
                print(f"[{run_id}] new best at epoch {epoch} (map50={primary})", flush=True)
            write_json(output_dir / "run-state.json", state)
        except Exception:
            record_error(output_dir, "validation", traceback.format_exc())
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    train_seconds = round(time.perf_counter() - train_started, 1)
    if state["best"] is None:
        # No validation pass ran (very short run); the last checkpoint is the best available.
        save_checkpoint(planned, "best")
        state["best"] = {"epoch": planned, "primary_map50": None, "checkpoint": "best.pt"}
    write_json(output_dir / "run-state.json", state)
    print(f"[{run_id}] training finished in {train_seconds}s", flush=True)

    report = {
        "run_id": run_id,
        "framework": cfg["framework"],
        "license": cfg["license"],
        "gpu_name": gpu_name,
        "total_parameters": total_params,
        "config": cfg,
        "amp": amp_enabled,
        "timings": {
            "train_seconds": train_seconds,
            "images_per_second": state["images_per_second"],
            "planned_epochs": planned,
            "planned_epochs_reason": state["planned_epochs_reason"],
            "gpu_budget_seconds": budget,
            "reserve_seconds": reserve,
        },
        "data": {
            "train_images_total": len(train_samples),
            "cc0_split_counts": {"train": len(cc0_train), "val": len(cc0_val), "test": len(cc0_test)},
            "sku110k_loaded_counts": {"train": len(sku_train), "val": len(sku_val), "test": len(sku_test)},
            "cross_split_dhash_leaks": cc0_leaks,
        },
        "loss_curve": state["loss_curve"],
        "val_history": state["val_history"],
        "best_checkpoint": state["best"],
    }
    write_json(output_dir / "metrics.json", report)

    # --- Export (independent try/except) ---------------------------------------------
    checkpoint_path = ckpt_dir / "best.pt"
    export_info = None
    try:
        state_dict = torch.load(checkpoint_path, map_location="cpu", weights_only=False)["model"]
        model.load_state_dict(state_dict)
        fp32_path = output_dir / f"{run_id}-fp32.onnx"
        export_info = export_fcos_onnx(model, fp32_path, input_size)
        export_info["checkpoint"] = checkpoint_path.name
        export_info["checkpoint_epoch"] = state["best"]["epoch"]
        export_info["cpu_latency_ms"] = measure_cpu_latency(fp32_path, input_size)
        int8_path = output_dir / f"{run_id}-int8.onnx"
        export_info["int8"] = quantize_int8_dynamic(fp32_path, int8_path)
        if export_info["int8"]:
            export_info["int8"]["cpu_latency_ms"] = measure_cpu_latency(int8_path, input_size)
        report["onnx"] = export_info
        write_json(output_dir / "metrics.json", report)
        print(f"[{run_id}] exported {fp32_path.name}", flush=True)
    except Exception:
        record_error(output_dir, "export", traceback.format_exc())

    # --- Evaluation (independent try/except), from the exported ONNX files ------------
    try:
        if not export_info:
            raise RuntimeError("no ONNX export to evaluate; see export-error.txt")
        onnx_paths = [output_dir / export_info["path"]]
        if export_info.get("int8"):
            onnx_paths.append(output_dir / export_info["int8"]["path"])

        evaluations: dict[str, dict] = {}
        tuned_thresholds = {
            "score_thresh": float(cfg["score_thresh"]),
            "nms_thresh": float(cfg["nms_thresh"]),
            "max_dets": int(cfg["detections_per_img"]),
        }
        sweep_rows: list[dict] = []

        # Tune on SKU-110K validation only (200 images), on the FP32 file.
        fp32_session = make_session(onnx_paths[0])
        cached_val_sku = run_raw_candidates(fp32_session, sku_val, input_size, normalise=False) if sku_val else []
        if sku_val:
            sweep_rows = sweep_thresholds(
                sku_val,
                cached_val_sku,
                input_size,
                cfg.get("score_grid", [0.25]),
                cfg.get("nms_grid", [0.45]),
                int(cfg["detections_per_img"]),
            )
            best = best_threshold_row(sweep_rows)
            tuned_thresholds = {
                "score_thresh": best["score_thresh"],
                "nms_thresh": best["nms_thresh"],
                "max_dets": best["max_dets"],
                "tuned_on": f"sku110k val ({len(sku_val)} images)",
            }
            print(f"[{run_id}] tuned thresholds {tuned_thresholds}", flush=True)

        report["thresholds"] = tuned_thresholds
        report["threshold_sweep_sku110k_val"] = sweep_rows

        slices = [("val_sku110k", sku_val), ("val_cc0", cc0_val)]
        if eval_test_once:
            slices += [("test_sku110k_once", sku_test), ("test_cc0_once", cc0_test)]
        for path in onnx_paths:
            session = make_session(path)
            key_tag = "int8" if "int8" in path.name else "fp32"
            evaluations[key_tag] = {"onnx_file": path.name}
            for name, samples in slices:
                if not samples:
                    continue
                cached = run_raw_candidates(session, samples, input_size, normalise=False)
                eval_inputs = to_eval_inputs(
                    samples,
                    cached,
                    input_size,
                    tuned_thresholds["score_thresh"],
                    tuned_thresholds["nms_thresh"],
                    tuned_thresholds["max_dets"],
                )
                block = summary_block(eval_inputs)
                if name.startswith("test_"):
                    block["predictions_file"] = save_predictions(
                        output_dir / "predictions" / f"{run_id}-{key_tag}-{name}.json.gz",
                        eval_inputs,
                        tuned_thresholds,
                        path.name,
                    )
                evaluations[key_tag][name] = block
                print(f"[{run_id}] {key_tag} {name} map50={block['map50']} mae={block['count_mae']}", flush=True)
        report["evaluations"] = evaluations
        # Keep the FP32 slice at the top level too: it is the model the card describes.
        if "fp32" in evaluations:
            for name in ("val_sku110k", "val_cc0", "test_sku110k_once", "test_cc0_once"):
                if name in evaluations["fp32"]:
                    report[name] = evaluations["fp32"][name]
        write_json(output_dir / "metrics.json", report)
    except Exception:
        record_error(output_dir, "evaluation", traceback.format_exc())

    # --- Metrics writing (independent try/except) ------------------------------------
    try:
        report["finished_at_unix"] = int(time.time())
        write_json(output_dir / "metrics.json", report)
        print(f"[{run_id}] wrote metrics.json", flush=True)
    except Exception:
        record_error(output_dir, "metrics", traceback.format_exc())

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resumable FCOS training run for ShelfSense.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cc0-dir", type=Path, required=True)
    parser.add_argument("--sku-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--eval-test-once", action="store_true")
    args = parser.parse_args(argv)

    train(args.config, args.cc0_dir, args.sku_dir, args.output_dir, args.resume, args.eval_test_once)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
