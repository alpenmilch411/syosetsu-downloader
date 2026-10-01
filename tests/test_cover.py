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
