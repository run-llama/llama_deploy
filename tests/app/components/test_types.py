from llama_agents.app.components.types import ButtonType


def test_button_type_enum():
    # Test that the enum values are correctly assigned
    assert ButtonType.SERVICE == "Service"
    assert ButtonType.TASK == "Task"
    assert ButtonType.HUMAN == "Human"

    # Test that the enum names are correct
    assert ButtonType.SERVICE.name == "SERVICE"
    assert ButtonType.TASK.name == "TASK"
    assert ButtonType.HUMAN.name == "HUMAN"

    # Test that the enum values are instances of the correct type
    assert isinstance(ButtonType.SERVICE, ButtonType)
    assert isinstance(ButtonType.TASK, ButtonType)
    assert isinstance(ButtonType.HUMAN, ButtonType)

    # Test that the enum values are instances of str
    assert isinstance(ButtonType.SERVICE, str)
    assert isinstance(ButtonType.TASK, str)
    assert isinstance(ButtonType.HUMAN, str)


def test_button_type_members():
    members = list(ButtonType)
    assert len(members) == 3
    assert ButtonType.SERVICE in members
    assert ButtonType.TASK in members
    assert ButtonType.HUMAN in members
