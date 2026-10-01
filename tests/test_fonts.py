import pytest

from syosetsu import fonts
from syosetsu.fonts import FontSpec, resolve_font


def fake_downloader(calls):
    def download(url, dest):
        calls.append(url)
        dest.write_bytes(b"font-bytes")
    return download


def test_path_spec_is_used_directly(tmp_path):
    f = tmp_path / "my.ttf"
    f.write_bytes(b"x")
    assert resolve_font(str(f), cache_dir=tmp_path / "c") == FontSpec(str(f), str(f), variable=False)


def test_named_font_is_downloaded_once_with_license(tmp_path):
    calls = []
    spec = resolve_font("shippori", cache_dir=tmp_path, download=fake_downloader(calls))
    assert spec.regular.endswith("ShipporiMincho-Regular.ttf") and spec.bold.endswith("ShipporiMincho-Bold.ttf")
    assert not spec.variable
    assert (tmp_path / "shippori" / "OFL.txt").exists()
    n = len(calls)
    resolve_font("shippori", cache_dir=tmp_path, download=fake_downloader(calls))
    assert len(calls) == n                                   # cached: no second download


def test_variable_font(tmp_path):
    spec = resolve_font("mincho", cache_dir=tmp_path, download=fake_downloader([]))
    assert spec.variable and spec.regular == spec.bold and "NotoSerifJP" in spec.regular


def test_unknown_name_raises(tmp_path):
    with pytest.raises(ValueError, match="unknown cover font"):
        resolve_font("comic-sans", cache_dir=tmp_path)


def test_download_failure_falls_back_to_system_font(tmp_path, monkeypatch):
    def broken(url, dest):
        raise OSError("offline")
    monkeypatch.setattr(fonts, "find_system_font", lambda: "/sys/font.ttc")
    assert resolve_font("gothic", cache_dir=tmp_path, download=broken) == FontSpec("/sys/font.ttc", "/sys/font.ttc", False)
    assert not list(tmp_path.rglob("*.ttf"))                 # nothing half-written left behind


def test_no_font_anywhere_returns_none(tmp_path, monkeypatch):
    def broken(url, dest):
        raise OSError("offline")
    monkeypatch.setattr(fonts, "find_system_font", lambda: None)
    assert resolve_font("gothic", cache_dir=tmp_path, download=broken) is None
