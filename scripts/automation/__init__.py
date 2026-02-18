import logging

from .clicks import ClickMixin
from .race import RaceMixin
from .training import TrainingMixin
from .events import EventMixin
from .unity import UnityMixin
from .navigation import NavigationMixin

class AutomationModule(
    ClickMixin, RaceMixin, TrainingMixin, EventMixin, UnityMixin, NavigationMixin
):

    def __init__(self, config: dict, vision_module, decision_module):
        self.config = config
        self.vision = vision_module
        self.decision = decision_module
        self.logger = logging.getLogger(__name__)
        self.click_offset_range = config["automation_settings"]["click_offset_range"]
        self.action_delay = (
            config["automation_settings"]["action_delay_min"],
            config["automation_settings"]["action_delay_max"],
        )
        self.first_race_done = False
        self.unity_round = 0
        self._event_db = {}
        self._last_selected_training = "speed"
        self._running_flag = None
        self._pause_event = None
