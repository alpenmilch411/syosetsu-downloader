import json

import httpx
import pytest

from conftest import fixture_text
from syosetsu.client import Client
from syosetsu.fetch import fetch_novel
from syosetsu.parse import LayoutError
from syosetsu.store import Store

META = [{"allcount": 1}, {"title": "テスト小説", "writer": "作者", "noveltype": 1, "end": 0,
                          "general_all_no": 3, "biggenre": 2, "genre": 201, "story": "あらすじ"}]
SHORT_META = [{"allcount": 1}, {"title": "短編のタイトル", "writer": "作者", "noveltype": 2, "end": 0,
                                "general_all_no": 1, "biggenre": 3, "genre": 302, "story": ""}]


def chapter_html(title):
    return f'<h1 class="p-novel__title">{title}</h1><div class="js-novel-text p-novel__text"><p>{title}の本文。</p></div>'


class Site:
    def __init__(self, meta=META, broken=()):
        self.meta, self.broken, self.hits = meta, set(broken), []

    def handler(self, req):
        url = str(req.url)
        self.hits.append(url)
        if "api.syosetu.com" in url:
            return httpx.Response(200, text=json.dumps(self.meta))
        if url.endswith("/n0000aa/?p=2"):
            return httpx.Response(200, text=fixture_text("toc_p2.html"))
        if url.endswith("/n0000aa/"):
            page = "short.html" if self.meta is SHORT_META else "toc_p1.html"
            return httpx.Response(200, text=fixture_text(page))
        n = int(url.rstrip("/").rsplit("/", 1)[1])
        if n in self.broken:
            return httpx.Response(200, text="<html><body>maintenance</body></html>")
        return httpx.Response(200, text=chapter_html(f"第{n}話"))


def run(tmp_path, fake_clock, site, **kw):
    client = Client(transport=httpx.MockTransport(site.handler), sleep=fake_clock.sleep, clock=fake_clock.clock)
    return fetch_novel(client, Store(tmp_path), "n0000aa", log=lambda *a: None,
                       now=lambda: "2026-10-01T00:00:00+00:00", **kw)


def test_fetches_all_chapters_and_writes_meta(tmp_path, fake_clock):
    res = run(tmp_path, fake_clock, Site())
    assert (res.fetched, res.skipped, res.total) == (3, 0, 3)
    store = Store(tmp_path)
    assert store.chapter_numbers("n0000aa") == [1, 2, 3]
    assert store.read_chapter("n0000aa", 2)[0] == "第一話　出会い & 別れ"   # TOC title wins
    meta = store.load_meta("n0000aa")
    assert meta["title"] == "テスト小説" and meta["chapter_count"] == 3
    assert [c["fetched_at"] for c in meta["chapters"]] == ["2026-10-01T00:00:00+00:00"] * 3


def test_arc_spanning_toc_pages(tmp_path, fake_clock):
    run(tmp_path, fake_clock, Site())
    arcs = Store(tmp_path).load_meta("n0000aa")["arcs"]
    assert arcs == [{"title": "第一章　はじまり", "first_chapter": 1},
                    {"title": "第二章　旅立ち", "first_chapter": 3}]   # heading on p1, chapter on p2


def test_resume_skips_existing(tmp_path, fake_clock):
    run(tmp_path, fake_clock, Site())
    site = Site()
    res = run(tmp_path, fake_clock, site)
    assert (res.fetched, res.skipped) == (0, 3)
    assert not [u for u in site.hits if u.rstrip("/").split("/")[-1].isdigit()]


def test_from_to_range(tmp_path, fake_clock):
    res = run(tmp_path, fake_clock, Site(), frm=2, to=2)
    assert res.fetched == 1
    assert Store(tmp_path).chapter_numbers("n0000aa") == [2]


def test_layout_error_writes_nothing(tmp_path, fake_clock):
    with pytest.raises(LayoutError):
        run(tmp_path, fake_clock, Site(broken={2}))
    store = Store(tmp_path)
    assert store.chapter_numbers("n0000aa") == [1]
    chapters = {c["n"]: c for c in store.load_meta("n0000aa")["chapters"]}
    assert chapters[1]["fetched_at"] and chapters[2]["fetched_at"] is None
    res = run(tmp_path, fake_clock, Site())          # re-run picks up where it stopped
    assert (res.fetched, res.skipped) == (2, 1)


def test_refresh_refetches_revised_chapters(tmp_path, fake_clock):
    run(tmp_path, fake_clock, Site())
    meta = Store(tmp_path).load_meta("n0000aa")
    for c in meta["chapters"]:
        c["fetched_at"] = "2020-02-01T00:00:00+00:00"   # before ch2's 改稿 (2020-03-01 JST), after others
    Store(tmp_path).save_meta("n0000aa", meta)
    res = run(tmp_path, fake_clock, Site(), refresh=True)
    assert (res.fetched, res.skipped) == (1, 2)


def test_short_story(tmp_path, fake_clock):
    res = run(tmp_path, fake_clock, Site(meta=SHORT_META))
    assert res.total == 1
    assert Store(tmp_path).read_chapter("n0000aa", 1) == ("短編のタイトル", ["短い話。"])


def test_truncated_fetch_is_marked_in_meta(tmp_path, fake_clock):
    run(tmp_path, fake_clock, Site(), to=2)
    assert Store(tmp_path).load_meta("n0000aa")["truncated_to"] == 2


def test_full_fetch_has_no_truncation_marker(tmp_path, fake_clock):
    run(tmp_path, fake_clock, Site(), to=3)            # limit >= total chapters → not truncated
    assert Store(tmp_path).load_meta("n0000aa")["truncated_to"] is None
