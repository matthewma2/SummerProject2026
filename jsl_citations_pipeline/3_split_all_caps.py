import json
import re
from pathlib import Path

src = Path("jsl_citations_data/2b_unresolved.json")
all_caps_path = Path("jsl_citations_data/3a_all_caps_authors.json")
rest_path = Path("jsl_citations_data/3b_unresolved.json")

items = json.loads(src.read_text(encoding="utf-8"))

connectors = {"and", "et", "und", "y", "e", "with"}
particles = {"v", "von", "van", "de", "del", "der", "den", "di", "du"}
word_re = re.compile(r"[A-Za-zÀ-ÖØ-ÞĀ-ſ]+|[,.]")


def is_initial(letters):
    return len(letters) == 1 and letters.upper() == letters


def is_allowed_author_word(token):
    letters = "".join(ch for ch in token if ch.isalpha())
    if not letters:
        return False, False

    lower = letters.lower()

    if lower in connectors:
        return True, False

    if lower in particles:
        return True, False

    if is_initial(letters):
        return True, False

    if letters == letters.upper():
        return True, True

    return False, False


def starts_with_all_caps_author(s):
    tokens = word_re.findall(s.strip())
    saw_upper_name = False
    previous_was_upper_name = False

    for token in tokens:
        if token == ",":
            return saw_upper_name

        if token == ".":
            if previous_was_upper_name:
                return True
            previous_was_upper_name = False
            continue

        allowed, is_upper_name = is_allowed_author_word(token)
        if not allowed:
            return False

        saw_upper_name = saw_upper_name or is_upper_name
        previous_was_upper_name = is_upper_name

    return saw_upper_name


all_caps = []
rest = []

for item in items:
    if starts_with_all_caps_author(item):
        all_caps.append(item)
    else:
        rest.append(item)

all_caps_path.write_text(
    json.dumps(all_caps, indent=4, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

rest_path.write_text(
    json.dumps(rest, indent=4, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

print(f"total={len(items)} all_caps={len(all_caps)} rest={len(rest)}")
print(all_caps_path)
print(rest_path)
