#!/usr/bin/env python3
"""
Parse JSL unresolved bibliographic reference strings into structured JSON.
Uses CrossRef API for author/metadata enrichment where needed.
"""

import json, re, urllib.request, urllib.parse, urllib.error, time, sys, unicodedata

# ─────────────────────────────────────────────
# 1. OCR CLEANING
# ─────────────────────────────────────────────
def fix_hyphenation(text):
    """Fix mid-word line-break hyphens: 'Mathe- matical' → 'Mathematical'."""
    return re.sub(r'(\w)-\s+(\w)', r'\1\2', text)

def clean_ocr(text):
    text = fix_hyphenation(text)
    token_fixes = [
        ('M1nd',            'Mind'),
        ('\x00v01\x00',     'vol'),   # placeholder; handled by regex below
        ('VO1',             'Vol'),
        ('Vo1',             'Vol'),
        ('vo1',             'vol'),
        ('lnuber',          'number'),
        ('!pp',             'pp'),
        ('lmplic',          'Implic'),
        ('Luhasiewicz',     'Lukasiewicz'),
        ('Gbttingen',       'Göttingen'),
        ('Gottingen',       'Göttingen'),
        ("'GOttingen",      "Göttingen"),
        ('G6ttingen',       'Göttingen'),
        ('G8ttingen',       'Göttingen'),
        ('Sdo Paulo',       'São Paulo'),
        ('HAs REICHENBACH', 'HANS REICHENBACH'),
        ('NICHOLAs RESCHER','NICHOLAS RESCHER'),
        ('GEORO HENRIK',    'GEORG HENRIK'),
        ('KlassenkalkiW',   'Klassenkalkül'),
        ('Klassenkalkiil',  'Klassenkalkül'),
        ('Kalkiils',        'Kalküls'),
        ('KalktW',          'Kalkül'),
        ('ewfoundation8',   'New foundations'),
        ('—ewfoundation8',  'New foundations'),
        ('—er Wahrheits',   'Der Wahrheits'),
        ('—n Cantor',       'On Cantor'),
        ('—On Cantor',      'On Cantor'),
        ('ZUr',             'Zur'),
        ('WV.',             'W.'),    # "WV. V. QUINE" OCR artifact
        ('based orn',       'based on'),
        ('orn strict',      'on strict'),
        ('full!',           'full'),
        ('Fragmtents',      'Fragments'),
        ('axiontatizability','axiomatizability'),
        ('Diodorean',       'Diodorean'),
        ('lnuber-theoretic', 'number-theoretic'),
        ('extendedpredicate','extended predicate'),
        ('PaulBernays',     'Paul Bernays'),
    ]
    for old, new in token_fixes:
        text = text.replace(old, new)

    # Regex-based fixes
    text = re.sub(r'\bv[o0]l\b', 'vol', text)
    text = re.sub(r'\bV[o0]l\b', 'Vol', text)
    text = re.sub(r'\bt[YyOo]ber\b', 'Über', text)
    text = re.sub(r'\bL[Oo]ber\b', 'Über', text)
    text = re.sub(r'\b[Uu]eber\b', 'Über', text)
    text = re.sub(r'Vollst[äa]ndigkeit|Vollstdndigkeit|Vollst.ndigkeit', 'Vollständigkeit', text)
    text = re.sub(r'VollstAndigkeit', 'Vollständigkeit', text)
    text = re.sub(r'Vollstandigkeit', 'Vollständigkeit', text)
    text = re.sub(r'\bJe[Bb]er\b', 'Über', text)
    text = re.sub(r"Mc'Kinsey", 'McKinsey', text)
    # Fix spurious trailing quote/apostrophe from OCR at end of page citations
    text = re.sub(r"'\s*$", '', text)
    # Fix ".10" footnote markers appended to some strings
    text = re.sub(r'\.(\d+)$', '.', text)
    # Fix "s~r." -> "sér."
    text = re.sub(r's~r\.', 'sér.', text)
    # Fix "0." -> "O." in names (e.g. "C. 0. Sylvester" -> "C. O. Sylvester")
    text = re.sub(r'\bC\.\s+0\.', 'C. O.', text)
    # Fix isolated pp→pages markers that got OCR'd with typos
    text = re.sub(r'\bPP\.\s', 'pp. ', text)
    text = re.sub(r'\bP\.\s+(\d)', r'p. \1', text)
    return text.strip()


