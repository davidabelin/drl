"""Welcome banner content loading and lightweight Markdown rendering."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path


FALLBACK_MARKDOWN = """# Welcome Banner

## Hello, Mom and Joe!

The welcome copy has not been written yet.
"""


@dataclass(frozen=True, slots=True)
class WelcomeBanner:
    """Rendered welcome banner content for the home page dialog."""

    markdown: str
    html: str


def load_welcome_banner(path: str | Path) -> WelcomeBanner:
    """Load and render the welcome banner Markdown file."""

    source_path = Path(path)
    try:
        markdown = source_path.read_text(encoding="utf-8")
    except OSError:
        markdown = FALLBACK_MARKDOWN
    return WelcomeBanner(markdown=markdown, html=render_markdown(markdown))


def render_markdown(markdown: str) -> str:
    """Render the small Markdown subset used by the welcome banner."""

    blocks: list[str] = []
    paragraph: list[str] = []
    open_lists = 0

    def flush_paragraph() -> None:
        if not paragraph:
            return
        text = " ".join(item.strip() for item in paragraph if item.strip())
        if text:
            blocks.append(f"<p>{_render_inline(text)}</p>")
        paragraph.clear()

    def close_lists(target: int = 0) -> None:
        nonlocal open_lists
        while open_lists > target:
            blocks.append("</ul>")
            open_lists -= 1

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            flush_paragraph()
            close_lists()
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            close_lists()
            level = min(len(heading.group(1)), 3)
            blocks.append(f"<h{level}>{_render_inline(heading.group(2).strip())}</h{level}>")
            continue

        list_item = re.match(r"^(\s*)-\s+(.+)$", line)
        if list_item:
            flush_paragraph()
            level = len(list_item.group(1).replace("\t", "  ")) // 2
            while open_lists < level + 1:
                blocks.append("<ul>")
                open_lists += 1
            close_lists(level + 1)
            blocks.append(f"<li>{_render_inline(list_item.group(2).strip())}</li>")
            continue

        close_lists()
        paragraph.append(line)

    flush_paragraph()
    close_lists()
    return "\n".join(blocks)


def _render_inline(text: str) -> str:
    code_fragments: list[str] = []

    def stash_code(match: re.Match[str]) -> str:
        code_fragments.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\0{len(code_fragments) - 1}\0"

    text = re.sub(r"`([^`]+)`", stash_code, text)
    rendered = html.escape(text)
    rendered = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", rendered)
    for index, fragment in enumerate(code_fragments):
        rendered = rendered.replace(f"\0{index}\0", fragment)
    return rendered
