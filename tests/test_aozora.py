from syosetsu import aozora
from syosetsu.aozora import RubySpan


def test_encode():
    assert aozora.encode("東京", "とうきょう") == "｜東京《とうきょう》"


def test_encode_refuses_notation_chars():
    # base/reading containing notation characters would corrupt the line → plain base
    assert aozora.encode("a《b", "x") == "a《b"
    assert aozora.encode("東京", "と｜う") == "東京"


def test_strip():
    assert aozora.strip("　｜東京《とうきょう》の空。") == "　東京の空。"
    assert aozora.strip("ruby無し") == "ruby無し"


def test_spans_offsets_point_into_plain_text():
    line = "「｜英雄《しゅやく》だ」と｜彼《・》は言った。"
    plain = aozora.strip(line)
    got = aozora.spans(line)
    assert got == [RubySpan(1, 3, "英雄", "しゅやく"), RubySpan(6, 7, "彼", "・")]
    for s in got:
        assert plain[s.start:s.end] == s.base


def test_to_html_escapes_and_renders_ruby():
    assert aozora.to_html("A&B<｜東京《とうきょう》>") == "A&amp;B&lt;<ruby>東京<rt>とうきょう</rt></ruby>&gt;"


def test_classify():
    assert aozora.classify("東京", "とうきょう") == "reading"
    assert aozora.classify("英雄", "しゅやく") == "reading"      # gikun in hiragana: known limitation
    assert aozora.classify("彼", "・") == "emphasis"
    assert aozora.classify("彼女", "﹅﹅") == "emphasis"
    assert aozora.classify("魔法", "マジック") == "gloss"        # katakana over kanji
    assert aozora.classify("ひらがな", "かな") == "gloss"        # no kanji in base
    assert aozora.classify("剣", "Sword") == "gloss"
    assert aozora.classify("王", "おうおうおうおうお") == "gloss"  # > 4× base length
    assert aozora.classify("佐々木", "ささき") == "reading"       # 々 counts as kanji
