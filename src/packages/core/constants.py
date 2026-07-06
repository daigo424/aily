from enum import StrEnum


class ScheduleDraftStatus(StrEnum):
    COLLECTING = "collecting"
    READY = "ready"
    CONFIRMED = "confirmed"


class TaskStatus(StrEnum):
    NOT_STARTED = "not_started"
    DOING = "doing"
    DONE = "done"


class ScheduleItemType(StrEnum):
    EVENT = "event"
    TASK = "task"


class ConversationIntent(StrEnum):
    ADD_SCHEDULE = "add_schedule"
    LIST_SCHEDULE = "list_schedule"
    SMALLTALK = "smalltalk"
    UNKNOWN = "unknown"
