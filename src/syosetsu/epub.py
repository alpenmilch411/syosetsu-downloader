"""EPUB3 builder (stdlib zipfile + string templates)."""
import re
import sys
import time
import uuid
import zipfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from . import aozora, cover
from .export_txt import chapter_lines
from .store import Store

CSS_COMMON = """body { font-family: "Hiragino Mincho ProN", "Yu Mincho", "Noto Serif CJK JP", serif; line-height: 1.8; margin: 0; }
p { margin: 0; }
p.blank { height: 1em; }
h1, h2 { font-size: 1.3em; }
rt { font-size: 0.5em; }
.title-page h1 { font-size: 1.6em; }
"""
CSS_HORIZONTAL = """html { writing-mode: horizontal-tb; -webkit-writing-mode: horizontal-tb; -epub-writing-mode: horizontal-tb; }
h1, h2 { margin: 0 0 1.5em 0; }
.title-page p { margin-top: 1em; }
"""
CSS_VERTICAL = """html { writing-mode: vertical-rl; -webkit-writing-mode: vertical-rl; -epub-writing-mode: vertical-rl; }
h1, h2 { margin: 0 0 0 2em; }
.title-page p { margin-left: 1em; }
.tcy { text-combine-upright: all; -webkit-text-combine: horizontal; -epub-text-combine: horizontal; }
"""


def safe_filename(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", title).strip("_")[:80] or "novel"


def _xhtml(title: str, body: str, extra_head: str = "") -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="ja" lang="ja">\n'
            f'<head><meta charset="UTF-8"/><title>{escape(title)}</title><link rel="stylesheet" href="style.css"/>{extra_head}</head>\n'
            f"<body>{body}</body></html>")


def _tcy(html: str) -> str:
    return re.sub(r"(?<![0-9])([0-9]{2})(?![0-9])", r'<span class="tcy">\1</span>', html)


def _ncx(uid: str, title: str, nav: list[dict]) -> str:
    """EPUB2-style NCX (for readers that ignore nav.xhtml), same arc → chapter nesting as the nav."""
    order = [0]

    def point(x) -> str:
        order[0] += 1
        n = order[0]
        href = x["href"] if "href" in x else x["items"][0]["href"]
        children = "".join(point(i) for i in x.get("items", []))
        return (f'<navPoint id="np{n}" playOrder="{n}"><navLabel><text>{escape(x["title"])}</text></navLabel>'
                f'<content src={quoteattr(href)}/>{children}</navPoint>')

    points = "".join(point(x) for x in nav)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="ja">'
            f'<head><meta name="dtb:uid" content={quoteattr(uid)}/><meta name="dtb:depth" content="2"/>'
            '<meta name="dtb:totalPageCount" content="0"/><meta name="dtb:maxPageNumber" content="0"/></head>'
            f"<docTitle><text>{escape(title)}</text></docTitle><navMap>{points}</navMap></ncx>")


