
from pubsub import StateChangeEventBase


class TaskStateChangeEventBase(StateChangeEventBase):
    """TaskStateChangeEvent is a base type for task state change events"""

    def __init__(self, new_state: str, entity_id: str,):
        super().__init__(entity_type="task", entity_id=entity_id, new_state=new_state)

    def __repr__(self) -> str:
        return f"TaskStateChangeEventBase(new_state={self._new_state}, entity_id={self._entity_id})"


class TaskCreatedStateChangeEvent(TaskStateChangeEventBase):
    """TaskCreatedStateChangeEvent is a type for task created events"""

    def __init__(self, entity_id: str):
        super().__init__(new_state="created", entity_id=entity_id)

    def from_dict(msg_dict: dict):
        return TaskCreatedStateChangeEvent(msg_dict["entity_id"])

    def __repr__(self) -> str:
        return f"TaskCreatedStateChangeEvent(entity_id={self._entity_id})"


class TaskUpdatedStateChangeEvent(TaskStateChangeEventBase):
    """TaskUpdatedStateChangeEvent is a type for task updated events"""

    def __init__(self, entity_id: str):
        super().__init__(new_state="updated", entity_id=entity_id)

    def from_dict(msg_dict: dict):
        return TaskUpdatedStateChangeEvent(msg_dict["entity_id"])

    def __repr__(self) -> str:
        return f"TaskUpdatedStateChangeEvent(entity_id={self._entity_id})"



class UserCreatedStateChangeEvent(StateChangeEventBase):
    """UserCreatedStateChangeEvent is a type for user created events"""

    def __init__(self, entity_id: str):
        super().__init__(entity_type="user", new_state="created", entity_id=entity_id)

    def from_dict(msg_dict: dict):
        return UserCreatedStateChangeEvent(msg_dict["entity_id"])

    def __repr__(self) -> str:
        return f"UserCreatedStateChangeEvent(entity_id={self._entity_id})"