# ─────────────────────────────────────────────
# 2. IGNORABLE DETECTION
# ─────────────────────────────────────────────
IGNORABLE_STARTS = [
    r'^\[\d+\]?$',                              # "[9]", "[91]"
    r'^\[\d',                                   # "[I] pp. 91 ff"
    r'^\d+\]\s*p',                              # "10] p. 359"
    r'^[Vv]ol\.?\s*\d+\s*[\(,]',               # "vol. 31 (1928), ..."
    r'^[Vv]ol\.\s+[IVX]+,',                    # "Vol. II, pp. ..."
    r'^Bd\.\s+\d+',                             # "Bd. 73 (1913), S. 245-272"
    r'^pp?\.\s+\d',                             # "pp. 297-298"
    r'^[Ss]\.\s+\d',                            # "S. 169-207" (German Seite)
    r'^p\.\s+\d',                               # "p. 88..."
    r'^[Tt]his\s+(?:JOURNAL|journal|Journal),\s+[Vv]ol', # "This JOURNAL, vol. X"
    r'^[Tt]his\s+(?:JOURNAL|journal|Journal),\s+[IVX]+\s+\d', # "this JOURNAL, VII 1"
    r'^[Tt]his\s+(?:JOURNAL|journal|Journal),\s+[IVX]+$',
    r'^[Mm]ath(?:ematical)?\s+[Rr]eviews?,?\s+vol',   # "Mathematical reviews, vol. 33..."
    r'^[Zz]entralblatt',                        # "Zentralblatt, vol. 117..."
    r'^errata,',                                # "errata, vol. 23, p. vi."
    r'^[Ss]econd\s+edition',
    r'^[Rr]evised\s+edition',
    r'^[Ss]iehe\b',                             # German "Siehe bes. die Arbeiten..."
    r'^paper\s+were\s+read',
    r'^(?:[A-Z][A-ZÄÖÜ\s\.]+)?[Ss]ee\s+[A-Z]\w+\s+and\b', # "JOHN ROBISON See Rescher..."
    r'^[Cc]ompare\s+[A-Z]',
    r'^Stelle\s*\(',                            # Ancient citation
    r'^Xenokrates',
    r'^Vom\s+letzten',
    r'^Granice\s+nauki',
    r'^the\s+footnote\s+to',
    r'^[Rr]ule\s+K',
    r'^Church\s+expounds',
    r'^Church\s+\([Ii]',                        # "Church (I 73, p. 351..."
    r'^(?:Church|Quine|Rosser)\'s?\s+(?:definition|monograph|system|recent)\b',
    r'^II\s+\d+\s+and\s+Church',               # "II 39 and Church's recent..."
    r'^Quine\'s\s+definition',
    r"^Quine's\s+definition",
    r'^author\'s\s+Ph',
    r"^author's\s+Ph",
    r'^M\.\s+I\.\s+T\.\s+Lincoln',
    r'^Sitzungsberichten\s+der',                # German conference proceedings fragment
    r'^Symbolic\s+logic,\s+p\.',                # "Symbolic logic, p. 493."
    r'^Mathematical\s+logic\s+p\.',             # "Mathematical logic p. 161"
    r'^p\.\s+\d+\s+of\s+',                     # "p. 88 of W. V. QUINE's..."
    r'^pp\.\s+\d+',                             # "pp. 150-151 of the Proceedings..."
    r'^(?:\d+\s+)?(?:and\s+)?[A-Z][a-z]+\'s\s+(?:earlier|recent|paper)\b', # "Lewis's earlier book..."
    r'^(?:vol\.\s*\d+\s*,\s*)?\d{4},\s*pp\.',  # "vol. 2, 1939, pp. 392-421."
    r'^Symbolic\s+logic\s*,\s*p',
    r'^Grundzüge\s+der',
    r'^Rasmus,',
    r'^Aus\s+der\s+Arbeit',                     # "Aus der Arbeit: L. Kalmär..."
    r'^\(in\s+preparation\)',
    r'^Tarski\'s\s+paper\s+mentioned',
    r'^Enderton\'s\s+work',
    r'^Polish\s+[Ll]ogic,\s+(?:ed\.|published)',
    r'^Constructivity\s+in\s+mathematics,',     # fragment without author
    r'^[A-Z]\.\s+S\.\s+Troelstra\s+has',       # informal mention
    r'^A\.\s+S\.\s+Troelstra\s+has',
]

IGNORABLE_PATTERNS_FULL = [
    # "Author YEAR" only citations with no title
    r'^[A-ZÄÖÜ][a-zäöüłśń]+(?:\s+(?:and\s+)?[A-ZÄÖÜ][a-zäöüłśń]+)?\s+\d{4}(?:,\s*(?:pp?\.|vol\.|p\s+\d).*)?\.?$',
    # "SURNAME YEAR" all caps
    r'^[A-ZÄÖÜ]{3,}\s+\d{4}(?:,?\s*pp?\.?\s+\d+.*)?\.?$',
    # Single journal volume only: "vol. 6 (1941), pp. 1-17."
    r'^vol\.\s+\d+\s*\(\d{4}\)',
    # "GEORD HENRIK VON WRIGHT" as only content (no title, no comma-separated title)
    # Handled by length check below
]

def is_ignorable(text):
    """Returns (True, reason) or (False, None)."""
    t = text.strip()

    # Too short / empty
    if len(t) < 10:
        return True, "TooShort"

    # Author+year only (like "Kneale 1946", "Anderson and Belnap 1958")
    if re.match(r'^[A-ZÄÖÜ][a-zäöü]+(?:\s+(?:and\s+)?[A-ZÄÖÜ][a-zäöüłś]+)*\s+\d{4}(?:,\s*[pP]+\.\s*\d+.*)?\.?$', t):
        return True, "AuthorYearOnly"
    # "SURNAME YEAR" format
    if re.match(r'^[A-ZÄÖÜ]{3,}(?:\s+[A-ZÄÖÜ]{3,})*\s+\d{4}(?:,?\s*pp?\.\s*\d+.*)?$', t) and ',' not in t.split(str(re.search(r'\d{4}', t).group()), 1)[0]:
        return True, "AuthorYearOnly"
    # "Duncan-Jones (1934, p. 71)" style
    if re.match(r'^[A-ZÄÖÜ][a-z]+(?:-[A-Z][a-z]+)?\s*\(\d{4},?\s*(?:vol\.|p\.|pp\.).*\)\.?$', t):
        return True, "AuthorYearOnly"
    # "Blanshard (1939, vol. 2, p. 390)"
    if re.match(r'^[A-Z][a-z]+\s+\(\d{4},\s*(?:vol|p|pp)', t):
        return True, "AuthorYearOnly"

    # Check prefix ignorable patterns
    for pat in IGNORABLE_STARTS:
        if re.match(pat, t, re.IGNORECASE):
            # Determine reason
            if 'JOURNAL' in pat or 'journal' in pat.lower():
                return True, "JournalFragment"
            elif 'review' in pat.lower() or 'entralblatt' in pat:
                return True, "ReviewCitation"
            elif 'edition' in pat.lower():
                return True, "EditionFragment"
            elif any(x in pat for x in ['Bd\\.', 'vol\\.', 'pp?\\.']):
                return True, "Fragment"
            else:
                return True, "Informal"

    # Full-string ignorable patterns
    for pat in IGNORABLE_PATTERNS_FULL:
        if re.match(pat, t):
            return True, "Fragment"

    # Publisher/location only fragments
    city_starts = ('Cambridge, Mass.:', 'New York:', 'Oxford:', 'Amsterdam:',
                   'Princeton:', 'Paris:', 'Berlin:', 'London:', 'Warsaw:',
                   'Leipzig:', 'Zürich:', 'Chicago:', 'Toronto:', 'Stanford:',
                   'Groningen:', 'Baltimore:', 'Vienna:', 'Stockholm:', 'Helsinki:',
                   'Pittsburgh:', 'Providence:')
    if any(t.startswith(c) for c in city_starts):
        return True, "PublisherFragment"
    # "Cambridge, Mass.: Harvard University Press, 1963."
    if re.match(r'^[A-Z][a-z]+,\s+(?:Mass|N\.J|Calif|Eng|Ill|Minn)\.:?\s+', t):
        return True, "PublisherFragment"

    # "ibid." only entries
    if re.match(r'^[Ii]bid\.?\s*(?:,\s*(?:pp?\.|vol\.|ser\.).*)?\.?$', t) and len(t) < 60:
        if not re.search(r'[A-Z][a-z]{3,}', t):
            return True, "IbidFragment"

    # "vol. X (YEAR) p. Y" journal fragment with no title
    if re.match(r'^vol\.\s+\d+\s*\(\d{4}\),?\s*pp?\.?\s*\d', t):
        return True, "JournalFragment"
    if re.match(r'^vol\.\s+\d+\s*\(\d{4}\)\s*$', t):
        return True, "JournalFragment"

    # "vol. 17 (1952) p. 210" fragments
    if re.match(r'^vol\.\s+\d+\s*\(\d{4}\)\s+pp?\.', t):
        return True, "JournalFragment"

    # Ancient classical refs with no structured metadata
    if re.match(r'^Sextus,\s+Pyr', t):
        return True, "AncientRef"
    if re.match(r'^C\.\s+Prantl,\s+Geschichte', t):
        # Actually this one has author+title, let's include it
        return False, None

    return False, None