def build_epub(store: Store, ncode: str, out=None, vertical=False, with_notes=False, today=None) -> Path:
    meta = store.load_meta(ncode)
    if meta is None:
        raise FileNotFoundError(f"{ncode} has not been fetched yet")
    title, author = meta["title"], meta.get("author", "")
    files: dict[str, str] = {}
    spine: list[str] = []
    cover_bytes = None
    font = cover.find_font()
    if font:
        art = store.novel_dir(ncode) / "art.png"
        cover_bytes = cover.cover_jpeg(cover.render_cover(title, author, ncode, meta.get("biggenre", 2),
                                                          art_path=art if art.exists() else None, font_path=font))
        files["cover.xhtml"] = _xhtml("表紙", '<div class="cover"><img src="cover.jpg" alt="表紙"/></div>',
                                      "<style>html,body{margin:0;padding:0;writing-mode:horizontal-tb}"
                                      "img{display:block;width:100%;height:100vh;object-fit:contain}</style>")
        spine.append("cover.xhtml")
    else:
        print("warning: no CJK font found — building without a cover", file=sys.stderr)
    files["title.xhtml"] = _xhtml(title, f'<div class="title-page"><h1>{escape(title)}</h1><p>{escape(author)}</p>'
                                         f'<p>{escape(meta.get("source_url", ""))}</p>'
                                         f'<p>取得日 {escape(today or date.today().isoformat())}</p></div>')
    spine.append("title.xhtml")
    arcs_by_first = {a["first_chapter"]: a["title"] for a in meta.get("arcs", [])}
    nav: list[dict] = []
    current = None
    for n in store.chapter_numbers(ncode):
        lines = chapter_lines(store, ncode, n, with_notes)
        name = f"ch{n:04d}.xhtml"
        body = "".join(
            (f"<p>{_tcy(aozora.to_html(l)) if vertical else aozora.to_html(l)}</p>" if l.strip() else '<p class="blank"></p>')
            for l in lines[2:])
        files[name] = _xhtml(lines[0], f"<h2>{escape(lines[0])}</h2>{body}")
        spine.append(name)
        if n in arcs_by_first:
            current = {"title": arcs_by_first[n], "items": []}
            nav.append(current)
        (current["items"] if current else nav).append({"title": lines[0], "href": name})

    def li(x):
        if "href" in x:
            return f'<li><a href={quoteattr(x["href"])}>{escape(x["title"])}</a></li>'
        return (f'<li><a href={quoteattr(x["items"][0]["href"])}>{escape(x["title"])}</a>'
                f'<ol>{"".join(li(i) for i in x["items"])}</ol></li>')

    files["nav.xhtml"] = _xhtml("目次", '<nav epub:type="toc" id="toc"><h1>目次</h1><ol>'
                                        '<li><a href="title.xhtml">扉</a></li>' + "".join(li(x) for x in nav) + "</ol></nav>")
    uid = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, 'syosetu:' + ncode)}"
    ncx = _ncx(uid, title, [{"title": "扉", "href": "title.xhtml"}] + nav)
    ids = {name: f"i{i}" for i, name in enumerate(files)}
    manifest = "".join(f'<item id="{ids[n]}" href={quoteattr(n)} media-type="application/xhtml+xml"'
                       f'{" properties=\"nav\"" if n == "nav.xhtml" else ""}/>' for n in files)
    manifest += '<item id="css" href="style.css" media-type="text/css"/>'
    manifest += '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
    if cover_bytes:
        manifest += '<item id="cover-img" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>'
    direction = "rtl" if vertical else "ltr"
    opf = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid" xml:lang="ja">\n'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
           f'<dc:identifier id="uid">{uid}</dc:identifier>'
           f"<dc:title>{escape(title)}</dc:title><dc:creator>{escape(author)}</dc:creator><dc:language>ja</dc:language>"
           f"<dc:source>{escape(meta.get('source_url', ''))}</dc:source>"
           f'<meta property="dcterms:modified">{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}</meta>'
           + ('<meta name="cover" content="cover-img"/>' if cover_bytes else "")
           + ('<meta name="primary-writing-mode" content="vertical-rl"/>' if vertical else "")
           + f"</metadata>\n<manifest>{manifest}</manifest>\n"
           f'<spine toc="ncx" page-progression-direction="{direction}">'
           + "".join(f'<itemref idref="{ids[n]}"/>' for n in spine) + "</spine>\n</package>")
    path = Path(out) if out else store.novel_dir(ncode) / f"{safe_filename(title)}.epub"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with zipfile.ZipFile(tmp, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                   "</rootfiles></container>", compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/toc.ncx", ncx, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", CSS_COMMON + (CSS_VERTICAL if vertical else CSS_HORIZONTAL),
                   compress_type=zipfile.ZIP_DEFLATED)
        if cover_bytes:
            z.writestr("OEBPS/cover.jpg", cover_bytes, compress_type=zipfile.ZIP_STORED)
        for name, content in files.items():
            z.writestr("OEBPS/" + name, content, compress_type=zipfile.ZIP_DEFLATED)
    tmp.replace(path)
    return path
