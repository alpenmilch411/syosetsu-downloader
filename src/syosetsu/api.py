"""Syosetu metadata API and ncode handling."""
import json
import re
from dataclasses import dataclass

from .client import Client, NotFound

API_URL = "https://api.syosetu.com/novelapi/api/"
NCODE_RE = re.compile(r"(?:^|/)(n\d{4}[a-z]{1,3})(?:/|$)", re.IGNORECASE)


def normalize_ncode(target: str) -> str:
    m = NCODE_RE.search(target.strip())
    if not m:
        raise ValueError(f"not an ncode or ncode.syosetu.com URL: {target!r}")
    return m.group(1).lower()


@dataclass(frozen=True)
class NovelMeta:
    ncode: str
    title: str
    author: str
    noveltype: int      # 1 = serial, 2 = short story
    finished: bool
    chapter_count: int
    biggenre: int
    genre: int
    story: str


def get_meta(client: Client, ncode: str) -> NovelMeta:
    data = json.loads(client.get_text(API_URL, params={"out": "json", "ncode": ncode, "of": "t-w-nt-e-ga-bg-g-s"}))
    if not data or data[0].get("allcount", 0) == 0:
        raise NotFound(f"novel {ncode} not found (deleted or wrong ncode)")
    d = data[1]
    return NovelMeta(ncode=ncode, title=d["title"].strip(), author=d["writer"].strip(),
                     noveltype=int(d["noveltype"]), finished=int(d["end"]) == 0,
                     chapter_count=int(d["general_all_no"]), biggenre=int(d["biggenre"]),
                     genre=int(d["genre"]), story=d.get("story", ""))
