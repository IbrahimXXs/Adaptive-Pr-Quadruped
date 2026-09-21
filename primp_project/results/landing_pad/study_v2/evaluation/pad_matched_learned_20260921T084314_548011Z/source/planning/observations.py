"""The explicit information boundary between execution and landing planners.

Only these measured quantities and an initial height estimate enter planning.
In particular, observations cannot contain MuJoCo objects or evaluation heights.
"""

from collections import deque
from dataclasses import dataclass, field, replace

import numpy as np


def immutable_array(value, shape, dtype=float):
    array = np.asarray(value, dtype=dtype)
    if array.shape != shape or not np.all(np.isfinite(array)):
        raise ValueError(f"Expected finite array with shape {shape}, got {array.shape}")
    # Bytes-backed arrays cannot be made writable by toggling setflags either.
    return np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(shape)


@dataclass(frozen=True)
class SensorObservation:
    time_s: float
    com_position: np.ndarray
    com_velocity: np.ndarray
    body_rpy: np.ndarray
    foot_position: np.ndarray
    foot_velocity: np.ndarray
    contacts: np.ndarray
    normal_forces: np.ndarray
    support_anchors: np.ndarray
    measurement_time_s: float | None = None

    def __post_init__(self):
        for name in ("com_position", "com_velocity", "body_rpy", "foot_position", "foot_velocity"):
            object.__setattr__(self, name, immutable_array(getattr(self, name), (3,)))
        object.__setattr__(self, "contacts", immutable_array(self.contacts, (4,), bool))
        object.__setattr__(self, "normal_forces", immutable_array(self.normal_forces, (4,)))
        object.__setattr__(self, "support_anchors", immutable_array(self.support_anchors, (3, 3)))
        if not np.isfinite(self.time_s) or np.any(self.normal_forces < 0):
            raise ValueError("Observation time must be finite and normal forces nonnegative")
        measured = self.time_s if self.measurement_time_s is None else self.measurement_time_s
        if not np.isfinite(measured) or measured > self.time_s + 1e-9:
            raise ValueError("Measurement time cannot be later than delivery time")
        object.__setattr__(self, "measurement_time_s", float(measured))


@dataclass(frozen=True)
class LandingContext:
    initial_height_estimate: float
    foot_radius: float
    start_time_s: float
    start_foot_position: np.ndarray
    start_com_position: np.ndarray
    target_xy: np.ndarray
    nominal_duration_s: float = 4.0
    max_search_depth: float = .02
    search_speed: float = .005
    support_margin: float = .02
    support_height_estimate: float = 0.0
    start_body_rpy: np.ndarray = field(default_factory=lambda: np.zeros(3))
    max_foot_speed: float = .015
    max_com_speed: float = .008
    max_body_displacement: float = .012
    planning_dt: float = .05
    contact_compression_m: float = .004

    def __post_init__(self):
        for name, shape in (("start_foot_position", (3,)), ("start_com_position", (3,)),
                            ("target_xy", (2,)), ("start_body_rpy", (3,))):
            object.__setattr__(self, name, immutable_array(getattr(self, name), shape))
        scalars = (self.initial_height_estimate, self.foot_radius, self.start_time_s,
                   self.nominal_duration_s, self.max_search_depth, self.search_speed,
                   self.support_margin, self.support_height_estimate, self.max_foot_speed,
                   self.max_com_speed, self.max_body_displacement, self.planning_dt)
        if not np.all(np.isfinite(scalars)):
            raise ValueError("Landing context scalars must be finite")
        if min(self.foot_radius, self.nominal_duration_s, self.max_search_depth,
               self.search_speed, self.max_foot_speed, self.max_com_speed,
               self.max_body_displacement, self.planning_dt) <= 0 or self.support_margin < 0:
            raise ValueError("Landing context limits and duration must be positive")
        if not np.isfinite(self.contact_compression_m) or self.contact_compression_m < 0:
            raise ValueError("Contact compression allowance must be finite and nonnegative")

    @property
    def minimum_foot_z(self):
        return self.initial_height_estimate - self.max_search_depth + self.foot_radius-self.contact_compression_m


@dataclass(frozen=True)
class MotionReference:
    com_position: np.ndarray
    com_velocity: np.ndarray
    body_rpy: np.ndarray
    foot_position: np.ndarray
    foot_velocity: np.ndarray
    foot_acceleration: np.ndarray
    remaining_time_s: float

    def __post_init__(self):
        for name in ("com_position", "com_velocity", "body_rpy", "foot_position", "foot_velocity", "foot_acceleration"):
            object.__setattr__(self, name, immutable_array(getattr(self, name), (3,)))
        if not np.isfinite(self.remaining_time_s) or self.remaining_time_s < 0:
            raise ValueError("Remaining movement time must be finite and nonnegative")


@dataclass(frozen=True)
class SensorProfile:
    name: str = "clean"
    position_noise_m: float = 0.0
    force_noise_n: float = 0.0
    delay_s: float = 0.0
    seed: int = 0

    def __post_init__(self):
        if not np.all(np.isfinite([self.position_noise_m, self.force_noise_n, self.delay_s])):
            raise ValueError("Sensor bounds must be finite")
        if min(self.position_noise_m, self.force_noise_n, self.delay_s) < 0:
            raise ValueError("Sensor bounds cannot be negative")


SENSOR_PROFILES = {
    "clean": SensorProfile(),
    "nominal": SensorProfile("nominal"),
    "noisy_delayed": SensorProfile("noisy_delayed", .0005, .3, .04),
    "noisy": SensorProfile("noisy", .0005, .3, .04),
}


class SensorStream:
    """Apply reproducible bounded sensor errors to supplied measurements only."""

    def __init__(self, profile=SensorProfile()):
        self.profile = profile
        self.rng = np.random.default_rng(profile.seed)
        self.queue = deque()

    def observe(self, observation):
        p = self.profile
        noisy = replace(
            observation,
            com_position=observation.com_position + self.rng.uniform(-p.position_noise_m, p.position_noise_m, 3),
            foot_position=observation.foot_position + self.rng.uniform(-p.position_noise_m, p.position_noise_m, 3),
            normal_forces=np.maximum(0., observation.normal_forces + self.rng.uniform(-p.force_noise_n, p.force_noise_n, 4)),
        )
        self.queue.append(noisy)
        cutoff = observation.time_s - p.delay_s
        while len(self.queue) > 1 and self.queue[1].time_s <= cutoff + 1e-10:
            self.queue.popleft()
        delayed = self.queue[0]
        return replace(delayed, time_s=observation.time_s)