# ─────────────────────────────────────────────
# 3. FIELD EXTRACTORS
# ─────────────────────────────────────────────

KNOWN_JOURNALS = {
    r'\bthis\s+(?:JOURNAL|journal|Journal)\b':  'The Journal of Symbolic Logic',
    r'\bJournal of Symbolic Logic\b':           'The Journal of Symbolic Logic',
    r'\bMind\b':                                'Mind',
    r'\bFundamenta\s+[Mm]athematicae\b':        'Fundamenta Mathematicae',
    r'\bMathematische\s+Annalen\b':             'Mathematische Annalen',
    r'\bAmerican\s+[Jj]ournal\s+of\s+[Mm]athematics\b': 'American Journal of Mathematics',
    r'\bTransactions\s+of\s+the\s+American\s+Mathematical\s+Society\b': 'Transactions of the American Mathematical Society',
    r'\bBulletin\s+of\s+the\s+American\s+Mathematical\s+Society\b': 'Bulletin of the American Mathematical Society',
    r'\bProceedings\s+of\s+the\s+American\s+Mathematical\s+Society\b': 'Proceedings of the American Mathematical Society',
    r'\bMonatshefte\s+f[üu]r\s+Mathematik\s+und\s+Physik\b': 'Monatshefte für Mathematik und Physik',
    r'\bCompositio\s+[Mm]athematica\b':         'Compositio Mathematica',
    r'\bAnnals\s+of\s+[Mm]athematics\b':        'Annals of Mathematics',
    r'\bMathematica\s+Scandinavica\b':          'Mathematica Scandinavica',
    r'\bMathematische\s+Zeitschrift\b':         'Mathematische Zeitschrift',
    r'\bStudia\s+[Ll]ogica\b':                  'Studia Logica',
    r'\bStudia\s+[Pp]hilosophica\b':            'Studia Philosophica',
    r'\bZeitschrift\s+f[üu]r\s+[Mm]athematische\s+[Ll]ogik\b': 'Zeitschrift für Mathematische Logik und Grundlagen der Mathematik',
    r'\bNotre\s+Dame\s+[Jj]ournal\s+of\s+[Ff]ormal\s+[Ll]ogic\b': 'Notre Dame Journal of Formal Logic',
    r'\b[Tt]he\s+[Pp]hilosophical\s+[Rr]eview\b': 'The Philosophical Review',
    r'\b[Pp]hilosophical\s+[Rr]eview\b':       'The Philosophical Review',
    r'\b[Tt]he\s+[Mm]onist\b':                 'The Monist',
    r'\bActa\s+[Ss]cientiarum\s+[Mm]athematicarum\b': 'Acta Scientiarum Mathematicarum',
    r'\bActa\s+(?:litterarum\s+ac\s+)?[Ss]cientiarum\s+(?:[Rr]egiae\s+)?[Mm]ath': 'Acta Scientiarum Mathematicarum',
    r'\bPacific\s+[Jj]ournal\s+of\s+[Mm]athematics\b': 'Pacific Journal of Mathematics',
    r'\bIndagationes\s+[Mm]athematicae\b':      'Indagationes Mathematicae',
    r'\b[Tt]he\s+[Jj]ournal\s+of\s+[Pp]hilosophy\b': 'Journal of Philosophy',
    r'\b[Jj]ournal\s+of\s+[Pp]hilosophy\b':    'Journal of Philosophy',
    r'\bAmerican\s+[Mm]athematical\s+[Mm]onthly\b': 'American Mathematical Monthly',
    r'\b[Tt]he\s+[Aa]merican\s+[Mm]athematical\s+[Mm]onthly\b': 'American Mathematical Monthly',
    r'\bArchiv\s+f[üu]r\s+mathematische\s+Logik\b': 'Archiv für Mathematische Logik und Grundlagenforschung',
    r'\bArchiv\s+f[üu]r\s+[Mm]ath(?:ematische)?\s+[Ll]ogik\b': 'Archiv für Mathematische Logik und Grundlagenforschung',
    r'\bIsrael\s+[Jj]ournal\s+of\s+[Mm]athematics\b': 'Israel Journal of Mathematics',
    r'\bDuke\s+[Mm]athematical\s+[Jj]ournal\b': 'Duke Mathematical Journal',
    r'\bTheoria\b':                             'Theoria',
    r'\bLogique\s+et\s+[Aa]nalyse\b':           'Logique et Analyse',
    r'\bCanadian\s+[Jj]ournal\s+of\s+[Mm]athematics\b': 'Canadian Journal of Mathematics',
    r'\bIllinois\s+[Jj]ournal\s+of\s+[Mm]athematics\b': 'Illinois Journal of Mathematics',
    r'\bMichigan\s+[Mm]athematical\s+[Jj]ournal\b': 'Michigan Mathematical Journal',
    r'\bProceedings\s+of\s+the\s+London\s+Mathematical\s+Society\b': 'Proceedings of the London Mathematical Society',
    r'\bAmerican\s+[Pp]hilosophical\s+[Qq]uarterly\b': 'American Philosophical Quarterly',
    r'\bProceedings\s+of\s+the\s+National\s+Academy\s+of\s+Sciences\b': 'Proceedings of the National Academy of Sciences',
    r'\bJournal\s+of\s+[Hh]ellenic\s+[Ss]tudies\b': 'Journal of Hellenic Studies',
    r'\bBritish\s+[Jj]ournal\s+for\s+(?:the\s+)?[Pp]hilosophy\s+of\s+[Ss]cience\b': 'British Journal for the Philosophy of Science',
    r'\bIBM\s+[Jj]ournal\s+of\s+[Rr]esearch\s+and\s+[Dd]evelopment\b': 'IBM Journal of Research and Development',
    r'\bVierteljahrsschrift\s+der\s+[Nn]aturforschenden\b': 'Vierteljahrsschrift der Naturforschenden Gesellschaft in Zürich',
    r'\bJapanese?\s+[Jj]ournal\s+of\s+[Mm]athematics\b': 'Japanese Journal of Mathematics',
    r'\bAnnals\s+of\s+[Mm]athematical\s+[Ll]ogic\b': 'Annals of Mathematical Logic',
    r'\b[Jj]ournal\s+of\s+[Cc]omputing\s+[Ss]ystems\b': 'Journal of Computing Systems',
    r'\bColloquium\s+Mathematicum\b':           'Colloquium Mathematicum',
    r'\bFranciscan\s+[Ss]tudies\b':             'Franciscan Studies',
    r'\bActa\s+[Pp]hilosophica\s+[Ff]ennica\b': 'Acta Philosophica Fennica',
    r'\bZentralblatt\s+f[üu]r\s+[Mm]athematik\b': 'Zentralblatt für Mathematik',
    r'\bPrzegląd\s+[Ff]ilozoficzny\b':          'Przegląd Filozoficzny',
    r'\bWiadomości\s+matematyczne\b':           'Wiadomości Matematyczne',
    r'\bComptes\s+[Rr]endus\s+des\s+séances\b': 'Comptes rendus des séances de la Société des Sciences et des Lettres de Varsovie',
    r'\bComptes\s+[Rr]endus\s+(?:de\s+la\s+)?[Ss]ociété\b': 'Comptes rendus des séances de la Société des Sciences et des Lettres de Varsovie',
    r'\bComptes\s+[Rr]endus\s+hebdomadaires\b': 'Comptes rendus hebdomadaires des séances de l\'académie des sciences',
    r'\bDialectica\b':                          'Dialectica',
    r'\bErgebnisse\s+eines\s+mathematischen\s+Kolloquiums\b': 'Ergebnisse eines mathematischen Kolloquiums',
    r'\bMededelingen\s+der\s+Koninklijke\b':    'Mededelingen der Koninklijke Nederlandse Akademie van Wetenschappen',
    r'\bKoninklijke\s+Neder[la]+ndsche\s+Akademie\b': 'Koninklijke Nederlandsche Akademie van Wetenschappen, Proceedings',
    r'\bAnnales\s+Universitatis\s+Mariae\s+Curie\b': 'Annales Universitatis Mariae Curie-Sklodowska',
    r'\b[Ss]ocietas\s+[Ss]cientiarum\s+[Ff]ennica\b': 'Commentationes Physico-Mathematicae (Societas Scientiarum Fennica)',
    r'\b[Rr]atio\b':                            'Ratio',
    r'\bProceedings\s+of\s+the\s+(?:Cambridge|Aristotelian)\b': 'Proceedings of the Cambridge Philosophical Society',
    r'\bProceedings\s+of\s+the\s+Aristotelian\s+[Ss]ociety\b': 'Proceedings of the Aristotelian Society',
    r'\bAjatus\b':                              'Ajatus',
    r'\bDominican\s+[Ss]tudies\b':              'Dominican Studies',
    r'\bRevue\s+néoscolastique\b':              'Revue Néoscolastique de Philosophie',
    r'\b[Jj]ournal\s+f[üu]r\s+die\s+reine\b':  'Journal für die reine und angewandte Mathematik',
    r'\b[Pp]hilosophy\s+and\s+[Pp]henomenological\s+[Rr]esearch\b': 'Philosophy and Phenomenological Research',
    r'\b[Ll]ogique\s+et\s+[Aa]nalyse\b':        'Logique et Analyse',
    r'\b[Ss]tudia\s+[Pp]hilosophica\s*\([Pp]oznań\)': 'Studia Philosophica (Poznań)',
    r'\bAmerican\s+[Ss]ociety\s+[Tt]ranslations\b': 'American Mathematical Society Translations',
    r'\bForschungen\s+zur\s+Logik\b':           'Forschungen zur Logik und zur Grundlegung der exakten Wissenschaften',
}

