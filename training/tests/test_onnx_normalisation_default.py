"""Guards the normalisation contract between the exporter and the evaluator.

The exporter bakes ImageNet mean/std into the graph, so the numpy path must not normalise a
second time. That mistake made the 12-epoch run report mAP50 0.13 on SKU-110K validation while
the same weights scored 0.60 on CC0, and it is silent: both paths run without error.
"""
import inspect

from shelfsense_training.onnx_eval import run_raw_candidates


def test_numpy_normalisation_is_off_by_default() -> None:
    """A caller that forgets the flag must get the graph's own normalisation, not a second one."""
    assert inspect.signature(run_raw_candidates).parameters["normalise"].default is False
