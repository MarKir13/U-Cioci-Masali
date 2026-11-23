"""Tests of the HTML cleaning of brand pages. They do not use the network."""

import pytest

from scraper.models import Brand, FaqItem
from scraper.sanitize import clean_fragment

BASE = "https://www.magiczne-indie.pl/brand/3-himalaya"


def test_only_the_tags_of_the_source_stay():
    html = "<div><h2>A</h2><h3>B</h3><p>x <strong>y</strong></p><ul><li>z</li></ul><em>e</em><span>s</span></div>"
    # <em> and <span> are removed, their text stays (outside any block, so it becomes a paragraph)
    assert clean_fragment(html, BASE) == (
        "<h2>A</h2>\n<h3>B</h3>\n<p>x <strong>y</strong></p>\n<ul><li>z</li></ul>\n<p>es</p>"
    )


def test_scripts_and_styles_are_removed_with_their_content():
    html = "<p>Tekst</p><script>alert(1)</script><style>p {color: red}</style><button>Czytaj więcej</button>"
    assert clean_fragment(html, BASE) == "<p>Tekst</p>"


def test_event_handlers_and_other_attributes_are_removed():
    html = (
        '<p onclick="steal()" style="color:red" class="x" id="y">A '
        '<a href="/335-x" onmouseover="x()" target="_blank">b</a></p>'
    )
    cleaned = clean_fragment(html, BASE)
    assert cleaned == '<p>A <a href="https://www.magiczne-indie.pl/335-x">b</a></p>'


@pytest.mark.parametrize("href", ["javascript:alert(1)", "data:text/html,<b>x</b>", "", "#faq"])
def test_a_link_without_an_http_address_becomes_its_text(href):
    assert clean_fragment(f'<p><a href="{href}">tekst</a></p>', BASE) == "<p>tekst</p>"


def test_whitespace_is_collapsed_and_blocks_are_on_separate_lines():
    html = "<p>\n   Jeden\n   dwa  </p>\n\n<ul>\n <li> a </li>\n <li>b</li>\n</ul><!-- komentarz -->"
    assert clean_fragment(html, BASE) == "<p>Jeden dwa</p>\n<ul><li>a</li>\n<li>b</li></ul>"


def test_editor_markup_becomes_plain_paragraphs():
    """Hari Tea and Shoti Maa use <address>, <span>, <br> and text outside any paragraph."""
    html = (
        '<address><strong><span style="x">Tytuł&nbsp;</span></strong></address>'
        "<address><span><br></span></address>"
        "<address><span>Jeden<br><br>Dwa <strong>trzy</strong></span></address>"
        "<address>&nbsp;</address>"
        "<span><strong>Luzem</strong> tekst<br>w jednej linii<br><br>Nowy akapit</span>"
    )
    assert clean_fragment(html, BASE) == (
        "<p><strong>Tytuł </strong></p>\n<p>Jeden</p>\n<p>Dwa <strong>trzy</strong></p>\n"
        "<p><strong>Luzem</strong> tekst w jednej linii</p>\n<p>Nowy akapit</p>"
    )


def test_paragraphs_without_text_are_dropped():
    assert clean_fragment("<p><br></p><p>&nbsp;</p><p>A</p>", BASE) == "<p>A</p>"


def test_polish_letters_and_quotes_stay_as_they_are():
    assert clean_fragment("<p>„Zastrzyk” — żółć &amp; więcej</p>", BASE) == "<p>„Zastrzyk” — żółć &amp; więcej</p>"


# The model rejects active content even if a parser lets it through


@pytest.mark.parametrize(
    "html",
    [
        "<p>a</p><script>x</script>",
        "<style>p{}</style><p>a</p>",
        '<p onclick="x()">a</p>',
        '<a href="/x" ONMOUSEOVER = "x">a</a>',
    ],
)
def test_a_brand_description_with_active_content_is_invalid(html):
    with pytest.raises(ValueError, match="script|style|event handler"):
        Brand(name="Test", description=html)


def test_an_faq_answer_with_active_content_is_invalid():
    with pytest.raises(ValueError):
        FaqItem(question="Pytanie?", answer='<p onclick="x()">Odpowiedź</p>')


def test_text_that_only_mentions_a_word_like_on_is_valid():
    assert Brand(name="Test", description="<p>Wsparcie on-line: a=b, onboarding = ok</p>").description


def test_a_link_to_the_source_loses_its_query_and_fragment():
    """Editor preview links of the source carry its back-office token, its admin folder and an employee id."""
    html = (
        '<p><a href="https://www.magiczne-indie.pl/1537-pack.html'
        '?adtoken=abc123&amp;ad=admin9&amp;id_employee=7#x">A</a> '
        '<a href="/12-b?adtoken=zzz&amp;ad=admin9">B</a> '
        '<a href="https://magiczne-indie.pl/13-c?adtoken=yyy">C</a></p>'
    )
    cleaned = clean_fragment(html, BASE)
    assert cleaned == (
        '<p><a href="https://www.magiczne-indie.pl/1537-pack.html">A</a> '
        '<a href="https://www.magiczne-indie.pl/12-b">B</a> '
        '<a href="https://magiczne-indie.pl/13-c">C</a></p>'
    )
    assert "adtoken" not in cleaned
    assert "admin" not in cleaned


def test_a_link_to_another_site_keeps_its_query():
    html = '<p><a href="https://example.org/a?b=1&amp;c=2">Inny</a></p>'
    assert clean_fragment(html, BASE) == html