def extract_journal(text):
    for pattern, name in KNOWN_JOURNALS.items():
        if re.search(pattern, text, re.IGNORECASE):
            return name
    return None

def extract_year(text):
    # Prefer year in parentheses
    m = re.search(r'\((\d{4})(?:/\d{2,4})?\)', text)
    if m:
        return int(m.group(1))
    # Bare year at end of string
    m = re.search(r',?\s*(\d{4})[\.,]?\s*$', text)
    if m:
        return int(m.group(1))
    # Bare year preceded by space mid-string (books)
    m = re.search(r'\b(1[89]\d{2})\b', text)
    if m:
        return int(m.group(1))
    return None

def extract_volume(text):
    m = re.search(r'[Vv]ol(?:ume)?\.?\s*(\d+|[IVXLC]+)\b', text)
    if m:
        return m.group(1)
    # German "Bd."
    m = re.search(r'\bBd\.\s+(\d+)', text)
    if m:
        return m.group(1)
    return None

def extract_number(text):
    m = re.search(r'\b(?:no|nr|number|Heft)\.?\s*(\d+)\b', text, re.IGNORECASE)
    if m:
        return m.group(1)
    # "vol. 10, no. 1" or "vol. X (YEAR), no. Y"
    m = re.search(r'[Vv]ol\..*?,\s*[Nn]o\.?\s*(\d+)', text)
    if m:
        return m.group(1)
    return None

