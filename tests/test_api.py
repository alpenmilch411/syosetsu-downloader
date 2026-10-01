import json

import httpx
import pytest

from syosetsu import api
from syosetsu.client import Client, NotFound


@pytest.mark.parametrize("target,expected", [
    ("n9669bk", "n9669bk"),
    ("N9669BK", "n9669bk"),
    ("https://ncode.syosetu.com/n9669bk/", "n9669bk"),
    ("https://ncode.syosetu.com/N9669BK/12/", "n9669bk"),
    ("ncode.syosetu.com/n6963w/", "n6963w"),
])
def test_normalize_ncode(target, expected):
    assert api.normalize_ncode(target) == expected


def test_normalize_ncode_rejects_garbage():
    with pytest.raises(ValueError):
        api.normalize_ncode("https://example.com/")


def _client(payload, fake_clock):
    def handler(req):
        assert req.url.params["ncode"] == "n0000aa"
        return httpx.Response(200, text=json.dumps(payload))
    return Client(transport=httpx.MockTransport(handler), sleep=fake_clock.sleep, clock=fake_clock.clock)


def test_get_meta(fake_clock):
    payload = [{"allcount": 1}, {"title": " テスト小説 ", "writer": "作者", "noveltype": 1, "end": 0,
                                 "general_all_no": 3, "biggenre": 2, "genre": 201, "story": "あらすじ"}]
    m = api.get_meta(_client(payload, fake_clock), "n0000aa")
    assert m == api.NovelMeta("n0000aa", "テスト小説", "作者", 1, True, 3, 2, 201, "あらすじ")


def test_get_meta_not_found(fake_clock):
    with pytest.raises(NotFound):
        api.get_meta(_client([{"allcount": 0}], fake_clock), "n0000aa")
