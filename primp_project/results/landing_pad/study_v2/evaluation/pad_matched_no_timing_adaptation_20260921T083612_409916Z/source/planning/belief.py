"""One-dimensional contact/missing-contact Bayesian terrain estimation."""

import numpy as np
from scipy.special import ndtr


class GroundHeightBelief:
    """A bounded grid posterior over pad top height, in the world frame.

    Loaded contact supplies a noisy height measurement. An airborne foot supplies
    a censored observation: the surface lies below its measured underside.
    Repeated copies of an unchanged measurement are not independent evidence.
    """

    def __init__(self, context, *, prior_std=.007, observation_std=.001, grid_points=241,
                 noncontact_updates=True):
        self.context = context
        if prior_std <= 0 or observation_std <= 0 or grid_points < 3:
            raise ValueError("Belief resolution and uncertainty must be positive")
        self.observation_std = float(observation_std)
        self.noncontact_updates = bool(noncontact_updates)
        self.heights = np.linspace(context.initial_height_estimate-context.max_search_depth,
                                   context.initial_height_estimate+context.max_search_depth, grid_points)
        self.probability = np.exp(-.5*((self.heights-context.initial_height_estimate)/prior_std)**2)
        self.probability /= self.probability.sum()
        self.missing_contact = False
        self.contact_observed = False
        self.last_event = "initial_estimate"
        self.updates = 0
        self.last_measurement_time = -np.inf
        self.lowest_airborne_bottom = np.inf

    @property
    def mean(self):
        return float(self.probability @ self.heights)

    @property
    def std(self):
        return float(np.sqrt(self.probability @ (self.heights-self.mean)**2))

    def quantile(self, probability):
        if not 0 <= probability <= 1:
            raise ValueError("Quantile must lie in [0, 1]")
        return float(np.interp(probability, np.cumsum(self.probability), self.heights))

    def update(self, observation):
        measured_t = observation.measurement_time_s
        if measured_t <= self.last_measurement_time + 1e-10:
            return self
        bottom = float(observation.foot_position[2]-self.context.foot_radius)
        touching = bool(observation.contacts[0] and observation.normal_forces[0] >= .5)
        if observation.contacts[0] and not touching:
            self.last_event = "contact_pending_load"
            self.missing_contact = False
            return self
        if touching:
            if self.contact_observed and measured_t-self.last_measurement_time < .05-1e-10:
                return self
            likelihood = np.exp(-.5*((self.heights-bottom)/self.observation_std)**2)
            self.contact_observed = True
            self.missing_contact = False
            self.last_event = "contact"
        else:
            if bottom <= self.context.initial_height_estimate + .0005:
                self.missing_contact = True
            if not self.noncontact_updates:
                # This ablation removes only censored Bayesian evidence. The
                # missing-contact event, bounded search, and loaded-contact
                # confirmation remain available to the common executor.
                self.last_event = "missing_contact_no_update" if self.missing_contact else "airborne_no_update"
                self.last_measurement_time = measured_t
                self.lowest_airborne_bottom = min(self.lowest_airborne_bottom, bottom)
                return self
            # Condition once per newly reached depth; holding in the air does
            # not falsely collapse uncertainty through duplicated evidence.
            if bottom > self.lowest_airborne_bottom - .00025:
                return self
            likelihood = ndtr((bottom-self.heights)/self.observation_std)
            self.lowest_airborne_bottom = bottom
            self.last_event = "missing_contact" if self.missing_contact else "airborne"
        posterior = self.probability * np.maximum(likelihood, 1e-30)
        self.probability = posterior / posterior.sum()
        self.last_measurement_time = measured_t
        self.updates += 1
        return self

    def summary(self):
        return dict(mean=self.mean, std=self.std, lower=self.quantile(.05),
                    upper=self.quantile(.95), missing_contact=self.missing_contact,
                    contact_observed=self.contact_observed, updates=self.updates,
                    event=self.last_event)
