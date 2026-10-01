from syosetsu.store import Store


def test_chapter_round_trip(tmp_path):
    s = Store(tmp_path)
    body = ["　一行目", "", "｜東京《とうきょう》", ""]
    s.write_chapter("n0000aa", 1, "第一話", body, preface=["前"], afterword=[])
    assert s.has_chapter("n0000aa", 1)
    assert s.read_chapter("n0000aa", 1) == ("第一話", body)
    assert s.read_notes("n0000aa", 1) == (["前"], [])
    assert s.chapter_path("n0000aa", 1).name == "0001.txt"


def test_empty_body_round_trip(tmp_path):
    s = Store(tmp_path)
    s.write_chapter("n0000aa", 2, "空", [])
    assert s.read_chapter("n0000aa", 2) == ("空", [])


def test_rewrite_removes_stale_notes(tmp_path):
    s = Store(tmp_path)
    s.write_chapter("n0000aa", 1, "t", ["a"], preface=["p"])
    s.write_chapter("n0000aa", 1, "t", ["a"])
    assert s.read_notes("n0000aa", 1) == ([], [])


def test_chapter_numbers_sorted_numerically(tmp_path):
    s = Store(tmp_path)
    for n in (10, 2, 10000):
        s.write_chapter("n0000aa", n, "t", ["x"])
    assert s.chapter_numbers("n0000aa") == [2, 10, 10000]


def test_meta_and_novels(tmp_path):
    s = Store(tmp_path)
    assert s.load_meta("n0000aa") is None
    s.save_meta("n0000aa", {"title": "テスト"})
    assert s.load_meta("n0000aa") == {"title": "テスト"}
    assert s.novels() == ["n0000aa"]


def test_no_tmp_files_left(tmp_path):
    s = Store(tmp_path)
    s.write_chapter("n0000aa", 1, "t", ["x"])
    s.save_meta("n0000aa", {})
    assert not list(tmp_path.rglob("*.tmp"))
