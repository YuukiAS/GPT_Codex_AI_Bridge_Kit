from src.greeting import greet


def test_greet_trims_name() -> None:
    assert greet(" Ada ") == "Hello, Ada!"


def test_greet_empty_name() -> None:
    assert greet("   ") == "Hello, there!"
