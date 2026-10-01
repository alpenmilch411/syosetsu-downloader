"""Orchestration: metadata → TOC → missing chapters → store. Resumable and incremental."""
from dataclasses import dataclass
from datetime import datetime, timezone

from . import api
from .client import Client
from .parse import BASE, Arc, TocEntry, parse_chapter, parse_toc
from .store import Store


@dataclass
class FetchResult:
    ncode: str
    title: str
    fetched: int
    skipped: int
    total: int


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _toc(client: Client, ncode: str) -> list:
    items, url = [], f"{BASE}/{ncode}/"
    while url:
        toc = parse_toc(client.get_text(url), ncode)
        items += toc.items
        url = toc.next_page
    return items


def _arcs(items: list) -> list[dict]:
    arcs, pending = [], None
    for it in items:
        if isinstance(it, Arc):
            pending = it.title
        elif pending is not None:
            arcs.append({"title": pending, "first_chapter": it.n})
            pending = None
    return arcs


def _stale(site_updated: str, fetched_at: str | None) -> bool:
    if not fetched_at:
        return True
    if not site_updated:
        return False
    return datetime.fromisoformat(site_updated) > datetime.fromisoformat(fetched_at)


def fetch_novel(client, store: Store, ncode: str, frm=None, to=None, refresh=False, log=print, now=None) -> FetchResult:
    now = now or _utcnow
    meta = api.get_meta(client, ncode)
    if meta.noveltype == 2:
        items = [TocEntry(1, meta.title, "")]
        url_of = {1: f"{BASE}/{ncode}/"}
    else:
        items = _toc(client, ncode)
        url_of = {it.n: f"{BASE}/{ncode}/{it.n}/" for it in items if isinstance(it, TocEntry)}
    entries = [it for it in items if isinstance(it, TocEntry)]
    old = {c["n"]: c for c in (store.load_meta(ncode) or {}).get("chapters", [])}
    chapters = [{"n": e.n, "title": e.title, "site_updated": e.site_updated,
                 "fetched_at": old.get(e.n, {}).get("fetched_at") if store.has_chapter(ncode, e.n) else None}
                for e in entries]
    record = {
        "ncode": ncode, "title": meta.title, "author": meta.author, "noveltype": meta.noveltype,
        "finished": meta.finished, "biggenre": meta.biggenre, "genre": meta.genre, "story": meta.story,
        "chapter_count": len(entries), "source_url": f"{BASE}/{ncode}/", "arcs": _arcs(items),
        "chapters": chapters, "fetched_at": now(),
        "truncated_to": to if to is not None and to < len(entries) else None,
    }
    store.save_meta(ncode, record)
    by_n = {c["n"]: c for c in chapters}
    fetched = skipped = 0
    for e in entries:
        if (frm is not None and e.n < frm) or (to is not None and e.n > to):
            continue
        rec = by_n[e.n]
        if store.has_chapter(ncode, e.n) and not (refresh and _stale(e.site_updated, rec["fetched_at"])):
            skipped += 1
            continue
        ch = parse_chapter(client.get_text(url_of[e.n]))   # LayoutError propagates; nothing written
        store.write_chapter(ncode, e.n, e.title or ch.title, ch.body, ch.preface, ch.afterword)
        rec["fetched_at"] = now()
        store.save_meta(ncode, record)
        fetched += 1
        log(f"[{e.n}/{len(entries)}] {e.title}")
    return FetchResult(ncode, meta.title, fetched, skipped, len(entries))
