"""Document parsers for HTML, PDF, and Markdown with heading and table extraction."""

import re
from typing import Any, NamedTuple

from selectolax.lexbor import LexborHTMLParser as HTMLParser


class ParsedBlock(NamedTuple):
    heading_level: int | None  # 1 for H1, 2 for H2, ..., None for body/table text
    text: str
    is_table: bool = False


def html_table_to_markdown(table_node: Any) -> str:
    """Convert an HTML table node into clean GitHub-flavored markdown."""
    rows = []
    headers = []

    # Check for thead or first tr
    th_nodes = table_node.css("th")
    if th_nodes:
        headers = [th.text(strip=True).replace("\n", " ") for th in th_nodes]

    tr_nodes = table_node.css("tr")
    for tr in tr_nodes:
        td_nodes = tr.css("td")
        if not td_nodes and not headers:
            # Maybe headers inside tr
            th_in_tr = tr.css("th")
            if th_in_tr:
                headers = [th.text(strip=True).replace("\n", " ") for th in th_in_tr]
            continue
        if td_nodes:
            row = [td.text(strip=True).replace("\n", " ") for td in td_nodes]
            rows.append(row)

    if not rows and not headers:
        return ""

    if not headers and rows:
        headers = [f"Col {i + 1}" for i in range(len(rows[0]))]

    # Normalize widths
    col_count = len(headers)
    md_lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join([":---"] * col_count) + " |"]
    for row in rows:
        # pad or truncate row
        padded = row[:col_count] + [""] * max(0, col_count - len(row))
        md_lines.append("| " + " | ".join(padded) + " |")

    return "\n".join(md_lines)


def parse_html(html_content: str) -> list[ParsedBlock]:
    """Parse HTML into structural blocks preserving H1-H6 and tables as markdown."""
    blocks: list[ParsedBlock] = []

    # Check if raw text has markdown tables or mixed markdown
    if "<table" not in html_content.lower() and "|" in html_content:
        # Mixed HTML and markdown: use markdown parser with HTML tag stripping
        cleaned = re.sub(r"<h([1-6])>(.*?)</h\1>", r"\n#\1 \2\n", html_content, flags=re.IGNORECASE)
        cleaned = re.sub(r"<p>(.*?)</p>", r"\n\1\n", cleaned, flags=re.IGNORECASE)
        return parse_markdown_or_text(cleaned)

    parser = HTMLParser(html_content)
    root = parser.body if parser.body else parser.root
    if not root:
        return [ParsedBlock(heading_level=None, text=html_content.strip())]

    for node in root.traverse():
        tag = node.tag
        if not tag:
            continue
        tag = tag.lower()

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            text = node.text(strip=True)
            if text:
                blocks.append(ParsedBlock(heading_level=level, text=text))
        elif tag == "table":
            table_md = html_table_to_markdown(node)
            if table_md:
                blocks.append(ParsedBlock(heading_level=None, text=table_md, is_table=True))
        elif tag in ("p", "li", "blockquote") and not node.css("table"):
            text = node.text(strip=True)
            if text and len(text) > 2:
                # Check if text contains markdown table rows
                if "|" in text and "\n|" in text:
                    sub_blocks = parse_markdown_or_text(text)
                    blocks.extend(sub_blocks)
                else:
                    blocks.append(ParsedBlock(heading_level=None, text=text))

    if not blocks:
        raw_text = root.text(strip=True)
        if raw_text:
            blocks = parse_markdown_or_text(raw_text)

    return blocks


def parse_markdown_or_text(text: str) -> list[ParsedBlock]:
    """Parse markdown text splitting on markdown headings and preserving markdown tables."""
    blocks: list[ParsedBlock] = []
    lines = text.split("\n")
    current_body: list[str] = []
    in_table: bool = False
    current_table: list[str] = []

    def flush_body() -> None:
        if current_body:
            content = "\n".join(current_body).strip()
            if content:
                blocks.append(ParsedBlock(heading_level=None, text=content))
            current_body.clear()

    def flush_table() -> None:
        if current_table:
            content = "\n".join(current_table).strip()
            if content:
                blocks.append(ParsedBlock(heading_level=None, text=content, is_table=True))
            current_table.clear()

    for line in lines:
        stripped = line.strip()
        # Check markdown table row
        if stripped.startswith("|") and stripped.endswith("|"):
            flush_body()
            in_table = True
            current_table.append(stripped)
            continue
        elif in_table:
            flush_table()
            in_table = False

        # Check markdown heading
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            flush_body()
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            blocks.append(ParsedBlock(heading_level=level, text=heading_text))
        else:
            if stripped:
                current_body.append(stripped)

    flush_table()
    flush_body()
    return blocks
