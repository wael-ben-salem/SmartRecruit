"""Two chunking strategies for CVs, compared in eval/:

A. section: split on CV headings (Experience, Education, Skills...), so a chunk is one
   coherent part of the CV; long sections are split further with B.
B. recursive: fixed-size windows with overlap, split on paragraph > line > sentence > word.

Sizes are in tokens, estimated as words * 1.3 (no tokenizer dependency).
"""
import re

SECTION_WORDS = {
    "summary": ["summary", "profile", "about me", "objective", "profil", "résumé", "a propos",
                "professional summary", "executive profile", "career overview", "professional profile", "executive summary"],
    "experience": ["experience", "work experience", "professional experience", "employment",
                   "work history", "expérience", "expériences", "expérience professionnelle"],
    "education": ["education", "academic background", "formation", "formations", "diplômes", "études",
                  "education and training"],
    "skills": ["skills", "technical skills", "competencies", "core competencies", "compétences",
               "compétences techniques", "tools", "technologies", "highlights", "skill highlights",
               "core qualifications", "qualifications"],
    "projects": ["projects", "academic projects", "personal projects", "projets"],
    "certifications": ["certifications", "certificates", "certificats", "licenses", "certifications and licenses"],
    "languages": ["languages", "langues"],
    "other": ["interests", "hobbies", "centres d'intérêt", "volunteering", "activities", "awards", "publications",
              "accomplishments", "additional information", "affiliations"],
}
_HEADING_TO_SECTION = {w: s for s, words in SECTION_WORDS.items() for w in words}


def tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def _heading(line: str) -> str | None:
    clean = re.sub(r"[^\wÀ-ÿ' ]", "", line).strip().lower()
    if not clean or len(clean.split()) > 4:
        return None
    return _HEADING_TO_SECTION.get(clean)


def _page_of(lines_before: list[str]) -> int:
    page = 1
    for line in lines_before:
        m = re.match(r"\[page (\d+)\]", line.strip())
        if m:
            page = int(m.group(1))
    return page


def recursive_split(text: str, size: int = 500, overlap: int = 50,
                    separators=("\n\n", "\n", ". ", " ")) -> list[str]:
    """Split text into pieces of at most `size` tokens, with `overlap` tokens repeated between pieces."""
    if tokens(text) <= size:
        return [text.strip()] if text.strip() else []
    sep = next((s for s in separators if s in text), " ")
    parts = [p for p in text.split(sep) if p.strip()]
    chunks, current = [], []
    for part in parts:
        candidate = sep.join(current + [part])
        if current and tokens(candidate) > size:
            chunks.append(sep.join(current).strip())
            # carry the tail of the previous chunk as overlap
            tail, kept = [], 0
            for prev in reversed(current):
                kept += tokens(prev)
                if kept > overlap:
                    break
                tail.insert(0, prev)
            current = tail + [part]
        else:
            current.append(part)
    if current:
        chunks.append(sep.join(current).strip())
    # a single part may still be too long (e.g. no separators): split it with the next separator
    out = []
    for c in chunks:
        if tokens(c) > size * 1.2 and sep != separators[-1]:
            out.extend(recursive_split(c, size, overlap, separators[separators.index(sep) + 1:]))
        else:
            out.append(c)
    return out


def chunk_recursive(text: str, size: int = 500, overlap: int = 50) -> list[dict]:
    chunks = []
    for piece in recursive_split(text, size, overlap):
        m = re.search(r"\[page (\d+)\]", piece)
        page = int(m.group(1)) if m else _page_of(text[:text.find(piece[:40])].splitlines())
        chunks.append({"text": piece, "section": "unknown", "page": page})
    return chunks


def chunk_by_section(text: str, max_tokens: int = 300, overlap: int = 30) -> list[dict]:
    lines = text.splitlines()
    sections, current, name, page = [], [], "header", 1
    for i, line in enumerate(lines):
        if re.match(r"\[page \d+\]", line.strip()):
            page = int(re.findall(r"\d+", line)[0])
            continue
        heading = _heading(line)
        if heading:
            if "".join(current).strip():
                sections.append((name, current_page, "\n".join(current)))
            name, current, current_page = heading, [line], page
        else:
            if not current:
                current_page = page
            current.append(line)
    if "".join(current).strip():
        sections.append((name, current_page, "\n".join(current)))

    chunks = []
    for name, page, body in sections:
        title = body.splitlines()[0] if name != "header" else ""
        for piece in recursive_split(body, max_tokens, overlap):
            # keep the heading on every piece so the chunk says what it is about
            if title and not piece.startswith(title):
                piece = f"{title}\n{piece}"
            chunks.append({"text": piece, "section": name, "page": page})
    return chunks


def chunk(text: str, strategy: str = "section", **kw) -> list[dict]:
    if strategy == "section":
        return chunk_by_section(text, **kw)
    if strategy == "recursive":
        return chunk_recursive(text, **kw)
    raise ValueError(f"Unknown chunking strategy: {strategy}")
