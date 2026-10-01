import json

import httpx

from syosetsu.client import Client
from syosetsu.rank import rank, read_list, write_list


def test_rank_queries_each_genre(fake_clock):
    seen = []

    def handler(req):
        p = req.url.params
        seen.append((p["genre"], p["type"], p["order"], p["lim"]))
        return httpx.Response(200, text=json.dumps([{"allcount": 5}, {"ncode": "N1234AB", "global_point": 9,
                                                    "general_all_no": 3, "length": 100, "title": "題\t名"}]))

    client = Client(transport=httpx.MockTransport(handler), sleep=fake_clock.sleep, clock=fake_clock.clock)
    rows = rank(client, genres=[201, 302], top=5)
    assert seen == [("201", "er", "hyoka", "5"), ("302", "er", "hyoka", "5")]
    assert rows[0] == {"ncode": "n1234ab", "genre": 201, "points": 9, "chapters": 3, "chars": 100, "title": "題 名"}


def test_list_round_trip(tmp_path):
    p = tmp_path / "l.tsv"
    write_list([{"ncode": "n1", "genre": 1, "points": 2, "chapters": 3, "chars": 4, "title": "t"}], p, "test list")
    p.write_text(p.read_text() + "\n# comment\nn2\n")
    assert read_list(p) == ["n1", "n2"]


def test_read_seed_list_format(tmp_path):
    p = tmp_path / "seed.tsv"
    p.write_text("# header\n# ncode\tgenre\nn9669bk\t201\t991606\t286\t2830000\t無職転生\n")
    assert read_list(p) == ["n9669bk"]