def extract_pages(text):
    # "pp. 123-456" or "S. 169-207"
    m = re.search(r'pp?\.?\s*([\d]+\s*[–—\-]+\s*[\d]+)', text)
    if m:
        # normalize dash
        return re.sub(r'\s*[–—]+\s*', '-', m.group(1))
    # single page "p. 54" or "p. 54f"
    m = re.search(r'\bp\.?\s*(\d+)f?\b', text)
    if m and 'pp.' not in text:
        return m.group(1)
    # German "S. 169-207"
    m = re.search(r'\bS\.\s*([\d]+\s*[-–—]+\s*[\d]+)', text)
    if m:
        return re.sub(r'\s*[–—]+\s*', '-', m.group(1))
    return None

# Book publisher/location patterns
PUBLISHER_HINTS = [
    'University Press', 'North-Holland', 'North Holland', 'McGraw-Hill',
    'Prentice-Hall', 'Van Nostrand', 'Interscience', 'Chelsea', 'Benjamin',
    'Macmillan', 'Academic Press', 'Dover', 'Springer', 'Wiley',
    'Allen & Unwin', 'Allen and Unwin', 'Clarendon', 'Routledge',
    'Gauthier-Villars', 'Harcourt', 'Simon & Schuster', 'Norton',
    'Nauwelaerts', 'Hermann', 'Hirzel', 'Raven Press', 'Humanities Press',
    'Doubleday', 'Williams & Wilkins', 'Open Court', 'Crowell',
    'G. Allen', 'Pergamon', 'Polska Akademia', 'Akademie',
    'Addison-Wesley', 'Birkhäuser',
]

def is_book(text, journal):
    if journal:
        return False
    for hint in PUBLISHER_HINTS:
        if hint.lower() in text.lower():
            return True
    # Has city + bare year pattern
    city_pat = r'\b(?:New York|London|Amsterdam|Oxford|Cambridge|Paris|Berlin|Warsaw|Chicago|Princeton|Toronto|Vienna|Zürich|Leipzig|Groningen|Meisenheim|Manchester|Pittsburgh|Baltimore|Stanford|Helsinki|Stockholm|Dordrecht)\b'
    if re.search(city_pat, text, re.IGNORECASE):
        # Check if there's a bare year (not inside parens, which would suggest journal)
        return True
    return False

def extract_location(text):
    cities = ['New York', 'London', 'Amsterdam', 'Oxford', 'Cambridge',
              'Paris', 'Berlin', 'Warsaw', 'Chicago', 'Princeton', 'Toronto',
              'Vienna', 'Zürich', 'Leipzig', 'Groningen', 'Meisenheim',
              'Manchester', 'Pittsburgh', 'Baltimore', 'Stanford', 'Helsinki',
              'Stockholm', 'Dordrecht', 'Szeged', 'Lublin', 'Wroclaw']
    for city in cities:
        if re.search(r'\b' + re.escape(city) + r'\b', text, re.IGNORECASE):
            return city
    return None

# ─────────────────────────────────────────────
# 4. AUTHOR EXTRACTION
# ─────────────────────────────────────────────

# Patterns for an "all-caps + initials" author unit:
# e.g. "J. C. E. DEKKER", "S. C. KLEENE", "A. TARSKI", "HASKELL B. CURRY"
_INIT_SEG   = r'[A-ZÄÖÜŁŚŃ]\.(?:\s*[A-ZÄÖÜŁŚŃ]\.)*'   # "J. C. E."
_CAPS_NAME  = r'[A-ZÄÖÜŁŚŃ][A-ZÄÖÜŁŚŃ\-]{1,}'         # "KLEENE"
_FULL_CAPS  = r'[A-ZÄÖÜŁŚŃ][A-ZÄÖÜ\-]+'               # for all-caps first name too

# One author unit (initials + caps surname, OR full caps name)
_ONE_AUTHOR_AC  = rf'(?:{_INIT_SEG}\s+)?{_CAPS_NAME}(?:\s+{_CAPS_NAME})*'

# Separator between authors: comma or "and"/"AND"
_SEP = r'(?:\s*,\s*|\s+(?:and|AND|und)\s+)'

# Multi-author block (caps style)
MULTI_CAPS_AUTH_PAT = re.compile(
    rf'^({_ONE_AUTHOR_AC}(?:{_SEP}{_ONE_AUTHOR_AC})*)'
    rf'(?:,\s+|\.\s+)',   # followed by comma or period (before the title)
    re.UNICODE
)

# Title-case author: "Rudolf Carnap" / "Albert Einstein and Leopold Infeld"
_TC_UNIT = r'[A-ZÄÖÜ][a-zäöüłśń]+(?:\s+[A-ZÄÖÜ]\.)?(?:\s+(?:von|van|de|du|le|la|den|der|van\s+de[rn]?)\s+)?[A-ZÄÖÜ][a-zäöüłśń]+'
MULTI_TC_AUTH_PAT = re.compile(
    rf'^({_TC_UNIT}(?:\s+and\s+{_TC_UNIT})*)'
    rf'[.\s]+',
    re.UNICODE
)

