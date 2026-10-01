"""Aozora-style ruby notation: ｜BASE《READING》."""
import re
from dataclasses import dataclass
from xml.sax.saxutils import escape

RUBY_RE = re.compile(r"｜([^｜《》\n]+)《([^｜《》\n]+)》")
KANJI_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿々〆ヶ]")
HIRAGANA_RE = re.compile(r"[ぁ-ゟー]+")
EMPHASIS_CHARS = frozenset("・﹅﹆●○◦•、ヽ")
NOTATION_CHARS = frozenset("｜《》")


@dataclass(frozen=True)
class RubySpan:
    start: int  # offsets into strip(line), code points, end exclusive
    end: int
    base: str
    reading: str


def encode(base: str, reading: str) -> str:
    if not base or not reading or NOTATION_CHARS & set(base + reading):
        return base
    return f"｜{base}《{reading}》"


def strip(line: str) -> str:
    return RUBY_RE.sub(r"\1", line)


def spans(line: str) -> list[RubySpan]:
    out, plain_pos, last = [], 0, 0
    for m in RUBY_RE.finditer(line):
        plain_pos += m.start() - last
        base = m.group(1)
        out.append(RubySpan(plain_pos, plain_pos + len(base), base, m.group(2)))
        plain_pos += len(base)
        last = m.end()
    return out


def to_html(line: str) -> str:
    parts, last = [], 0
    for m in RUBY_RE.finditer(line):
        parts.append(escape(line[last:m.start()]))
        parts.append(f"<ruby>{escape(m.group(1))}<rt>{escape(m.group(2))}</rt></ruby>")
        last = m.end()
    parts.append(escape(line[last:]))
    return "".join(parts)


def classify(base: str, reading: str) -> str:
    if reading and all(c in EMPHASIS_CHARS for c in reading):
        return "emphasis"
    if KANJI_RE.search(base) and HIRAGANA_RE.fullmatch(reading) and len(reading) <= 4 * len(base):
        return "reading"
    return "gloss"
