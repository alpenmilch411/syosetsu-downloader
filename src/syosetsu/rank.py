"""Ranking query → download list (TSV, first column = ncode, '#' comments)."""
import json
from pathlib import Path

from .api import API_URL
from .client import Client

GENRES = {101: "異世界〔恋愛〕", 102: "現実世界〔恋愛〕", 201: "ハイファンタジー", 202: "ローファンタジー",
          301: "純文学", 302: "ヒューマンドラマ", 303: "歴史", 304: "推理", 305: "ホラー", 306: "アクション",
          307: "コメディー", 401: "VRゲーム", 402: "宇宙", 403: "空想科学", 404: "パニック", 9901: "童話",
          9903: "エッセイ", 9904: "リプレイ", 9999: "その他", 9801: "ノンジャンル"}
STATUS_TYPE = {"completed": "er", "all": "re"}


def rank(client: Client, genres=None, top=10, status="completed", order="hyoka") -> list[dict]:
    rows = []
    for g in genres or list(GENRES):
        params = {"out": "json", "genre": g, "type": STATUS_TYPE[status], "order": order, "lim": top,
                  "of": "n-t-ga-l-gp"}
        for d in json.loads(client.get_text(API_URL, params=params))[1:]:
            rows.append({"ncode": d["ncode"].lower(), "genre": g, "points": d["global_point"],
                         "chapters": d["general_all_no"], "chars": d["length"],
                         "title": " ".join(d["title"].split())})
    return rows


def write_list(rows: list[dict], path: Path, header: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {header}", "# ncode\tgenre\tpoints\tchapters\tchars\ttitle"]
    lines += [f"{r['ncode']}\t{r['genre']}\t{r['points']}\t{r['chapters']}\t{r['chars']}\t{r['title']}" for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_list(path: Path) -> list[str]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line.split("\t")[0].strip())
    return out
