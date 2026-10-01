import pytest

from conftest import fixture_text
from syosetsu.parse import Arc, LayoutError, TocEntry, parse_chapter, parse_toc


def test_toc_page_1():
    toc = parse_toc(fixture_text("toc_p1.html"), "n0000aa")
    assert toc.items == [
        Arc("第一章　はじまり"),
        TocEntry(1, "プロローグ", "2020-01-01T12:00:00+09:00"),
        TocEntry(2, "第一話　出会い & 別れ", "2020-03-01T09:30:00+09:00"),  # 改稿 date wins
        Arc("第二章　旅立ち"),
    ]
    assert toc.next_page == "https://ncode.syosetu.com/n0000aa/?p=2"


def test_toc_last_page_has_no_next():
    toc = parse_toc(fixture_text("toc_p2.html"), "n0000aa")
    assert toc.items == [TocEntry(3, "第二話　出発", "2020-01-03T12:00:00+09:00")]
    assert toc.next_page is None


def test_toc_ncode_case_insensitive():
    assert parse_toc(fixture_text("toc_p2.html"), "N0000AA").items[0].n == 3


def test_toc_without_eplist_raises():
    with pytest.raises(LayoutError):
        parse_toc("<html><body></body></html>", "n0000aa")


def test_chapter_lines():
    ch = parse_chapter(fixture_text("chapter.html"))
    assert ch.title == "第一話　出会い"
    assert ch.body == [
        "　｜東京《とうきょう》の空は青い。",
        "",
        "「｜英雄《しゅやく》だ」と｜彼《・》は言った。",
        "｜魔法《マジック》 & 剣",
        "《罠》だ。",                      # base with notation chars → ruby dropped, base kept
    ]
    assert ch.preface == ["前書きです。"]
    assert ch.afterword == ["後書きです。"]


def test_short_story_page():
    ch = parse_chapter(fixture_text("short.html"))
    assert ch.title == "短編のタイトル"
    assert ch.body == ["短い話。"]
    assert ch.preface == [] and ch.afterword == []


def test_chapter_without_body_raises():
    with pytest.raises(LayoutError):
        parse_chapter(fixture_text("no_body.html"))


def test_empty_body_div_raises():
    html = '<h1 class="p-novel__title">t</h1><div class="js-novel-text p-novel__text"></div>'
    with pytest.raises(LayoutError):
        parse_chapter(html)


def test_image_only_chapter_is_accepted():
    html = '<h1 class="p-novel__title">t</h1><div class="js-novel-text p-novel__text"><p><img src="x.png"></p></div>'
    assert parse_chapter(html).body == [""]
