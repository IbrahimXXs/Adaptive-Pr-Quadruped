"""PRIMP-based learning of coordinated quadruped landing motions."""

from .primp import MotionPrediction, PRIMPMotionModel, relative_features
from .data import fit_runs, fit_recovery_runs
from .recovery import RecoveryMotionModel

__all__ = ["MotionPrediction", "PRIMPMotionModel", "RecoveryMotionModel", "relative_features", "fit_runs", "fit_recovery_runs"]
