import logging

from .engine import EngineMixin
from .events import EventDecisionMixin

class DecisionModule(EngineMixin, EventDecisionMixin):

    def __init__(self, config: dict, vision_module):
        self.config = config
        self.vision = vision_module
        self.logger = logging.getLogger(__name__)

        self.energy_low = config["thresholds"]["energy_low"]
        self.energy_training = config["thresholds"]["energy_training"]
        self.rainbow_energy_min = config["thresholds"]["rainbow_energy_min"]
        self.mood_threshold = config["thresholds"]["mood_threshold"]

        self.targets = config["training_targets"]
        self.tolerance = self.targets["tolerance"]
        self.stat_priority = config["stat_priority"]
