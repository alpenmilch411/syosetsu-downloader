"""Pure HTML → data parsers for ncode.syosetu.com pages. No I/O."""
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from selectolax.parser import HTMLParser, Node

from . import aozora

BASE = "https://ncode.syosetu.com"
DATE_RE = re.compile(r"(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2})")
SKIP_TAGS = {"br", "img", "rp", "rt", "script", "style"}


class LayoutError(Exception):
    """The page does not have the structure we expect — the site layout probably changed."""


@dataclass(frozen=True)
class Arc:
    title: str


@dataclass(frozen=True)
class TocEntry:
    n: int
    title: str
    site_updated: str


@dataclass
class Toc:
    items: list
    next_page: str | None


@dataclass
class Chapter:
    title: str
    body: list[str]
    preface: list[str]
    afterword: list[str]


def _classes(node: Node) -> list[str]:
    return (node.attributes.get("class") or "").split()


def _text(node: Node) -> str:
    # collapse ASCII whitespace only — full-width spaces (U+3000) are part of Japanese titles
    return re.sub(r"[ \t\r\n]+", " ", node.text(deep=True)).strip(" \t\r\n") if node is not None else ""


def _jst(text: str) -> str:
    found = DATE_RE.findall(text)
    if not found:
        return ""
    y, mo, d, h, mi = found[-1]
    return f"{y}-{mo}-{d}T{h}:{mi}:00+09:00"


def parse_toc(html: str, ncode: str) -> Toc:
    tree = HTMLParser(html)
    eplist = tree.css_first("div.p-eplist")
    if eplist is None:
        raise LayoutError("TOC page has no div.p-eplist")
    href_re = re.compile(rf"^/{re.escape(ncode)}/(\d+)/$", re.IGNORECASE)
    items: list = []
    for node in eplist.traverse():
        cls = _classes(node)
        if "p-eplist__chapter-title" in cls:
            items.append(Arc(_text(node)))
        elif "p-eplist__sublist" in cls:
            a = node.css_first("a.p-eplist__subtitle")
            m = href_re.match((a.attributes.get("href") or "") if a is not None else "")
            if not m:
                raise LayoutError(f"TOC entry without chapter link: {node.html[:200]}")
            upd = node.css_first("div.p-eplist__update")
            stamp_src = ""
            if upd is not None:
                span = upd.css_first("span[title]")
                stamp_src = upd.text(deep=True) + " " + ((span.attributes.get("title") or "") if span is not None else "")
            items.append(TocEntry(int(m.group(1)), _text(a), _jst(stamp_src)))
    nxt = tree.css_first("a.c-pager__item--next")
    next_page = urljoin(BASE, nxt.attributes["href"]) if nxt is not None and nxt.attributes.get("href") else None
    return Toc(items, next_page)


def _render(node: Node) -> str:
    out = []
    for child in node.iter(include_text=True):
        tag = child.tag
        if tag == "-text":
            out.append(child.text(deep=True))
        elif tag == "ruby":
            out.append(_ruby(child))
        elif tag in SKIP_TAGS:
            continue
        else:
            out.append(_render(child))
    return "".join(out)


def _ruby(node: Node) -> str:
    base, reading = [], []
    for child in node.iter(include_text=True):
        if child.tag == "rp":
            continue
        if child.tag == "rt":
            reading.append(child.text(deep=True))
        elif child.tag == "-text":
            base.append(child.text(deep=True))
        else:
            base.append(_render(child))
    return aozora.encode("".join(base).strip(), "".join(reading).strip())


def _lines(div: Node) -> list[str]:
    return [_render(p).replace("\r", "").replace("\n", "") for p in div.css("p")]


def parse_chapter(html: str) -> Chapter:
    tree = HTMLParser(html)
    body = preface = afterword = None
    for div in tree.css("div.js-novel-text"):
        cls = _classes(div)
        if "p-novel__text--preface" in cls:
            preface = _lines(div)
        elif "p-novel__text--afterword" in cls:
            afterword = _lines(div)
        elif body is None:
            if not div.css("p"):
                raise LayoutError("chapter body div has no <p> lines")
            body = _lines(div)
    if body is None:
        raise LayoutError("chapter page has no body div.js-novel-text")
    return Chapter(_text(tree.css_first("h1.p-novel__title")), body, preface or [], afterword or [])
