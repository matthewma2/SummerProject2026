import json
import re
import unicodedata
from pathlib import Path

src = Path("jsl_citations_data/3c_more_than_43.json")
authors_path = Path("databases/authors.json")

with_author_path = Path("jsl_citations_data/4a_with_authors.json")
without_author_path = Path("jsl_citations_data/4b_no_authors.json")

items = json.loads(src.read_text(encoding="utf-8"))
authors = json.loads(authors_path.read_text(encoding="utf-8"))

SPECIAL = str.maketrans({
    "Ł": "L", "ł": "l",
    "Ø": "O", "ø": "o",
    "Đ": "D", "đ": "d",
    "Æ": "Ae", "æ": "ae",
    "Œ": "Oe", "œ": "oe",
    "0": "O",
})


def norm(s):
    s = str(s).translate(SPECIAL)
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    return re.sub(r"\s+", " ", s)


full_terms = set()
surname_terms = set()


def is_first_name_only(term, full_name):
    if not term or not full_name:
        return False

    term_norm = norm(term)
    full_tokens = norm(full_name).split()
    return len(full_tokens) > 1 and term_norm == full_tokens[0]


for author in authors:
    full = author.get("full_name") or author.get("name") or ""
    if full:
        n = norm(full)
        full_terms.add(n)
        toks = n.split()
        if toks:
            surname_terms.add(toks[-1])

    for alt in author.get("alternative_names") or []:
        if is_first_name_only(alt, full):
            continue

        n = norm(alt)
        if not n:
            continue
        if len(n.split()) > 1:
            full_terms.add(n)
        else:
            surname_terms.add(n)

full_terms = sorted(full_terms, key=lambda x: (-len(x), x))
surname_terms = sorted(surname_terms, key=lambda x: (-len(x), x))
compact_full_terms = {
    term.replace(" ", "")
    for term in full_terms
    if len(term.replace(" ", "")) >= 6
}

particles = r"(?:van|von|de|del|der|den|di|du|le|la|v)"
initial = r"(?:[A-ZÀ-ÖØ-Þ0]\.|[A-ZÀ-ÖØ-Þ])"
word = r"[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ\u0100-\u017f\x27-]+"

init_name_pat = re.compile(
    rf"^(?:{initial}\s*){{1,5}}(?:{particles}\s+)?{word}(?:\s+{word})?"
    rf"(?:\s+(?:and|et|und)\s+(?:{initial}\s*){{1,5}}"
    rf"(?:{particles}\s+)?{word}(?:\s+{word})?)*"
    rf"(?=\s*[,.:;]|\s+in\b|\s*\(|\s+\d{{4}}\b)",
    re.UNICODE,
)

inverted_pat = re.compile(
    rf"^{word},\s*(?:{initial}\s*){{1,5}}(?=\s|\.|,)",
    re.UNICODE,
)

uppercase_name_no_delim_pat = re.compile(
    rf"^(?:(?:{initial}\s*){{1,5}})?"
    rf"[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ]*\s+"
    rf"(?:(?:{initial}\s*){{0,3}})?"
    rf"[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þa-zà-öø-ÿ]+"
    rf"(?=\s+[A-ZÀ-ÖØ-Þ\x27\"]|\s+\d)",
    re.UNICODE,
)

not_author_starts = re.compile(
    r"^(?:this journal|the journal|journal|mathematical reviews?|zentralblatt|"
    r"vol\.?|bd\.?|pp?\.?|s\.?|rule\b|compare\b|see\b|siehe\b|vom\b|"
    r"paper\b|proceedings\b|corrections\b|revised edition\b|second edition\b|"
    r"ibid\b|idem\b|the\s+|a\s+|an\s+|on\s+|formal\b|some\b|grundlagen\b|"
    r"grundzuge\b|grundzüge\b|die\b|uber\b|über\b|zur\b|introduction\b|"
    r"methods\b|system\b|theory\b|postulates\b|a note\b|a correction\b)",
    re.IGNORECASE,
)

context_pat = re.compile(
    r"\b(?:journal|logic|mathematics|mathematical|mind|theoria|studia|"
    r"fundamenta|annalen|review|press|vol\.?|pp?\.?|\d{4})\b",
    re.IGNORECASE,
)


def known_full_prefix(s):
    ns = norm(s)
    padded = ns + " "
    if any(padded.startswith(term + " ") for term in full_terms):
        return True

    compact = ns.replace(" ", "")
    return any(compact.startswith(term) for term in compact_full_terms)


def _is_initial_token(token):
    return len(token) == 1


def known_surname_anchor_prefix(s):
    t = s.strip()
    ns = norm(t)
    tokens = ns.split()

    while tokens and _is_initial_token(tokens[0]):
        tokens.pop(0)

    if not tokens or tokens[0] not in surname_terms:
        return False

    surname = tokens[0]
    raw_match = re.match(
        r"^(?:[A-Za-zÀ-ÖØ-öø-ÿ0]\.?\s*){0,5}"
        r"([A-Za-zÀ-ÖØ-öø-ÿĀ-ſ'-]+)",
        t,
    )
    raw_anchor = raw_match.group(1) if raw_match else ""

    if re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿĀ-ſ]+[\x27’]s\b", t):
        return True

    if re.match(rf"^(?:[A-Za-zÀ-ÖØ-öø-ÿ0]\.?\s*){{0,5}}{re.escape(raw_anchor)}[\x27’]s\b", t):
        return True

    if len(tokens) >= 2 and tokens[1] in {"in", "reviewing", "recently"}:
        return True

    if re.match(r"^[^,.;:()]+(?:[,.;:]|\s+\d{4}\b|\s+in\b|\s*\()", t, re.IGNORECASE):
        return True

    # No punctuation, but a known surname followed by title-ish metadata is still
    # usually an author lead in this corpus: "S. C. KLEENE General recursive..."
    return bool(context_pat.search(t))


def known_surname_prefix(s):
    t = s.strip()
    ns = norm(t)
    first = ns.split(" ", 1)[0] if ns else ""

    if first not in surname_terms:
        return False

    if re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿĀ-ſ]+[\x27’]s\b", t):
        return True

    return bool(
        re.match(
            r"^[^,.;:()]+(?:[,.;:]|\s+\d{4}\b|\s+in\b|\s*\()",
            t,
            re.IGNORECASE,
        )
    )


def starts_with_author(s):
    t = s.strip().strip("\ufeff")

    if not t or not re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿĀ-ſ]", t):
        return False

    full_prefix = known_full_prefix(t)
    surname_anchor_prefix = known_surname_anchor_prefix(t)

    blocked = not_author_starts.match(t)
    if blocked and not full_prefix and not surname_anchor_prefix:
        return False

    if full_prefix:
        return True

    if inverted_pat.match(t):
        return True

    if init_name_pat.match(t):
        return True

    if surname_anchor_prefix:
        return True

    if known_surname_prefix(t):
        return True

    if uppercase_name_no_delim_pat.match(t) and context_pat.search(t):
        return True

    return False


with_author = []
without_author = []

for item in items:
    if starts_with_author(item):
        with_author.append(item)
    else:
        without_author.append(item)

with_author_path.write_text(
    json.dumps(with_author, indent=4, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

without_author_path.write_text(
    json.dumps(without_author, indent=4, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

print(
    f"total={len(items)} "
    f"with_author={len(with_author)} "
    f"no_author={len(without_author)}"
)
print(with_author_path)
print(without_author_path)
