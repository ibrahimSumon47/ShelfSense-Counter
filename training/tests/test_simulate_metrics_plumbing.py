"""Plumbing check for the metric code using SIMULATED predictions.

Everything here is synthetic. `simulate_predictions` perturbs ground-truth boxes, so the
numbers it yields say nothing about any model. It exists only to prove that
`evaluate_predictions` handles perfect, partial and empty inputs. It must never be
imported by training or reporting code (a guard test in step 5 enforces this).
"""
import random

from shelfsense_training.metrics import DetectionBox, ImageEvalInput, evaluate_predictions


def simulate_predictions(gt: tuple[DetectionBox, ...], keep: float, seed: int) -> tuple[DetectionBox, ...]:
    """Keep a random fraction of ground-truth boxes. Synthetic, for plumbing tests only."""
    rng = random.Random(seed)
    return tuple(b for b in gt if rng.random() < keep)


def _grid(n: int) -> tuple[DetectionBox, ...]:
    return tuple(DetectionBox(i * 12.0, 0.0, i * 12.0 + 10.0, 20.0, 1.0) for i in range(n))


def test_simulated_perfect_input_scores_one() -> None:
    gt = _grid(30)
    item = ImageEvalInput("a", gt, simulate_predictions(gt, keep=1.0, seed=1))
    assert evaluate_predictions([item]).map50 == 1.0


def test_simulated_empty_predictions_score_zero() -> None:
    gt = _grid(30)
    item = ImageEvalInput("a", gt, simulate_predictions(gt, keep=0.0, seed=1))
    summary = evaluate_predictions([item])
    assert summary.map50 == 0.0
    assert summary.count_mae == 30.0
