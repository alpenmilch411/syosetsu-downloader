import re
import shutil
import subprocess
import zipfile
from xml.dom import minidom

import pytest

from syosetsu.epub import build_epub, safe_filename
from syosetsu.store import Store


def setup(tmp_path, title="テスト小説"):
    s = Store(tmp_path)
    s.save_meta("n0000aa", {"ncode": "n0000aa", "title": title, "author": "作者 & <仲間>", "biggenre": 2,
                            "source_url": "https://ncode.syosetu.com/n0000aa/",
                            "arcs": [{"title": "第一章", "first_chapter": 1}, {"title": "第二章", "first_chapter": 2}]})
    s.write_chapter("n0000aa", 1, "第一話 <始まり>", ["　｜東京《とうきょう》の空 & 海", ""])
    s.write_chapter("n0000aa", 2, "第二話", ["本文"])
    return s


def test_structure(tmp_path):
    path = build_epub(setup(tmp_path), "n0000aa", today="2026-10-01")
    z = zipfile.ZipFile(path)
    names = z.namelist()
    assert names[0] == "mimetype" and z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
    assert z.read("mimetype") == b"application/epub+zip"
    for n in names:
        if n.endswith((".xhtml", ".opf", ".xml")):
            minidom.parseString(z.read(n))                      # well-formed
    opf = z.read("OEBPS/content.opf").decode()
    for href in re.findall(r'href="([^"]+)"', opf):
        assert "OEBPS/" + href in names                         # manifest ↔ files
    assert 'page-progression-direction="ltr"' in opf
    assert 'properties="cover-image"' in opf or "cover" not in opf


def test_ruby_and_nav(tmp_path):
    z = zipfile.ZipFile(build_epub(setup(tmp_path), "n0000aa"))
    ch1 = z.read("OEBPS/ch0001.xhtml").decode()
    assert "<ruby>東京<rt>とうきょう</rt></ruby>" in ch1
    nav = z.read("OEBPS/nav.xhtml").decode()
    assert nav.index("第一章") < nav.index("第一話") < nav.index("第二章") < nav.index("第二話")


def test_special_characters_escaped(tmp_path):
    z = zipfile.ZipFile(build_epub(setup(tmp_path, title="A/B & <C>"), "n0000aa"))
    assert "&amp; 海" in z.read("OEBPS/ch0001.xhtml").decode()
    assert "作者 &amp; &lt;仲間&gt;" in z.read("OEBPS/content.opf").decode()
    assert safe_filename("A/B & <C>") == "A_B_&_C"


def test_vertical_option(tmp_path):
    z = zipfile.ZipFile(build_epub(setup(tmp_path), "n0000aa", vertical=True))
    assert 'page-progression-direction="rtl"' in z.read("OEBPS/content.opf").decode()
    assert "vertical-rl" in z.read("OEBPS/style.css").decode()


def test_default_output_path(tmp_path):
    path = build_epub(setup(tmp_path), "n0000aa")
    assert path == tmp_path / "n0000aa" / "テスト小説.epub"


@pytest.mark.skipif(shutil.which("epubcheck") is None, reason="epubcheck not installed")
def test_epubcheck(tmp_path):
    path = build_epub(setup(tmp_path), "n0000aa")
    r = subprocess.run(["epubcheck", str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_ncx_with_nested_navmap(tmp_path):
    z = zipfile.ZipFile(build_epub(setup(tmp_path), "n0000aa"))
    assert "OEBPS/toc.ncx" in z.namelist()
    ncx = z.read("OEBPS/toc.ncx").decode()
    minidom.parseString(ncx)
    opf = z.read("OEBPS/content.opf").decode()
    assert 'media-type="application/x-dtbncx+xml"' in opf and 'toc="ncx"' in opf
    doc = minidom.parseString(ncx)
    top = [n for n in doc.getElementsByTagName("navMap")[0].childNodes if n.nodeName == "navPoint"]
    labels = [p.getElementsByTagName("text")[0].firstChild.data for p in top]
    assert labels[-2:] == ["第一章", "第二章"]
    assert len(top[-2].getElementsByTagName("navPoint")) == 1     # chapter nested under its arc
    orders = [int(p.getAttribute("playOrder")) for p in doc.getElementsByTagName("navPoint")]
    assert orders == sorted(orders) and len(set(orders)) == len(orders)
