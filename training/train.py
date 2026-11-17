"""Training entrypoint for ShelfSense (NOT IMPLEMENTED YET).

An earlier version of this file contained a random-weight ONNX generator and a
function that faked detections by jittering ground-truth boxes. Both were removed:
they produced numbers that did not come from a trained model (see docs/LESSONS.md).

Real training (a COCO-pretrained detector fine-tuned on shelf data, run on a GPU)
is tracked in docs/features.json (S2-02 onwards). Until it exists this script
refuses to run so nothing can be mistaken for a measured result.
"""
from __future__ import annotations

import sys


def main() -> int:
    """Exit with a clear message instead of producing any metric or model file."""
    print(
        "training/train.py: real training is not implemented yet. "
        "No model, metric or ONNX file is produced. See docs/HANDOFF.md.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
