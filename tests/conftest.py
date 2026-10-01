from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def fake_clock():
    return FakeClock()


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
