"""Remove direct identifiers before any text reaches the LLM agents.

Regex for contact details, a heuristic for the candidate's name (the first line of the CV
that looks like a person's name, or a first name / last name split over two lines next to the
contact details, as two-column layouts produce), removal of birth date / gender / nationality
lines, and inline removal of age, family status and street addresses.
Measured with scripts/eval_anonymization.py.
"""
import re

PATTERNS = {
    "EMAIL": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "URL": r"(?:https?://|www\.)\S+|(?:linkedin|github)\.com/\S+",
    "PHONE": r"(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,5}\d{2,4}",
}
SENSITIVE_LINE = re.compile(
    r"^.*\b(date of birth|born on|birth date|né[e]? le|date de naissance|age\s*:|âge\s*:|"
    r"gender|sexe|marital status|situation familiale|nationality|nationalité)\b.*$",
    re.I | re.M,
)
# replaced inside the line, so the rest of the sentence ("27 years old data analyst") is kept
INLINE = {
    "AGE": re.compile(r"\b(?:age|âge)\s*:?\s*\d{2}\b(?:\s*ans)?|\b\d{2}\s*(?:years old|-year-old|ans)\b", re.I),
    # only in list-like positions ("Age: 27 · Married", "..., single, ..."): "single instance" is common in IT CVs
    "FAMILY STATUS": re.compile(r"(?<![\w-])(?:married|single|divorced|widowed|célibataire|mariée?|divorcée?|veuve?)"
                                r"(?=\s*(?:[,·|;\n]|$|\(|with\s+\d|\d+\s+child))", re.I | re.M),
    "ADDRESS": re.compile(
        r"\b(?:\d{1,5}\s*,?\s*(?:bis|ter)?\s*)?(?i:rue|avenue|boulevard|bd|impasse|chemin|allée)\s+"
        r"(?:de\s+la\s+|de\s+l'|du\s+|des\s+|de\s+|d')?[A-ZÀ-Ý][^\n,·|]*"
        r"|\b\d{1,5}\s+(?:[A-Z][\w'.-]*\s+){1,4}(?:Street|St\.?|Road|Rd\.?|Avenue|Ave\.?|Lane|Ln\.?|Terrace|Drive|Dr\.?"
        r"|Way|Boulevard|Blvd\.?|Court|Ct\.?)\b"),
}
# referees' names are third-party personal data ("Supervisor: Mr. John Ciesiolka (254-553-5006)")
THIRD_PARTY = re.compile(r"\b(Supervisor|Reference|Referee|Contact)(\s*:\s*|\s+-\s+)"
                         r"((?:(?:Mr|Mrs|Ms|Dr)\.?\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})")
CONTACT_HINT = re.compile(r"@|\+?\d[\d\s().-]{7,}|contact", re.I)
NAME_LINE = re.compile(r"^[A-ZÀ-Ý][a-zà-ÿ'-]+(?:\s+[A-ZÀ-Ý][A-Za-zà-ÿ'-]+){1,3}$")
HEADINGS = {"curriculum vitae", "resume", "cv", "profile", "summary", "experience", "education", "skills"}
# Many CVs start with the job title in capitals ("ASSISTANT FOOTBALL COACH", "IT SPECIALIST"): not a name
JOB_WORDS = re.compile(
    r"\b(manager|specialist|engineer|developer|director|technician|analyst|assistant|consultant|coach|intern|"
    r"administrator|officer|coordinator|supervisor|lead|senior|junior|head|chief|president|associate|teacher|"
    r"designer|architect|scientist|accountant|advisor|representative|executive|clerk|nurse|chef|sales|support|"
    r"information|technology|data|software|it|systems?|network|integrator|operations|project|program|business|services?|"
    r"ingénieur|développeur|chef|stagiaire|responsable|technicien)\b", re.I)


def find_name(text: str) -> str | None:
    for line in text.splitlines()[:8]:
        line = line.strip()
        if line.startswith("[page"):
            continue
        if line.lower() in HEADINGS or JOB_WORDS.search(line):
            continue
        if NAME_LINE.match(line) or (line.isupper() and 2 <= len(line.split()) <= 4 and line.replace(" ", "").isalpha()):
            return line
    return _split_name(text)


def _is_name_word(line: str) -> bool:
    w = line.strip()
    return (len(w.split()) == 1 and w[:1].isupper() and w.replace("-", "").replace("'", "").isalpha()
            and w.lower() not in HEADINGS and not JOB_WORDS.search(w) and not w.isupper())


def _split_name(text: str) -> str | None:
    """'Youssef' / 'Haddad' on two lines, right next to an e-mail, a phone or a CONTACT heading."""
    lines = [l.strip() for l in text.splitlines()]
    for i in range(len(lines) - 1):
        if _is_name_word(lines[i]) and _is_name_word(lines[i + 1]):
            around = " ".join(lines[max(0, i - 2):i] + lines[i + 2:i + 4])
            if CONTACT_HINT.search(around):
                return f"{lines[i]} {lines[i + 1]}"
    return None


def anonymize(text: str, candidate_id: str) -> dict:
    removed = {}
    name = find_name(text)
    if name:
        for part in [name] + [p for p in name.split() if len(p) > 2]:
            text, n = re.subn(rf"\b{re.escape(part)}\b", f"[{candidate_id}]" if part == name else "[NAME]", text, flags=re.I)
            removed["NAME"] = removed.get("NAME", 0) + n
    text, n = SENSITIVE_LINE.subn("[REMOVED: sensitive attribute]", text)
    if n:
        removed["SENSITIVE"] = n
    for label, pattern in INLINE.items():
        text, n = pattern.subn(f"[{label}]", text)
        if n:
            removed[label] = n
    text, n = THIRD_PARTY.subn(r"\1\2[THIRD PARTY]", text)
    if n:
        removed["THIRD PARTY"] = n
    for label, pattern in PATTERNS.items():
        text, n = re.subn(pattern, _replacer(label), text)
        n = text.count(f"[{label}]")
        if n:
            removed[label] = n
    return {"text": text, "removed": removed}


YEAR_RANGE = re.compile(r"^\s*(19|20)\d{2}\s*[-–/.]?\s*((19|20)\d{2})?\s*$")


def _only_years(s: str) -> bool:
    """'2003) 2003' or '2019 2021': numbers that are all years are not a phone number."""
    groups = re.findall(r"\d+", s)
    return all(len(g) == 4 and g[:2] in ("19", "20") for g in groups)


def _replacer(label: str):
    def repl(m: re.Match) -> str:
        s = m.group(0)
        # date ranges such as "2019 - 2022" look like phone numbers to the regex: keep them
        if label == "PHONE" and (sum(c.isdigit() for c in s) < 8 or YEAR_RANGE.match(s) or _only_years(s)):
            return s
        return f"[{label}]"
    return repl
