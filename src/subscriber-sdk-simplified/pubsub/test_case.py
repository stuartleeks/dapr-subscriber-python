from .consumer_app import case


def test_pascal_to_kebab_case():
    assert case.pascal_to_kebab_case("TaskCreated") == "task-created"
    assert case.pascal_to_kebab_case("TaskInProgress") == "task-in-progress"

def test_snake_to_camel_case():
    assert case.snake_to_kebab_case("task_created") == "task-created"
    assert case.snake_to_kebab_case("task_in_progress") == "task-in-progress"
