from motorcycle_parts_watcher.utils.i18n import (
    LANG_EN,
    LANG_JA,
    LANG_ZH,
    detect_lang,
    translate,
    translate_for_adapter,
)


# --- detect_lang -------------------------------------------------------

def test_detect_lang_english():
    assert detect_lang("exhaust") == LANG_EN
    assert detect_lang("Brembo brake pad") == LANG_EN
    assert detect_lang("") == LANG_EN


def test_detect_lang_japanese_kana():
    assert detect_lang("マフラー") == LANG_JA          # katakana
    assert detect_lang("ばってりー") == LANG_JA         # hiragana
    assert detect_lang("スズキ排気管") == LANG_JA      # mixed kana + kanji → still JA


def test_detect_lang_chinese_han_only():
    assert detect_lang("排氣管") == LANG_ZH
    assert detect_lang("煞車片") == LANG_ZH


# --- translate ---------------------------------------------------------

def test_translate_en_to_ja():
    assert translate("exhaust", LANG_JA) == "マフラー"
    assert translate("brake", LANG_JA) == "ブレーキ"


def test_translate_en_to_zh():
    assert translate("exhaust", LANG_ZH) == "排氣管"
    assert translate("brake pad", LANG_ZH) == "煞車片"


def test_translate_ja_to_zh():
    assert translate("マフラー", LANG_ZH) == "排氣管"


def test_translate_zh_to_ja():
    assert translate("排氣管", LANG_JA) == "マフラー"


def test_translate_multiword_phrase_greedy():
    # "oil filter" must match as one entry, not two separate words.
    assert translate("oil filter", LANG_JA) == "オイルフィルター"
    assert translate("oil filter", LANG_ZH) == "機油濾芯"


def test_translate_passthrough_unknown_brand():
    # Brand name not in dictionary survives unchanged.
    assert translate("Brembo", LANG_JA) == "Brembo"


def test_translate_mixed_known_and_unknown():
    # "Brembo brake" → known word translated, unknown brand passes through.
    assert translate("Brembo brake", LANG_JA) == "Brembo ブレーキ"


def test_translate_noop_when_source_equals_target():
    assert translate("exhaust", LANG_EN) == "exhaust"
    assert translate("マフラー", LANG_JA) == "マフラー"
    assert translate("排氣管", LANG_ZH) == "排氣管"


def test_translate_empty_string():
    assert translate("", LANG_JA) == ""
    assert translate(None, LANG_JA) is None or translate(None, LANG_JA) == ""


def test_translate_case_insensitive_english():
    assert translate("EXHAUST", LANG_JA) == "マフラー"
    assert translate("Brake Pad", LANG_JA) == "ブレーキパッド"


# --- translate_for_adapter --------------------------------------------

class _Adapter:
    def __init__(self, lang):
        self.preferred_query_lang = lang


def test_translate_for_adapter_with_target():
    a = _Adapter("ja")
    assert translate_for_adapter("exhaust", a) == "マフラー"


def test_translate_for_adapter_none_preference_passthrough():
    a = _Adapter(None)
    assert translate_for_adapter("exhaust", a) == "exhaust"


def test_translate_for_adapter_missing_attribute_passthrough():
    class Bare:
        pass
    assert translate_for_adapter("exhaust", Bare()) == "exhaust"


def test_translate_for_adapter_empty_query():
    a = _Adapter("ja")
    assert translate_for_adapter("", a) == ""
    assert translate_for_adapter(None, a) is None
