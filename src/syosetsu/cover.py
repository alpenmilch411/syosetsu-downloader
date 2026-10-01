"""Cover image: vertical Mincho title, typographic or over an illustration."""
import hashlib
import io
import os
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from .fonts import FontSpec, find_system_font

W, H = 1600, 2560
PALETTE = {  # biggenre → (background, accent)
    1: ((122, 42, 58), (236, 200, 170)), 2: ((28, 52, 92), (226, 196, 120)),
    3: ((44, 70, 58), (222, 214, 180)), 4: ((24, 30, 44), (150, 210, 230)),
    99: ((70, 60, 52), (230, 210, 170)), 98: ((60, 60, 64), (220, 220, 210)),
}
PRESETS = {
    "indigo": (28, 52, 92), "rose": (122, 42, 58), "forest": (44, 70, 58), "night": (24, 30, 44),
    "sepia": (222, 203, 164), "charcoal": (52, 52, 56), "cream": (243, 236, 220),
}
PATTERNS = ("waves", "none")
LIGHT_TEXT, DARK_TEXT = (250, 246, 236), (38, 30, 26)
GOLD, BROWN = (226, 196, 120), (120, 82, 36)
VERT = str.maketrans({"「": "﹁", "」": "﹂", "『": "﹃", "』": "﹄", "（": "︵", "）": "︶", "(": "︵", ")": "︶",
                      "ー": "丨", "－": "丨", "—": "丨", "…": "︙", "〜": "丨", "～": "丨", "【": "︻", "】": "︼",
                      "〈": "︿", "〉": "﹀", "《": "︽", "》": "︾", "!": "！", "?": "？"})
PHRASE_RE = re.compile(r"[^、。]*[、。]|[^、。]+$")


find_font = find_system_font


def _luminance(c) -> float:
    ch = [x / 255 for x in c]
    ch = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in ch]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def _contrast(a, b) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def resolve_palette(color: str, biggenre: int, ncode: str) -> tuple[tuple, tuple, tuple]:
    """→ (background, accent, text). 'auto' tints by genre; presets and #RRGGBB are accepted.
    Text and accent colours are chosen so they stay readable on the background."""
    preferred_accent = GOLD
    if color == "auto":
        bg, preferred_accent = PALETTE.get(biggenre, PALETTE[99])
        shift = int(hashlib.sha1(ncode.encode()).hexdigest(), 16) % 21 - 10
        bg = tuple(max(0, min(255, c + shift)) for c in bg)
    elif color in PRESETS:
        bg = PRESETS[color]
    elif re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        bg = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    else:
        raise ValueError(f"invalid cover color {color!r}: use auto, {', '.join(PRESETS)} or #RRGGBB")
    text = max((LIGHT_TEXT, DARK_TEXT), key=lambda t: _contrast(bg, t))
    accent = next((a for a in (preferred_accent, GOLD, BROWN) if _contrast(bg, a) >= 3.0), text)
    return bg, accent, text


def _font(font: FontSpec, size: int, bold: bool) -> ImageFont.FreeTypeFont:
    if font.variable:
        f = ImageFont.truetype(font.regular, size)
        try:
            f.set_variation_by_name("Bold" if bold else "Regular")
        except (OSError, ValueError):
            pass
        return f
    if font.regular != font.bold:
        return ImageFont.truetype(font.bold if bold else font.regular, size)
    try:  # one collection file (e.g. Hiragino .ttc): index 1 is the heavier weight
        return ImageFont.truetype(font.regular, size, index=1 if bold else 0)
    except OSError:
        return ImageFont.truetype(font.regular, size)


def split_title(title: str) -> tuple[str, str]:
    t = re.sub(r"【[^】]*】|\[[^\]]*\]", "", title).strip()
    t = re.sub(r"ヽ?[(（][^)）]*[)）]ノ?", "", t).strip()
    parts = re.split(r"\s*[〜～~]\s*|\s+[-－―]\s*", t, maxsplit=1)
    main = parts[0].strip(" 　")
    sub = parts[1].strip(" 　〜～~") if len(parts) > 1 else ""
    return main, sub


def columns(text: str, rows: int) -> list[str]:
    """Columns of <= rows chars, breaking right after 、。 where possible."""
    text = text.replace(" ", "").replace("　", "")
    cols, cur = [], ""
    for seg in PHRASE_RE.findall(text) or [text]:
        while len(seg) > rows:
            if cur:
                cols.append(cur)
                cur = ""
            cols.append(seg[:rows])
            seg = seg[rows:]
        if len(cur) + len(seg) > rows:
            cols.append(cur)
            cur = seg
        else:
            cur += seg
    if cur:
        cols.append(cur)
    return cols


