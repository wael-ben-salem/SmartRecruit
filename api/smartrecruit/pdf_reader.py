"""Multimodal PDF reading.

Router per page:
  - enough clean text  -> text layer (PyMuPDF, sorted in reading order), no model call
  - little / no text (scan) or multi-column layout -> page rendered to PNG and read by a vision model
"""
import re

import pymupdf

from . import config, llm, prompts


def _text_quality(page: pymupdf.Page) -> tuple[str, int]:
    """Return the page text and the number of text columns detected."""
    lines = [l["bbox"] for b in page.get_text("dict")["blocks"] if b.get("type") == 0
             for l in b["lines"] if "".join(s["text"] for s in l["spans"]).strip()]
    text = page.get_text("text", sort=True)
    return text, _columns(lines, page.rect.width)


def _columns(lines: list[tuple], width: float) -> int:
    """2 if a vertical gutter splits the page into two columns of text lines side by side, else 1."""
    for x in range(int(width * 0.2), int(width * 0.7), 4):
        if any(x0 < x < x1 for x0, _, x1, _ in lines):
            continue  # a line crosses this x: not a gutter
        left = [l for l in lines if l[2] <= x]
        right = [l for l in lines if l[0] >= x]
        if len(left) >= 3 and len(right) >= 3:
            # both sides must share vertical space, otherwise it's just indentation
            top, bottom = max(min(l[1] for l in left), min(l[1] for l in right)), min(max(l[3] for l in left), max(l[3] for l in right))
            if bottom - top > 100:
                return 2
    return 1


def _render_png(page: pymupdf.Page, dpi: int = 150) -> bytes:
    return page.get_pixmap(dpi=dpi).tobytes("png")


def route_page(page: pymupdf.Page) -> tuple[str, str]:
    """Decide how to read one page. Returns (method, reason)."""
    text, columns = _text_quality(page)
    chars = len(re.sub(r"\s", "", text))
    if chars < config.MIN_CHARS_PER_PAGE:
        # a short last page of a text CV is not a scan: only pages that carry an image go to vision
        if page.get_images():
            return "vision", f"only {chars} characters of text and an image: scanned page"
        return "text", f"short page ({chars} characters), no image"
    if columns > 1:
        return "vision", "multi-column layout: text layer would mix columns"
    return "text", f"{chars} characters, single column"


def read_pdf(path: str, use_vision: bool = True) -> dict:
    """Read a PDF into pages of text, recording which method was used for each page."""
    doc = pymupdf.open(path)
    pages = []
    for i, page in enumerate(doc, start=1):
        method, reason = route_page(page)
        text, _ = _text_quality(page)
        if method == "vision" and use_vision:
            system, user = prompts.load("vision_reader")
            out = llm.vision_json(system, prompts.render(user, page_number=i), [_render_png(page)])
            text = out.get("text", "")
        elif method == "vision":
            reason += " (vision disabled: text layer kept)"
            method = "text"
        pages.append({"page": i, "method": method, "reason": reason, "text": text.strip()})
    return {"pages": pages, "full_text": "\n\n".join(f"[page {p['page']}]\n{p['text']}" for p in pages)}


def read_text_file(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return {"pages": [{"page": 1, "method": "text", "reason": "plain text file", "text": text}],
            "full_text": f"[page 1]\n{text}"}


def read_any(path: str, use_vision: bool = True) -> dict:
    return read_pdf(path, use_vision) if path.lower().endswith(".pdf") else read_text_file(path)
