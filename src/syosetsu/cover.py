"""Cover image: vertical Mincho title, typographic or over an illustration."""
import hashlib
import io
import os
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

W, H = 1600, 2560
FONT_CANDIDATES = [
    "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
    "/System/Library/Fonts/Hiragino Mincho ProN.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
]
PALETTE = {  # biggenre → (background, accent)
    1: ((122, 42, 58), (236, 200, 170)), 2: ((28, 52, 92), (226, 196, 120)),
    3: ((44, 70, 58), (222, 214, 180)), 4: ((24, 30, 44), (150, 210, 230)),
    99: ((70, 60, 52), (230, 210, 170)), 98: ((60, 60, 64), (220, 220, 210)),
}
VERT = str.maketrans({"「": "﹁", "」": "﹂", "『": "﹃", "』": "﹄", "（": "︵", "）": "︶", "(": "︵", ")": "︶",
                      "ー": "丨", "－": "丨", "—": "丨", "…": "︙", "〜": "丨", "～": "丨", "【": "︻", "】": "︼",
                      "〈": "︿", "〉": "﹀", "《": "︽", "》": "︾", "!": "！", "?": "？"})
PHRASE_RE = re.compile(r"[^、。]*[、。]|[^、。]+$")


def find_font() -> str | None:
    env = os.environ.get("SYOSETSU_COVER_FONT")
    for p in ([env] if env else []) + FONT_CANDIDATES:
        if p and Path(p).exists():
            return p
    return None


def _font(path: str, size: int, bold: bool) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size, index=1 if bold else 0)
    except OSError:
        return ImageFont.truetype(path, size)


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


def render_cover(title, author, ncode, biggenre=2, art_path=None, font_path=None) -> Image.Image:
    font_path = font_path or find_font()
    if font_path is None:
        raise RuntimeError("no CJK font found (set SYOSETSU_COVER_FONT)")
    bg, accent = PALETTE.get(biggenre, PALETTE[99])
    main, sub = split_title(title)
    if art_path and Path(art_path).exists():
        return _art_cover(main, sub, author, accent, Path(art_path), font_path)
    shift = int(hashlib.sha1(ncode.encode()).hexdigest(), 16) % 21 - 10
    bg = tuple(max(0, min(255, c + shift)) for c in bg)
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    faint = tuple(min(255, c + 14) for c in bg)
    for row in range(14):                      # faint 青海波 waves in the lower part
        y = H - 120 - row * 60
        if y < H * 0.62:
            break
        for x in range(-120 + (0 if row % 2 else 60), W + 120, 120):
            for r in (60, 44, 28):
                d.arc((x - r, y - r, x + r, y + r), 180, 360, fill=faint, width=3)
    d.rectangle((70, 70, W - 70, H - 70), outline=accent, width=6)
    d.rectangle((95, 95, W - 95, H - 95), outline=accent, width=2)
    size, rows = fit(main, W - 420, H * 0.72, 220)
    n_main = _draw_vertical(d, main, _font(font_path, size, True), W - 190, 200, rows, (250, 246, 236))
    if sub:
        s_size, s_rows = fit(sub, W - 420 - n_main * size * 1.25 - 40, H * 0.72, 96)
        _draw_vertical(d, sub, _font(font_path, s_size, False), W - 190 - n_main * size * 1.25 - 50, 240, s_rows, accent)
    _draw_vertical(d, author, _font(font_path, 80, True), 330, H - 200 - min(len(author), 12) * 84, 12, accent)
    return img


def _art_cover(main, sub, author, accent, art_path, font_path) -> Image.Image:
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
    n_main = _draw_vertical(d, main, _font(font_path, size, True), W - 150, 170, rows, (252, 248, 238),
                            stroke=max(3, size // 22), stroke_fill=shadow)
    if sub:
        s_size, s_rows = fit(sub, W * 0.16, H * 0.62, 70)
        _draw_vertical(d, sub, _font(font_path, s_size, False), W - 150 - n_main * size * 1.25 - 30, 200, s_rows,
                       accent, stroke=3, stroke_fill=shadow)
    _draw_vertical(d, author, _font(font_path, 72, True), 260, H - 170 - min(len(author), 12) * 76, 12, accent,
                   stroke=3, stroke_fill=shadow)
    return img


def cover_jpeg(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "JPEG", quality=88, optimize=True, progressive=True)
    return buf.getvalue()
