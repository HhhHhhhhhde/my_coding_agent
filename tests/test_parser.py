from mini_agent.parser import parse_action


def test_parse_valid_action() -> None:
    result = parse_action('{"thought":"inspect","action":{"tool":"list_dir","args":{"path":"."}}}')

    assert result.ok
    assert result.action is not None
    assert result.action.tool == "list_dir"
    assert result.action.args == {"path": "."}


def test_parse_invalid_json() -> None:
    result = parse_action("not json")

    assert not result.ok
    assert result.error_type == "InvalidJson"


def test_parse_repairs_missing_trailing_object_delimiter() -> None:
    result = parse_action(
        '{"thought":"write","action":{"tool":"write_file","args":{"path":"x.py","content_lines":["value = 1"]}}'
    )

    assert result.ok
    assert result.action is not None
    assert result.action.tool == "write_file"
    assert result.action.args == {"path": "x.py", "content_lines": ["value = 1"]}


def test_parse_requires_thought() -> None:
    result = parse_action('{"action":{"tool":"list_dir","args":{}}}')

    assert not result.ok
    assert result.error_type == "InvalidThought"
