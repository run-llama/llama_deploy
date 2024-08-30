from enum import Enum


class ButtonType(str, Enum):
    SERVICE = "Service"
    TASK = "Task"
    HUMAN = "Human"