def fit(text: str, max_w: float, max_h: float, start: int, col_gap: float = 1.25) -> tuple[int, int]:
    """Largest size that fits; first keeping every 、-phrase whole, else an even hard wrap."""
    t = text.replace(" ", "").replace("　", "")
    n = len(t)
    longest = max(len(x) for x in PHRASE_RE.findall(t) or [t])
    for size in range(start, 40, -4):
        if longest <= int(max_h // (size * 1.05)) and len(columns(t, longest)) * size * col_gap <= max_w:
            return size, longest
    for size in range(start, 40, -4):
        max_rows = int(max_h // (size * 1.05))
        rows = -(-n // -(-n // max_rows))
        if len(columns(t, rows)) * size * col_gap <= max_w:
            return size, rows
    return 40, int(max_h // 42)


def _draw_vertical(d, text, font, x_right, y_top, rows, fill, stroke=0, stroke_fill=None, col_gap=1.25):
    size = font.size
    for ci, col in enumerate(columns(text, rows)):
        x = x_right - (ci + 1) * size * col_gap
        for ri, ch in enumerate(col.translate(VERT)):
            cx, cy = x + size / 2, y_top + ri * size * 1.05 + size / 2
            if ch in "、。，．":
                cx, cy = cx + size * 0.32, cy - size * 0.32
            d.text((cx, cy), ch, font=font, fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=stroke_fill)
    return len(columns(text, rows))


def render_cover(title, author, ncode, biggenre=2, art_path=None, font_path=None,
                 color="auto", pattern="waves", font: FontSpec | None = None) -> Image.Image:
    if pattern not in PATTERNS:
        raise ValueError(f"invalid cover pattern {pattern!r}: use {' or '.join(PATTERNS)}")
    bg, accent, text = resolve_palette(color, biggenre, ncode)
    if font is None:
        path = font_path or find_font()
        if path is None:
            raise RuntimeError("no CJK font found (set SYOSETSU_COVER_FONT)")
        font = FontSpec(path, path, False)
    main, sub = split_title(title)
    if art_path and Path(art_path).exists():
        art_accent = accent if _contrast(accent, (10, 12, 22)) >= 3.0 else GOLD
        return _art_cover(main, sub, author, art_accent, Path(art_path), font)
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    step = -14 if text == DARK_TEXT else 14
    faint = tuple(max(0, min(255, c + step)) for c in bg)
    for row in range(14 if pattern == "waves" else 0):                      # faint 青海波 waves in the lower part
        y = H - 120 - row * 60
        if y < H * 0.62:
            break
        for x in range(-120 + (0 if row % 2 else 60), W + 120, 120):
            for r in (60, 44, 28):
                d.arc((x - r, y - r, x + r, y + r), 180, 360, fill=faint, width=3)
    d.rectangle((70, 70, W - 70, H - 70), outline=accent, width=6)
    d.rectangle((95, 95, W - 95, H - 95), outline=accent, width=2)
    size, rows = fit(main, W - 420, H * 0.72, 220)
    n_main = _draw_vertical(d, main, _font(font, size, True), W - 190, 200, rows, text)
    if sub:
        s_size, s_rows = fit(sub, W - 420 - n_main * size * 1.25 - 40, H * 0.72, 96)
        _draw_vertical(d, sub, _font(font, s_size, False), W - 190 - n_main * size * 1.25 - 50, 240, s_rows, accent)
    _draw_vertical(d, author, _font(font, 80, True), 330, H - 200 - min(len(author), 12) * 84, 12, accent)
    return img


def _art_cover(main, sub, author, accent, art_path, font: FontSpec) -> Image.Image:
    src = Image.open(art_path).convert("RGB")
    scale = max(W / src.width, H / src.height)
    src = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    left, top = (src.width - W) // 2, (src.height - H) // 2
    img = src.crop((left, top, left + W, top + H))
    side = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(side)
    for x in range(W):                         # darker towards the right edge (title side)
        sd.line((x, 0, x, H), fill=int(max(0, (x - W * 0.35) / (W * 0.65)) ** 1.6 * 170))
    ends = Image.new("L", (W, H), 0)
    ed = ImageDraw.Draw(ends)
    for y in range(H):                         # top fade + bottom fade for the author
        ed.line((0, y, W, y), fill=int(max(max(0, 1 - y / (H * 0.55)) * 120, max(0, (y - H * 0.82) / (H * 0.18)) * 170)))
    img = Image.composite(Image.new("RGB", (W, H), (10, 12, 22)), img, ImageChops.lighter(side, ends))
    d = ImageDraw.Draw(img)
    d.rectangle((60, 60, W - 60, H - 60), outline=accent, width=4)
    shadow = (8, 10, 20)
    size, rows = fit(main, W * 0.42, H * 0.62, 190)
    n_main = _draw_vertical(d, main, _font(font, size, True), W - 150, 170, rows, (252, 248, 238),
                            stroke=max(3, size // 22), stroke_fill=shadow)
    if sub:
        s_size, s_rows = fit(sub, W * 0.16, H * 0.62, 70)
        _draw_vertical(d, sub, _font(font, s_size, False), W - 150 - n_main * size * 1.25 - 30, 200, s_rows,
                       accent, stroke=3, stroke_fill=shadow)
    _draw_vertical(d, author, _font(font, 72, True), 260, H - 170 - min(len(author), 12) * 76, 12, accent,
                   stroke=3, stroke_fill=shadow)
    return img


def cover_jpeg(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "JPEG", quality=88, optimize=True, progressive=True)
    return buf.getvalue()
