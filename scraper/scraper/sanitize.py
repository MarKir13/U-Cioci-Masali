"""Cleaning of HTML taken from the source shop, so that only the tags the source uses reach the results."""

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

# The tags the source's brand pages use. Any other tag is removed and its text stays.
ALLOWED_TAGS = {"h2", "h3", "p", "ul", "li", "strong", "a"}
# Tags removed together with everything inside them: they hold code, not text
DROPPED_WITH_CONTENT = {"script", "style", "noscript", "template", "iframe", "object", "embed", "svg", "button"}
# Containers that the source's editor uses for a paragraph (`<address>` on Hari Tea): they become <p>
PARAGRAPH_LIKE = {"address", "div", "section", "article", "blockquote", "center"}
# Only these link schemes are kept (no javascript:, data:)
LINK_SCHEMES = {"http", "https"}

BLOCK = r"(?:p|h2|h3|ul|li)"
BLOCK_NAMES = ["h2", "h3", "ul", "p", *sorted(PARAGRAPH_LIKE)]


def has_text(node) -> bool:
    return bool(node.get_text().replace("\xa0", " ").strip())


def is_break(node) -> bool:
    return isinstance(node, Tag) and node.name == "br"


def split_at_double_breaks(paragraph: Tag, soup: BeautifulSoup) -> list[Tag]:
    """The paragraph as several, cut where two or more `<br>` follow each other (an editor's way to end one).

    Only `<br>` that are direct children count. A single `<br>` is left for the caller to turn into a space.
    """
    groups: list[list] = [[]]
    children = list(paragraph.children)
    i = 0
    while i < len(children):
        if is_break(children[i]):
            j = i
            count = 0
            while j < len(children) and (
                is_break(children[j]) or (isinstance(children[j], NavigableString) and not children[j].strip())
            ):
                count += is_break(children[j])
                j += 1
            if count >= 2:
                groups.append([])
                i = j
                continue
        groups[-1].append(children[i])
        i += 1
    result = []
    for group in groups:
        new = soup.new_tag("p")
        for child in group:
            new.append(child.extract())
        result.append(new)
    return result


def _same_site(host: str | None, source_host: str | None) -> bool:
    """True if both hosts are the source shop (with or without `www.`)."""
    if not host or not source_host:
        return False
    return host.removeprefix("www.") == source_host.removeprefix("www.")


def clean_fragment(html: str, base_url: str) -> str:
    """The HTML fragment with only ALLOWED_TAGS, no attributes except `href` (absolute) on links, no comments.

    Scripts, styles and buttons are removed with their content. Event handlers (`onclick=`) and `style=`
    attributes go with all other attributes. A link without a http(s) address is replaced by its text. The editor
    markup of the source (`<address>` or text outside any paragraph, `<span>`, `<br>`) is turned into plain
    paragraphs: two `<br>` end a paragraph, one is a space, and paragraphs with no text are dropped. Whitespace is
    collapsed, with one block element per line.
    """
    soup = BeautifulSoup(f"<div>{html}</div>", "html.parser")
    root = soup.div
    for comment in root.find_all(string=lambda node: isinstance(node, Comment)):
        comment.extract()
    for tag in root.find_all(True):
        if tag.decomposed:  # inside a tag that was removed already
            continue
        if tag.name in DROPPED_WITH_CONTENT:
            tag.decompose()
        elif tag.name in PARAGRAPH_LIKE:
            if tag.find(BLOCK_NAMES):  # a wrapper around paragraphs and headings
                tag.unwrap()
            else:
                tag.name = "p"
                tag.attrs = {}
        elif tag.name == "br":
            continue
        elif tag.name not in ALLOWED_TAGS:
            tag.unwrap()
        elif tag.name == "a":
            raw = tag.get("href", "").strip()
            href = urljoin(base_url, raw)
            parts = urlparse(href)
            # An empty or in-page link would point at the brand page itself once made absolute
            if raw and not raw.startswith("#") and parts.scheme in LINK_SCHEMES:
                if _same_site(parts.hostname, urlparse(base_url).hostname):
                    # Editor preview links of the source carry its back-office token (adtoken), the name of its
                    # admin folder (ad) and an employee id; nothing in the query or fragment is needed
                    href = parts._replace(query="", fragment="").geturl()
                tag.attrs = {"href": href}
            else:
                tag.unwrap()
        else:
            tag.attrs = {}

    # Text, links and bold text outside any block (the editor did not wrap them) become paragraphs
    block_names = {"p", "h2", "h3", "ul"}
    run: list = []

    def close_run() -> None:
        if run:
            paragraph = soup.new_tag("p")
            run[0].insert_before(paragraph)
            for node in run:
                paragraph.append(node.extract())
            run.clear()

    for child in list(root.children):
        if isinstance(child, Tag) and child.name in block_names:
            close_run()
        else:
            run.append(child)
    close_run()

    for paragraph in root.find_all("p"):
        parts = split_at_double_breaks(paragraph, soup) if paragraph.find("br", recursive=False) else [paragraph]
        if parts != [paragraph]:
            for part in reversed(parts):
                paragraph.insert_after(part)
            paragraph.decompose()
    for br in root.find_all("br"):
        br.replace_with(" ")
    for paragraph in root.find_all("p"):
        if not has_text(paragraph):
            paragraph.decompose()

    text = "".join(str(child) for child in root.children)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(rf"(<{BLOCK}>)\s+", r"\1", text)
    text = re.sub(rf"\s+(</{BLOCK}>)", r"\1", text)
    text = re.sub(rf"(</{BLOCK}>)\s*(<{BLOCK}>)", r"\1\n\2", text)
    return text.strip()
