"""The XML the importer sends and how it reads values back (no shop needed)."""

import xml.etree.ElementTree as ET

from importer.api import Lang, text, to_xml


def test_to_xml_writes_plain_multilingual_and_associated_fields():
    body = to_xml(
        "products",
        {
            "price": "11.780488",
            "name": Lang("Krem & balsam <nowy>"),
            "associations": {"categories": [("category", {"id": 12}), ("category", {"id": 40})]},
        },
        lang_ids=[1, 2],
    )
    product = ET.fromstring(body).find("product")
    assert product.findtext("price") == "11.780488"
    assert [(n.get("id"), n.text) for n in product.find("name")] == [
        ("1", "Krem & balsam <nowy>"),
        ("2", "Krem & balsam <nowy>"),
    ]
    assert [c.findtext("id") for c in product.find("associations/categories")] == ["12", "40"]
    # ElementTree escapes the special characters, so the text cannot break the XML
    assert b"Krem &amp; balsam &lt;nowy&gt;" in body


def test_text_reads_one_language_or_many():
    assert text("Kosmetyki") == "Kosmetyki"
    assert text([{"id": "1", "value": "Kosmetyki"}, {"id": "2", "value": "Cosmetics"}]) == "Kosmetyki"
    assert text(None) == ""