# "SURNAME, FIRSTNAME" inverted (with optional citation marker [1])
INVERTED_AUTH_PAT = re.compile(
    r'^([A-ZÄÖÜŁŚŃ][A-ZÄÖÜŁŚŃ\-]+,\s+[A-ZÄÖÜ][A-ZÄÖÜ\s\.]+?)'
    r'(?:\[\d+\])?\s*,\s+',
    re.UNICODE
)

# "Surname, I." inverted title-case
INVERTED_TC_PAT = re.compile(
    r'^([A-ZÄÖÜ][a-zäöüłś]+,\s+[A-Z]\.)(?:\s+,|\.\s+)',
    re.UNICODE
)

def normalise_author_string(raw):
    """Convert 'SURNAME FIRSTNAME' / 'F. SURNAME' etc to 'Firstname Surname' style."""
    raw = raw.strip().rstrip(',.')
    # Handle inverted "SURNAME, FIRSTNAME"
    inv = re.match(r'^([A-ZÄÖÜ][A-ZÄÖÜ\-]+),\s+([A-ZÄÖÜ][\w\s\.]+)$', raw)
    if inv:
        last, first = inv.group(1), inv.group(2).strip()
        # Titlecase the last name only if it's all-caps
        if last == last.upper():
            last = last.capitalize()
        return f'{first} {last}'.strip()
    return raw

def split_author_block(raw):
    """Split an author block string like 'A. TARSKI and R. M. ROBINSON' into list."""
    parts = re.split(r'\s*,\s*(?=[A-ZÄÖÜ]|and\s)|\s+and\s+|\s+AND\s+|\s+und\s+', raw)
    out = []
    for p in parts:
        p = p.strip().strip(',')
        if p:
            out.append(normalise_author_string(p))
    return out

def extract_authors(text):
    """
    Try to extract author(s) from the beginning of the text.
    Returns (list_of_author_strings, rest_of_text_after_author_block).
    """
    # Strip leading citation markers like "[1] " or "1. "
    text = re.sub(r'^\[\d+\]\s*', '', text)
    text = re.sub(r'^\d+\.\s+(?=[A-ZÄÖÜ])', '', text)
    # Strip leading dash for continuation entries
    text = re.sub(r'^—\s*', '', text)

    # Try inverted format first: "CHURCH, ALONZO" or "Tarski, A."
    m = INVERTED_AUTH_PAT.match(text)
    if m:
        raw = m.group(1)
        rest = text[m.end():]
        return [normalise_author_string(raw)], rest

    m = INVERTED_TC_PAT.match(text)
    if m:
        raw = m.group(1)
        rest = text[m.end():]
        return [normalise_author_string(raw)], rest

    # Try caps+initials multi-author pattern
    m = MULTI_CAPS_AUTH_PAT.match(text)
    if m:
        raw_block = m.group(1)
        rest = text[m.end():]
        # Validate: rest should look like a title (starts with capital + lowercase)
        if rest and (rest[0].isupper() or rest[0].islower()):
            return split_author_block(raw_block), rest

    # Try title-case pattern
    m = MULTI_TC_AUTH_PAT.match(text)
    if m:
        raw_block = m.group(1)
        rest = text[m.end():]
        # Heuristic: rest should not start with another name
        if rest and not re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+', rest):
            authors = [a.strip() for a in re.split(r'\s+and\s+', raw_block)]
            return authors, rest

    return [], text


# ─────────────────────────────────────────────
# 5. TITLE EXTRACTION
# ─────────────────────────────────────────────

# Signals that we've left the title and entered venue/metadata
VENUE_SIGNALS = [
    # Journal names (abbreviated)
    r'\bthis\s+(?:JOURNAL|journal|Journal)\b',
    r'\bFundamenta\s+[Mm]ath', r'\bMathematische\s+Annalen\b',
    r'\bAmerican\s+[Jj]ournal\s+of\s+[Mm]ath',
    r'\bTransactions\s+of\s+the\s+American',
    r'\bBulletin\s+of\s+the\s+American',
    r'\bProceedings\s+of\s+the\s+American',
    r'\bMonatshefte\s+f[üu]r\s+Math',
    r'\bCompositio\s+[Mm]ath', r'\bAnnals\s+of\s+[Mm]ath',
    r'\bMathematica\s+Scand', r'\bMathematische\s+Zeitschrift\b',
    r'\bStudia\s+[Ll]ogica\b', r'\bZeitschrift\s+f[üu]r\s+[Mm]ath',
    r'\bNotre\s+Dame\s+[Jj]ournal', r'\b[Pp]hilosophical\s+[Rr]eview\b',
    r'\b[Tt]he\s+[Mm]onist\b', r'\bActa\s+[Ss]cient',
    r'\bPacific\s+[Jj]ournal', r'\bIndagationes\s+[Mm]ath',
    r'\b[Jj]ournal\s+of\s+[Pp]hilosophy\b', r'\bAmerican\s+[Mm]ath.*[Mm]onthly\b',
    r'\bArchiv\s+f[üu]r\s+math', r'\bIsrael\s+[Jj]ournal',
    r'\bDuke\s+[Mm]ath.*[Jj]ournal\b', r'\bTheoria\b',
    r'\bLogique\s+et\s+analyse\b', r'\bCanadian\s+[Jj]ournal\s+of\s+[Mm]ath',
    r'\bIllinois\s+[Jj]ournal', r'\bMichigan\s+[Mm]ath',
    r'\bProceedings\s+of\s+the\s+London', r'\b[Aa]merican\s+[Pp]hilosoph.*[Qq]uarterly\b',
    r'\bProceedings\s+of\s+the\s+National\s+Academy',
    r'\bIBM\s+[Jj]ournal', r'\bVierteljahrsschrift\b',
    r'\bJapanese?\s+[Jj]ournal', r'\bAnnals\s+of\s+[Mm]ath.*[Ll]ogic\b',
    r'\bColloquium\s+Math', r'\bDialectica\b',
    r'\bErgebnisse\s+eines', r'\bMededelingen\b',
    r'\bKoninklijke\s+Neder', r'\bAnnales\s+Universitatis',
    r'\bForschungen\s+zur\s+Logik\b',
    r'\bPrzegląd\s+[Ff]il', r'\bWiadomości\b',
    r'\bComptes\s+[Rr]endus\b',
    # Publisher signals
    r'\bNorth[\s-]Holland\b', r'\bMcGraw[\s-]Hill\b', r'\bPrentice[\s-]Hall\b',
    r'\bVan\s+Nostrand\b', r'\bInterscience\b', r'\bChelsea\b', r'\bBenjamin\b',
    r'\bMacmillan\b', r'\bDover\b', r'\bSpringer\b', r'\bWiley\b',
    r'\bClarendon\b', r'\bRoutledge\b', r'\bGauthier[\s-]Villars\b',
    r'\bHarcourt\b', r'\bSimon\s*&\s*Schuster\b', r'\bNorton\b',
    r'\bHermann\b', r'\bHirzel\b', r'\bRaven\s+Press\b',
    r'\bHumanities\s+Press\b', r'\bDoubleday\b', r'\bOpen\s+Court\b',
    r'\bPergamon\b', r'\bPolska\s+Akademia\b', r'\bAddison[\s-]Wesley\b',
    r'\bUniversity\s+Press\b',
    # Date/volume signals
    r',\s+vol\.', r',\s+Vol\.', r',\s+no\.', r',\s+\(\d{4}\)',
    r',\s+\d{4},', r'\(\d{4}\)',
]

