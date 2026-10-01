import json

from syosetsu.export_txt import chapter_lines, export_txt
from syosetsu.store import Store


def setup(tmp_path):
    s = Store(tmp_path)
    s.write_chapter("n0000aa", 1, "第一話", ["　｜東京《とうきょう》の｜空《・》。", "", "｜魔法《マジック》だ"],
                    preface=["前書き"], afterword=["後書き"])
    s.write_chapter("n0000aa", 2, "第二話", ["ruby無し"])
    s.save_meta("n0000aa", {"title": "t"})
    return s


def test_outputs_are_line_aligned_and_offsets_valid(tmp_path):
    s = setup(tmp_path)
    assert export_txt(s, "n0000aa") == (2, 3)
    d = s.novel_dir("n0000aa")
    plain = (d / "plain" / "0001.txt").read_text().split("\n")
    ruby = (d / "ruby" / "0001.txt").read_text().split("\n")
    assert len(plain) == len(ruby)
    assert plain[:3] == ["第一話", "", "　東京の空。"]
    records = [json.loads(l) for l in (d / "ruby.jsonl").read_text().splitlines()]
    assert [r["kind"] for r in records] == ["reading", "emphasis", "gloss"]
    for r in records:
        assert plain[r["line"] - 1][r["start"]:r["end"]] == r["base"]
    assert records[0] == {"ch": 1, "line": 3, "start": 1, "end": 3, "base": "東京", "reading": "とうきょう", "kind": "reading"}


def test_notes_excluded_by_default_and_included_on_request(tmp_path):
    s = setup(tmp_path)
    assert "前書き" not in chapter_lines(s, "n0000aa", 1)
    lines = chapter_lines(s, "n0000aa", 1, with_notes=True)
    assert lines[2] == "前書き" and lines[-1] == "後書き"


def test_unicode_not_escaped_in_jsonl(tmp_path):
    s = setup(tmp_path)
    export_txt(s, "n0000aa")
    assert "東京" in (s.novel_dir("n0000aa") / "ruby.jsonl").read_text()
