from motorcycle_parts_watcher.services.catalog_sync import _MF_LINK_RE, _parse_md_variants


def test_mf_link_regex_extracts_makers():
    html = """
    <a href="https://www.webike.tw/mf/HONDA/00">HONDA</a>
    <a href="/mf/HARLEY-DAVIDSON/00">HD</a>
    <a href="/mf/TW_SUZUKI/00">TW Suzuki</a>
    <a href="/mf/honda/00">lowercase ignored</a>
    """
    found = {m.group(1) for m in _MF_LINK_RE.finditer(html)}
    assert found == {"HONDA", "HARLEY-DAVIDSON", "TW_SUZUKI"}


def test_parse_md_variants_year_ranges():
    html = """
    <a class="hover-sub-font-primary text-dark" href="/md/679/kt/3145" title="x" value="3145">年式 : 1981 ~ 1982 型式 : GS110X</a>
    <a class="hover-sub-font-primary text-dark" href="/md/679/kt/3146" title="x" value="3146">年式 : 1983 ~ 1986 型式 : GS110X</a>
    <a class="hover-sub-font-primary text-dark" href="/md/679/kt/3145" title="dup" value="3145">年式 : 1981 ~ 1982 型式 : GS110X</a>
    """
    variants = _parse_md_variants(html, "https://www.webike.tw/md/679", current_year=2026)
    assert variants == [
        (1981, 1982, "https://www.webike.tw/md/679/kt/3145"),
        (1983, 1986, "https://www.webike.tw/md/679/kt/3146"),
    ]


def test_parse_md_variants_open_ended_uses_current_year():
    html = '<a href="/md/687/kt/10653">年式 : 2021 ~   型式 : 8BL-EJ11A</a>'
    variants = _parse_md_variants(html, "https://www.webike.tw/md/687", current_year=2026)
    assert variants == [(2021, 2026, "https://www.webike.tw/md/687/kt/10653")]


def test_parse_md_variants_no_matches_returns_empty():
    assert _parse_md_variants("<html>no variants here</html>", "https://x", 2026) == []