def extract_title(text_after_author):
    """
    Given the text AFTER the author block has been removed,
    extract the title (everything before the venue/metadata block).
    """
    t = text_after_author.strip()
    # Remove stray numbering: "1. Title" or "[1] Title" at start
    t = re.sub(r'^\[\d+\]\s*', '', t)
    t = re.sub(r'^\d+\.\s+', '', t)

    # Find where the venue starts
    earliest_pos = len(t)
    for sig in VENUE_SIGNALS:
        m = re.search(sig, t, re.IGNORECASE)
        if m and m.start() < earliest_pos:
            earliest_pos = m.start()

    title_raw = t[:earliest_pos].strip().rstrip(',;. ')

    # Also try period-split: many entries have "Title. Journal vol."
    # If title_raw contains a period, truncate there too
    dot_split = re.split(r'\.\s+(?=[A-ZÄÖÜ])', title_raw, maxsplit=1)
    if len(dot_split) > 1 and len(dot_split[0]) > 10:
        title_raw = dot_split[0]

    title_raw = title_raw.strip().rstrip(',;.')
    return title_raw if len(title_raw) > 3 else None


# ─────────────────────────────────────────────
# 6. ADDITIONAL INFO EXTRACTION
# ─────────────────────────────────────────────

def extract_additional_info(text):
    """Look for reprint, translation, abstract, dissertation, or forthcoming notes."""
    notes = []
    if re.search(r'\breprinted?\b', text, re.IGNORECASE):
        m = re.search(r'(?:reprinted?[^,;.]*(?:[,;.][^,;.]*)?)', text, re.IGNORECASE)
        if m:
            notes.append(m.group(0).strip())
    if re.search(r'\btranslated?\b', text, re.IGNORECASE):
        m = re.search(r'(?:translated?\s+by[^,;.]*)', text, re.IGNORECASE)
        if m:
            notes.append(m.group(0).strip())
    if re.search(r'\b(?:abstract|forthcoming|to\s+appear|in\s+preparation|mimeographed|doctoral\s+thesis|Ph\.?D\.?\s+thesis)\b', text, re.IGNORECASE):
        kw = re.search(r'\b(?:abstract|forthcoming|to\s+appear|in\s+preparation|mimeographed|doctoral\s+thesis|Ph\.?D\.?\s+thesis)\b', text, re.IGNORECASE)
        if kw:
            notes.append(kw.group(0))
    return '; '.join(notes) if notes else None


# ─────────────────────────────────────────────
# 7. CROSSREF API ENRICHMENT
# ─────────────────────────────────────────────

crossref_cache = {}
crossref_calls = 0
MAX_CROSSREF_CALLS = 350

