from pubsub import StateChangeEventBase


class TaskCreatedStateChangeEvent(StateChangeEventBase):
    """TaskCreatedStateChangeEvent is a type for task created events"""


class TaskUpdatedStateChangeEvent(StateChangeEventBase):
    """TaskUpdatedStateChangeEvent is a type for task updated events"""


class UserCreatedStateChangeEvent(StateChangeEventBase):
    """UserCreatedStateChangeEvent is a type for user created events"""
