import pytest

from syosetsu.client import Client
from syosetsu.fetch import fetch_novel
from syosetsu.store import Store


@pytest.mark.live
def test_live_two_chapters(tmp_path):
    res = fetch_novel(Client(), Store(tmp_path), "n9669bk", frm=1, to=2, log=lambda *a: None)
    assert res.fetched == 2 and res.total > 200
    title, body = Store(tmp_path).read_chapter("n9669bk", 1)
    assert title and len(body) > 10