def query_crossref(title, year=None, journal=None):
    global crossref_calls
    if crossref_calls >= MAX_CROSSREF_CALLS:
        return None

    cache_key = f"{title}|{year}|{journal}"
    if cache_key in crossref_cache:
        return crossref_cache[cache_key]

    query = title
    if journal:
        query += f" {journal}"

    params = {
        'query.title': title,
        'rows': '1',
        'select': 'author,title,published-print,volume,issue,page,container-title,type',
    }
    if year:
        params['filter'] = f'from-pub-date:{year-1},until-pub-date:{year+1}'
    if journal and 'symbolic logic' in journal.lower():
        params['query.container-title'] = 'Journal of Symbolic Logic'

    url = 'https://api.crossref.org/works?' + urllib.parse.urlencode(params)
    headers = {
        'User-Agent': 'JSLBibParser/1.0 (mailto:research@example.com)',
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        crossref_calls += 1
        time.sleep(0.15)  # polite crawl delay

        items = data.get('message', {}).get('items', [])
        if not items:
            crossref_cache[cache_key] = None
            return None

        item = items[0]
        score = item.get('score', 0)
        if score < 40:  # low-confidence match
            crossref_cache[cache_key] = None
            return None

        result = {}
        # Authors
        if 'author' in item:
            authors = []
            for a in item['author']:
                given = a.get('given', '')
                family = a.get('family', '')
                if given or family:
                    authors.append(f"{given} {family}".strip())
            if authors:
                result['authors'] = authors
        # Year
        dp = item.get('published-print', item.get('published-online', {}))
        parts = dp.get('date-parts', [[]])[0]
        if parts:
            result['year'] = parts[0]
        # Journal
        ct = item.get('container-title', [])
        if ct:
            result['journal'] = ct[0]
        # Volume/issue/pages
        if item.get('volume'):
            result['volume'] = item['volume']
        if item.get('issue'):
            result['number'] = item['issue']
        if item.get('page'):
            result['pages'] = item['page'].replace('--', '-')

        crossref_cache[cache_key] = result
        return result

    except Exception:
        crossref_cache[cache_key] = None
        return None

def query_open_library(title, author=None, year=None):
    """Query Open Library for book metadata."""
    params = {'title': title, 'limit': '1', 'fields': 'title,author_name,first_publish_year,publisher,publish_place'}
    if author:
        params['author'] = author
    if year:
        params['publish_year'] = str(year)
    url = 'https://openlibrary.org/search.json?' + urllib.parse.urlencode(params)
    headers = {'User-Agent': 'JSLBibParser/1.0'}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        time.sleep(0.2)
        docs = data.get('docs', [])
        if not docs:
            return None
        doc = docs[0]
        result = {}
        if doc.get('author_name'):
            result['authors'] = doc['author_name']
        if doc.get('first_publish_year'):
            result['year'] = doc['first_publish_year']
        if doc.get('publisher'):
            result['publisher'] = doc['publisher'][0] if doc['publisher'] else None
        if doc.get('publish_place'):
            result['location'] = doc['publish_place'][0] if doc['publish_place'] else None
        return result
    except Exception:
        return None


# ─────────────────────────────────────────────
# 8. MAIN PARSER
# ─────────────────────────────────────────────

def parse_one(raw_text):
    """
    Parse a single reference string.
    Returns a structured dict, or None if the string is ignorable.
    Also returns (entry_or_none, ignore_reason).
    """
    text = clean_ocr(raw_text)

    ignored, reason = is_ignorable(text)
    if ignored:
        return None, reason

    # Extract authors
    authors, rest = extract_authors(text)

    # Extract title
    title = extract_title(rest)

    # If there's no title at all, check if maybe there was no author and
    # the whole string IS a title-like thing... try again from full text
    if not title and not authors:
        title = extract_title(text)

    # If still no title, check if rest itself is meaningful
    if not title and rest.strip():
        # Sometimes the entire non-author part is the title (very short entries)
        candidate = rest.strip().rstrip(',;. ')
        if len(candidate) > 10 and not re.match(r'^vol\.|^pp\.', candidate, re.IGNORECASE):
            title = candidate

    # Must have at least a title
    if not title or len(title.strip()) < 4:
        return None, "NoTitle"

    # Detect journal
    journal = extract_journal(text)

    # Detect type
    entry_type = "book" if is_book(text, journal) else "article"
    if journal:
        entry_type = "article"

    # Extract metadata
    year    = extract_year(text)
    volume  = extract_volume(text)
    number  = extract_number(text)
    pages   = extract_pages(text)
    additional = extract_additional_info(text)

    # CrossRef enrichment: if article with no authors, query CrossRef
    cr_result = None
    if entry_type == "article" and not authors and title and year:
        cr_result = query_crossref(title, year=year, journal=journal)
        if cr_result:
            if not authors and cr_result.get('authors'):
                authors = cr_result['authors']
            if not year and cr_result.get('year'):
                year = cr_result['year']
            if not volume and cr_result.get('volume'):
                volume = cr_result['volume']
            if not number and cr_result.get('number'):
                number = cr_result['number']
            if not pages and cr_result.get('pages'):
                pages = cr_result['pages']

    # Open Library enrichment for books with missing authors
    if entry_type == "book" and not authors and title:
        ol_result = query_open_library(title, year=year)
        if ol_result:
            if ol_result.get('authors'):
                authors = ol_result['authors']
            if not year and ol_result.get('year'):
                year = ol_result['year']

    # Build entry
    entry = {
        "title": title,
        "authors": authors,
        "year": year,
        "type": entry_type,
    }

    if entry_type == "article":
        entry["journal"] = journal
        entry["volume"] = volume
        if number:
            entry["number"] = number
        entry["pages"] = pages
    else:
        loc = extract_location(text)
        if loc:
            entry["location"] = loc
        entry["pages"] = pages

    if additional:
        entry["additional_information"] = additional

    return entry, None


# ─────────────────────────────────────────────
# 9. RUN ON ALL ENTRIES
# ─────────────────────────────────────────────

with open('active_data/jsl_unresolved_reference_strings.json', 'r', encoding='utf-8') as f:
    refs = json.load(f)

parsed  = []
ignored = []
errors  = []

print(f"Processing {len(refs)} reference strings...", file=sys.stderr)

for i, raw in enumerate(refs):
    if i % 200 == 0:
        print(f"  {i}/{len(refs)} (CrossRef calls so far: {crossref_calls})", file=sys.stderr)
    try:
        result, reason = parse_one(raw)
        if result is None:
            ignored.append((raw, reason))
        else:
            parsed.append(result)
    except Exception as e:
        errors.append((raw, str(e)))
        ignored.append((raw, "ParseError"))

print(f"\nDone. Parsed: {len(parsed)}, Ignored: {len(ignored)}, Errors: {len(errors)}", file=sys.stderr)
print(f"CrossRef API calls made: {crossref_calls}", file=sys.stderr)

# ─────────────────────────────────────────────
# 10. OUTPUT
# ─────────────────────────────────────────────

with open('active_data/section1_parsed.json', 'w', encoding='utf-8') as f:
    json.dump(parsed, f, ensure_ascii=False, indent=2)

with open('active_data/section2_ignored.txt', 'w', encoding='utf-8') as f:
    for raw, reason in ignored:
        f.write(f'- "{raw}" [{reason}]\n')

if errors:
    with open('active_data/parse_errors.txt', 'w', encoding='utf-8') as f:
        for raw, err in errors:
            f.write(f'ERROR: {err}\n  RAW: {raw}\n\n')

print("Output written.", file=sys.stderr)