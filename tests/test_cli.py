from syosetsu import cli
from syosetsu.fetch import FetchResult
from syosetsu.parse import LayoutError


def test_fetch_list_continues_after_failure(tmp_path, monkeypatch, capsys):
    lst = tmp_path / "l.tsv"
    lst.write_text("n0000aa\nn0000bb\nn0000cc\n")
    done = []

    def fake_fetch(client, store, ncode, **kw):
        if ncode == "n0000bb":
            raise LayoutError("boom")
        done.append(ncode)
        return FetchResult(ncode, "t", 1, 0, 1)

    monkeypatch.setattr(cli, "fetch_novel", fake_fetch)
    rc = cli.main(["--data", str(tmp_path / "data"), "fetch", "--list", str(lst)])
    assert rc == 1
    assert done == ["n0000aa", "n0000cc"]
    assert "n0000bb" in capsys.readouterr().err


def test_bad_target_is_a_clean_error(tmp_path, capsys):
    assert cli.main(["--data", str(tmp_path), "fetch", "https://example.com/"]) == 2
    assert "not an ncode" in capsys.readouterr().err


def test_list_command(tmp_path, capsys):
    from syosetsu.store import Store
    s = Store(tmp_path)
    s.save_meta("n0000aa", {"title": "テスト", "chapter_count": 3})
    s.write_chapter("n0000aa", 1, "t", ["x"])
    assert cli.main(["--data", str(tmp_path), "list"]) == 0
    assert "n0000aa\t1/3\tテスト" in capsys.readouterr().out


def test_fetch_list_skips_malformed_entries(tmp_path, monkeypatch, capsys):
    lst = tmp_path / "l.tsv"
    lst.write_text("n0000aa\nnot-an-ncode\nn0000cc\n")
    done = []

    def fake_fetch(client, store, ncode, **kw):
        done.append(ncode)
        return FetchResult(ncode, "t", 1, 0, 1)

    monkeypatch.setattr(cli, "fetch_novel", fake_fetch)
    rc = cli.main(["--data", str(tmp_path / "data"), "fetch", "--list", str(lst)])
    assert rc == 1
    assert done == ["n0000aa", "n0000cc"]
    assert "not-an-ncode" in capsys.readouterr().err


def test_fetch_interval_option(tmp_path, monkeypatch):
    seen = {}

    class FakeClient:
        def __init__(self, **kw):
            seen.update(kw)

    monkeypatch.setattr(cli, "Client", FakeClient)
    monkeypatch.setattr(cli, "fetch_novel", lambda client, store, ncode, **kw: FetchResult(ncode, "t", 0, 0, 0))
    assert cli.main(["--data", str(tmp_path), "fetch", "n0000aa", "--interval", "1.0"]) == 0
    assert seen["min_interval"] == 1.0


def test_bad_cover_color_is_a_clean_error(tmp_path, capsys):
    from syosetsu.store import Store
    s = Store(tmp_path)
    s.save_meta("n0000aa", {"title": "t", "chapter_count": 1})
    s.write_chapter("n0000aa", 1, "t", ["x"])
    assert cli.main(["--data", str(tmp_path), "export", "epub", "n0000aa", "--cover-color", "nope"]) == 2
    assert "cover color" in capsys.readouterr().err
