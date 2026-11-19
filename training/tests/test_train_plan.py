"""Tests for the epoch plan that keeps a Kaggle run inside the free weekly GPU quota."""
import pytest

from train import plan_epochs


def test_plan_never_goes_below_the_minimum() -> None:
    """A slow GPU still gets the 12 epochs the schedule needs; the budget is reported, not obeyed blindly."""
    assert plan_epochs(images_per_second=2.0, num_images=6000, budget_seconds=10800, reserve_seconds=2160, min_epochs=12, max_epochs=20) == 12


def test_plan_caps_at_the_maximum_and_uses_the_budget() -> None:
    """6 images/s on 6000 images fits (10800-2160)*6/6000 = 8 epochs, clamped up; 20/s fits 28, clamped down."""
    assert plan_epochs(6.0, 6000, 10800, 2160, 12, 20) == 12
    assert plan_epochs(20.0, 6000, 10800, 2160, 12, 20) == 20
    # 11 images/s -> (8640 * 11) / 6000 = 15.8 -> 15 epochs inside the budget.
    assert plan_epochs(11.0, 6000, 10800, 2160, 12, 20) == 15


def test_plan_handles_nonsense_input() -> None:
    """Zero speed or zero images must not divide by zero."""
    assert plan_epochs(0.0, 6000, 10800, 2160, 12, 20) == 12
    assert plan_epochs(5.0, 0, 10800, 2160, 12, 20) == 12
