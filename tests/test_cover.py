import pytest
from PIL import Image

from syosetsu import cover

FONT = cover.find_font()
needs_font = pytest.mark.skipif(FONT is None, reason="no CJK font available")


def test_split_title_drops_tags_and_kaomoji():
    assert cover.split_title("【書籍化】帰って来た勇者 ヽ(・∀・)ノ ～都会的スローライフ～") == ("帰って来た勇者", "都会的スローライフ")
    assert cover.split_title("婚活ダンジョンちゃん、東京に巣食う") == ("婚活ダンジョンちゃん、東京に巣食う", "")


def test_columns_keep_phrases_whole():
    assert cover.columns("婚活ダンジョンちゃん、東京に巣食う", 11) == ["婚活ダンジョンちゃん、", "東京に巣食う"]
    assert cover.columns("あいうえおかきくけこ", 4) == ["あいうえ", "おかきく", "けこ"]


def test_fit_prefers_whole_phrases():
    size, rows = cover.fit("婚活ダンジョンちゃん、東京に巣食う", 1600 * 0.42, 2560 * 0.62, 190)
    assert cover.columns("婚活ダンジョンちゃん、東京に巣食う", rows) == ["婚活ダンジョンちゃん、", "東京に巣食う"]


@needs_font
def test_typographic_cover(tmp_path):
    img = cover.render_cover("テスト小説、東京編", "作者", "n0000aa", 2, font_path=FONT)
    assert img.size == (1600, 2560)
    data = cover.cover_jpeg(img)
    assert data[:2] == b"\xff\xd8" and len(data) < 1_500_000


@needs_font
def test_art_cover(tmp_path):
    art = tmp_path / "art.png"
    Image.new("RGB", (1024, 1536), (200, 120, 60)).save(art)
    img = cover.render_cover("テスト", "作者", "n0000aa", 2, art_path=art, font_path=FONT)
    assert img.size == (1600, 2560)
    assert img.getpixel((200, 1300))[0] > 150       # illustration visible on the left side


def _contrast(a, b):
    def lum(c):
        ch = [x / 255 for x in c]
        ch = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("color", ["auto", "indigo", "rose", "forest", "night", "sepia", "charcoal", "cream", "#3A2E5C", "#F0E6D2"])
def test_palette_is_always_readable(color):
    bg, accent, text = cover.resolve_palette(color, biggenre=1, ncode="n0000aa")
    assert _contrast(bg, text) >= 4.5, (color, bg, text)
    assert _contrast(bg, accent) >= 3.0, (color, bg, accent)


def test_light_background_gets_dark_text():
    bg, accent, text = cover.resolve_palette("cream", 2, "n0000aa")
    assert sum(text) < sum(bg)


def test_auto_palette_follows_genre():
    assert cover.resolve_palette("auto", 1, "n0000aa") != cover.resolve_palette("auto", 2, "n0000aa")


@pytest.mark.parametrize("bad", ["purple-ish", "#12345", "#GGGGGG"])
def test_invalid_color_raises(bad):
    with pytest.raises(ValueError, match="cover color"):
        cover.resolve_palette(bad, 2, "n0000aa")


@needs_font
def test_pattern_none_leaves_lower_area_plain():
    img = cover.render_cover("テスト", "作者", "n0000aa", 2, font_path=FONT, color="indigo", pattern="none")
    bottom = img.crop((450, 2100, 1200, 2300))
    assert len(bottom.getcolors(maxcolors=1 << 20)) == 1


@needs_font
def test_pattern_waves_draws_in_lower_area():
    img = cover.render_cover("テスト", "作者", "n0000aa", 2, font_path=FONT, color="indigo", pattern="waves")
    assert len(img.crop((450, 2100, 1200, 2300)).getcolors(maxcolors=1 << 20)) > 1
