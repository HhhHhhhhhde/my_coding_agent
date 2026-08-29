from calculator import add, abs


def test_add() -> None:
    assert add(2, 3) == 5

def test_add1() -> None:
    assert abs(3) == 3