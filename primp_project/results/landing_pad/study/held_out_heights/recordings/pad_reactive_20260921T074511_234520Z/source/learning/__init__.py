"""PRIMP-based learning of coordinated quadruped landing motions."""

from .primp import MotionPrediction, PRIMPMotionModel, relative_features
from .data import fit_runs

__all__ = ["MotionPrediction", "PRIMPMotionModel", "relative_features", "fit_runs"]
