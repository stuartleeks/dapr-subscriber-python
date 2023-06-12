from .consumer_app import ConsumerApp, StateChangeEventBase


class SampleEvent1StateChangeEvent(StateChangeEventBase):
    def __init__(self, entity_id: str):
        super().__init__(entity_type="sample", new_state="event1", entity_id=entity_id)

    def from_dict(self, data: dict):
        return SampleEvent1StateChangeEvent(data["entity_id"])


class SampleMultiPartEventStateChangeEvent(StateChangeEventBase):
    def __init__(self, entity_id: str):
        super().__init__(entity_type="sample", new_state="multi-part-event", entity_id=entity_id)

    def from_dict(self, data: dict):
        return SampleEvent1StateChangeEvent(data["entity_id"])


def test_get_topic_name_simple():
    def on_task_created():
        pass

    topic_name = ConsumerApp._get_topic_name_from_method(on_task_created)
    assert topic_name == "task-created"


def test_get_topic_name_extended():
    def on_task_in_progress():
        pass

    topic_name = ConsumerApp._get_topic_name_from_method(on_task_in_progress)
    assert topic_name == "task-in-progress"


def test_get_topic_name_from_class_simple():
    topic_name = ConsumerApp._get_topic_name_from_event_class(SampleEvent1StateChangeEvent)
    assert topic_name == "sample-event1"


def test_get_topic_name_from_class_extended():
    topic_name = ConsumerApp._get_topic_name_from_event_class(SampleMultiPartEventStateChangeEvent)
    assert topic_name == "sample-multi-part-event"


def test_event_classes_discovered():
    app = ConsumerApp(default_subscription_name="test-subscription")
    assert app._topic_to_event_class_map.get("sample-event1") == SampleEvent1StateChangeEvent
    assert app._topic_to_event_class_map.get("sample-multi-part-event") == SampleMultiPartEventStateChangeEvent


def test_get_event_class_for_method_simple():
    def on_sample_event1():
        pass

    app = ConsumerApp(default_subscription_name="test-subscription")
    event_class = app._get_event_class_from_method(on_sample_event1)
    assert event_class == SampleEvent1StateChangeEvent


def test_get_event_class_for_method_extended():
    def on_sample_multi_part_event():
        pass

    app = ConsumerApp(default_subscription_name="test-subscription")
    event_class = app._get_event_class_from_method(on_sample_multi_part_event)
    assert event_class == SampleMultiPartEventStateChangeEvent
