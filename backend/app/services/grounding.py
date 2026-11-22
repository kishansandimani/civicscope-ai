"""Check that an AI-quoted piece of evidence really appears in the source text."""
import re
import unicodedata


def normalise(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    return re.sub(r"\s+", " ", s).strip().casefold()


def evidence_in_text(evidence: str, source_text: str, min_len: int = 12) -> bool:
    e = normalise(evidence).strip(" .…\"'")
    if len(e) < min_len:
        return False
    return e in normalise(source_text)
