"""Learn remaining recovery motion and physical time from successful windows.

Each training example begins at a measured state after missing contact and ends
at confirmed reload. Its context is measured foot-bottom clearance to the known
training surface. Online, the same clearance distribution is obtained from the
current measured foot height and a fixed terrain posterior. No exhausted global
phase or hand-written depth/speed timing law is used by this model.
"""

from dataclasses import replace
from pathlib import Path

import numpy as np

from .primp import PRIMPMotionModel


class RecoveryMotionModel:
    """A PRIMP distribution reanchored to the current measured body/foot pose."""

    def __init__(self, motion_model):
        self.motion_model = motion_model
        self.metadata = motion_model.metadata
        self.phase_points = motion_model.phase_points
        if self.metadata.get("context_variable") != "measured_clearance_to_surface_m":
            raise ValueError("Artifact is not a measured-clearance recovery model")

    @classmethod
    def fit(cls, features, clearances_m, remaining_durations_s, *, training_records=None,
            translation_noise_m=2e-5, rotation_noise_rad=2e-4):
        """Fit measured current-state→reload windows of shape [windows,K,9].

        Feature origins are each window's initial measured CoM, body rotation,
        and FL position. Labels are current measured foot bottom minus known
        surface height, and strictly positive time until confirmed reload.
        ``fit_recovery_runs`` supplies the demonstration-only provenance gate.
        """
        model = PRIMPMotionModel.fit(features, clearances_m, remaining_durations_s,
            training_records=training_records, translation_noise_m=translation_noise_m,
            rotation_noise_rad=rotation_noise_rad)
        model.metadata.update(
            model="PRIMP recovery windows with measured-clearance and remaining-duration contexts",
            context_variable="measured_clearance_to_surface_m",
            training_clearance_range_m=list(model.metadata["training_height_range_m"]),
            remaining_duration_range_s=list(model.metadata["training_duration_range_s"]),
            training_windows=len(features),
            duration_semantics="Positive physical time from current measured state to confirmed reload",
            reference_origins="Current measured CoM, body SO3 orientation, and FL position",
            posterior_semantics="Fixed terrain q(h); clearance=current measured foot bottom minus h; no training-prior reweighting")
        return cls(model)

    def condition_belief(self, heights, probabilities, *, current_foot_bottom_m):
        """Predict a fresh remaining motion and time from current measurements.

        The returned features are relative to the current measured body/foot
        origins; the caller reconstructs world references and enforces command
        continuity separately. ``duration_s`` is the posterior expectation of
        positive remaining duration, not a total duration minus elapsed phase.
        Unsupported posterior mass refers to the demonstrated clearance range.
        """
        if not np.isfinite(current_foot_bottom_m):
            raise ValueError("Current measured foot bottom must be finite")
        heights = np.asarray(heights, dtype=float)
        clearances = float(current_foot_bottom_m)-heights
        prediction = self.motion_model.condition_belief(clearances, probabilities,
                                                       current_phase=0., current_features=np.zeros(9))
        return replace(prediction, mixture_heights=heights.copy())

    def save(self, path):
        path = Path(path)
        if path.suffix != ".npz":
            path = path/"recovery.npz"
        return self.motion_model.save(path)

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.is_dir():
            path = path/"recovery.npz"
        return cls(PRIMPMotionModel.load(path))
