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


@pytest.fixture(autouse=True)
def no_font_downloads(monkeypatch, tmp_path):
    """Tests never hit the network for cover fonts: downloads fail, so the system font fallback is used."""
    from syosetsu import fonts

    def offline(url, dest):
        raise OSError("network disabled in tests")

    monkeypatch.setattr(fonts, "_download", offline)
    monkeypatch.setenv("SYOSETSU_CACHE_DIR", str(tmp_path / "cache"))
