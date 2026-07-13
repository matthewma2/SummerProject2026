#!/usr/bin/env python3
"""Build databases/journals.json from journal fields in works.json."""

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


WORKS_PATH = Path("databases/works.json")
OUTPUT_PATH = Path("databases/journals.json")
MIN_TOTAL_COUNT = 5


ABBREVIATIONS = {
    "acad": "academy",
    "accad": "accademia",
    "amer": "american",
    "ann": "annals",
    "appl": "applied",
    "arch": "archive",
    "beitr": "beitrage",
    "ber": "berichte",
    "bol": "bollettino",
    "boll": "bollettino",
    "bull": "bulletin",
    "cl": "classe",
    "comptes": "comptes",
    "cr": "comptes rendus",
    "d": "deutsche",
    "deutsch": "deutsche",
    "ens": "enseignement",
    "fil": "filozoficzny",
    "fortschr": "fortschritte",
    "fund": "fundamenta",
    "ges": "gesellschaft",
    "int": "international",
    "jahresb": "jahresbericht",
    "jour": "journal",
    "jr": "journal",
    "j": "journal",
    "lond": "london",
    "math": "mathematicae",
    "mat": "mathematicae",
    "metaph": "metaphysique",
    "mor": "morale",
    "monatsh": "monatshefte",
    "m": "mathematiker",
    "nat": "national",
    "nauk": "nauk",
    "phil": "philosophy",
    "philos": "philosophy",
    "phys": "physik",
    "proc": "proceedings",
    "przegl": "przeglad",
    "rev": "revue",
    "rend": "rendiconti",
    "r": "reine",
    "sci": "sciences",
    "soc": "society",
    "trans": "transactions",
    "ver": "vereinigung",
    "viertelj": "vierteljahrsschrift",
    "wiss": "wissenschaftliche",
    "z": "zeitschrift",
}


MANUAL_CANONICAL = {
    "the journal of symbolic logic": "The Journal of Symbolic Logic",
    "journal of symbolic logic": "The Journal of Symbolic Logic",
    "journal symbolic logic": "The Journal of Symbolic Logic",
    "mind": "Mind",
    "the monist": "The Monist",
    "monist": "The Monist",
    "math annalen": "Mathematische Annalen",
    "mathematische annalen": "Mathematische Annalen",
    "math z": "Mathematische Zeitschrift",
    "mathematische zeitschrift": "Mathematische Zeitschrift",
    "bull amer math soc": "Bulletin of the American Mathematical Society",
    "bulletin of the american mathematical society": "Bulletin of the American Mathematical Society",
    "trans amer math soc": "Transactions of the American Mathematical Society",
    "transactions of the american mathematical society": "Transactions of the American Mathematical Society",
    "amer jour math": "American Journal of Mathematics",
    "american journal of mathematics": "American Journal of Mathematics",
    "annals of mathematics": "Annals of Mathematics",
    "annals of math": "Annals of Mathematics",
    "annals mathematics": "Annals of Mathematics",
    "fund math": "Fundamenta Mathematicae",
    "fundamenta mathematicae": "Fundamenta Mathematicae",
    "monatsh math phys": "Monatshefte für Mathematik und Physik",
    "monatshefte fur mathematik und physik": "Monatshefte für Mathematik und Physik",
    "monatshefte für mathematik und physik": "Monatshefte für Mathematik und Physik",
    "rev metaph mor": "Revue de Métaphysique et de Morale",
    "revue de metaphysique et de morale": "Revue de Métaphysique et de Morale",
    "revue de métaphysique et de morale": "Revue de Métaphysique et de Morale",
    "przegl fil": "Przegląd Filozoficzny",
    "przeglad filozoficzny": "Przegląd Filozoficzny",
    "przegląd filozoficzny": "Przegląd Filozoficzny",
    "l ens math": "L'Enseignement Mathématique",
    "l enseignement mathematique": "L'Enseignement Mathématique",
    "l enseignement mathématique": "L'Enseignement Mathématique",
    "jour philos": "Journal of Philosophy",
    "jour philos etc": "Journal of Philosophy, Psychology and Scientific Methods",
    "journal of philosophy": "Journal of Philosophy",
    "the journal of philosophy": "Journal of Philosophy",
    "the philosophical review": "The Philosophical Review",
    "philosophical review": "The Philosophical Review",
    "philosophy of science": "Philosophy of Science",
    "philosophy science": "Philosophy of Science",
    "proc london math soc": "Proceedings of the London Mathematical Society",
    "proceedings of the london mathematical society": "Proceedings of the London Mathematical Society",
    "proceedings of the cambridge philosophical society": "Proceedings of the Cambridge Philosophical Society",
    "proc nat acad sci": "Proceedings of the National Academy of Sciences",
    "the american mathematical monthly": "The American Mathematical Monthly",
    "american mathematical monthly": "The American Mathematical Monthly",
    "c r soc sci lett varsovie classe iii": "Comptes rendus de la Société des Sciences et des Lettres de Varsovie, Classe III",
    "comptes rendus soc sci et let de varsovie classe iii": "Comptes rendus de la Société des Sciences et des Lettres de Varsovie, Classe III",
    "jahresb d m v": "Jahresbericht der Deutschen Mathematiker-Vereinigung",
    "jahresb deutschen mathematiker vereinigung": "Jahresbericht der Deutschen Mathematiker-Vereinigung",
    "jahresbericht deutschen mathematiker vereinigung": "Jahresbericht der Deutschen Mathematiker-Vereinigung",
    "jahresbericht der deutschen mathematiker vereinigung": "Jahresbericht der Deutschen Mathematiker-Vereinigung",
    "proc nat acad sci": "Proceedings of the National Academy of Sciences",
    "proceedings national academy sciences": "Proceedings of the National Academy of Sciences",
}


