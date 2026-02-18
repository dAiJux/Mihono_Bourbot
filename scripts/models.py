from enum import Enum

class GameScreen(Enum):
    MAIN = "main"
    TRAINING = "training"
    INSPIRATION = "inspiration"
    EVENT = "event"
    RACE = "race"
    RACE_SELECT = "race_select"
    RACE_RESULT = "race_result"
    STRATEGY = "strategy"
    UNITY = "unity"
    CAREER_COMPLETE = "career_complete"
    UNKNOWN = "unknown"

class Action(Enum):
    RACE = "race"
    INFIRMARY = "infirmary"
    RAINBOW_TRAINING = "rainbow_training"
    REST = "rest"
    RECREATION = "recreation"
    TRAINING = "training"
    UNITY_CUP = "unity_cup"
    SKIP = "skip"
    COMPLETE = "complete"