def strip_accents(text):
    return "".join(
        char for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )


def base_normalize(text):
    text = str(text).strip()
    text = text.replace("&", " and ")
    text = text.replace("D. M.-V", "Deutschen Mathematiker Vereinigung")
    text = text.replace("D. M.-V.", "Deutschen Mathematiker Vereinigung")
    text = text.replace("Amer.", "Amer")
    text = text.replace("Math.", "Math")
    text = text.replace("Jour.", "Jour")
    text = text.replace("J.", "J")
    text = text.replace("Bull.", "Bull")
    text = text.replace("Proc.", "Proc")
    text = text.replace("Trans.", "Trans")
    text = text.replace("Rev.", "Rev")
    text = text.replace("Vol.", "Vol")
    text = re.sub(r"^[\"'“”]+|[\"'“”,.]+$", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = strip_accents(text).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\b(the|le|la|les|of|de|des|du|der|die|das|and|und|et)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def expand_abbreviations(normalized):
    tokens = []
    for token in normalized.split():
        tokens.extend(ABBREVIATIONS.get(token, token).split())
    return re.sub(r"\s+", " ", " ".join(tokens)).strip()


def journal_key(raw):
    normalized = base_normalize(raw)
    manual = MANUAL_CANONICAL.get(normalized)
    if manual:
        return base_normalize(manual)
    expanded = expand_abbreviations(normalized)
    manual = MANUAL_CANONICAL.get(expanded)
    if manual:
        return base_normalize(manual)
    return expanded


def display_name(raw_values):
    counts = Counter(raw_values)
    for raw, _ in counts.most_common():
        key = base_normalize(raw)
        expanded = expand_abbreviations(key)
        if key in MANUAL_CANONICAL:
            return MANUAL_CANONICAL[key]
        if expanded in MANUAL_CANONICAL:
            return MANUAL_CANONICAL[expanded]

    # Prefer fuller, less abbreviated names when there is no manual canonical.
    def score(raw):
        lowered = raw.lower()
        abbreviation_penalty = len(re.findall(r"\b[a-z]\.|\.", lowered))
        article_bonus = 2 if lowered.startswith("the ") else 0
        return (len(raw.split()) * 3 + len(raw) / 20 + article_bonus - abbreviation_penalty)

    return max(counts, key=score)


def slugify(name):
    text = strip_accents(name).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "journal"


def build_journals(works):
    grouped = defaultdict(lambda: {
        "raw_values": [],
    })

    for work in works:
        journal = work.get("journal")
        if not journal:
            continue
        key = journal_key(journal)
        grouped[key]["raw_values"].append(journal)

    journals = []
    for key, data in grouped.items():
        total_count = len(data["raw_values"])
        if total_count < MIN_TOTAL_COUNT:
            continue

        canonical = display_name(data["raw_values"])
        raw_counts = Counter(data["raw_values"])
        aliases = []
        canonical_key = base_normalize(canonical)
        for value, _ in raw_counts.most_common():
            if base_normalize(value) == canonical_key:
                continue
            aliases.append(value)
        journals.append({
            "journal": canonical,
            "aliases": aliases,
            "total_count": total_count,
        })

    return sorted(journals, key=lambda item: (-item["total_count"], item["journal"].lower()))


def main():
    works = json.loads(WORKS_PATH.read_text(encoding="utf-8"))
    journals = build_journals(works)
    OUTPUT_PATH.write_text(
        json.dumps(journals, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    raw_count = sum(1 for work in works if work.get("journal"))
    unique_raw = len({work.get("journal") for work in works if work.get("journal")})
    print(
        f"Wrote {len(journals)} journal records with total_count >= {MIN_TOTAL_COUNT} "
        f"from {raw_count} journal fields ({unique_raw} unique raw strings) to {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
