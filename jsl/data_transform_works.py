import json
import os
import re

FILTERED_FILE = "jsl/filtered_jsl_works.jsonl"
METADATA_FILE = "/Users/matthewma/Downloads/jstor_metadata.jsonl"
OUTPUT_FILE = "jsl_works.json"
AUTHORS_FILE = "authors.json"


def parse_year(date_string):
    if not date_string:
        return None
    match = re.search(r"(1[89]\d{2}|20\d{2})", str(date_string))
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def format_creator(creator):
    if not isinstance(creator, dict):
        return None
    first = str(creator.get("first_name", "") or "").strip()
    last = str(creator.get("last_name", "") or "").strip()
    if first and last:
        return f"{first} {last}"
    if last:
        return last
    if first:
        return first
    return None


def normalize_name(s):
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s).strip()).lower()


def load_authors_index(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Authors file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        try:
            authors = json.load(f)
        except json.JSONDecodeError:
            authors = []

    name_to_id = {}
    last_name_map = {}
    for entry in authors:
        aid = entry.get("id")
        full = entry.get("full_name") or ""
        norm_full = normalize_name(full)
        if norm_full:
            name_to_id[norm_full] = aid
        for alt in entry.get("alternative_names", []) or []:
            norm_alt = normalize_name(alt)
            if norm_alt:
                name_to_id[norm_alt] = aid
        parts = full.split()
        if parts:
            last = parts[-1].strip().strip('.,').lower()
            if last:
                last_name_map.setdefault(last, []).append(aid)

    return name_to_id, last_name_map


def get_creator_ids(creators, name_to_id, last_name_map):
    if not creators:
        return None
    ids = []
    for c in creators:
        name = format_creator(c)
        if not name:
            continue
        key = normalize_name(name)
        if key in name_to_id:
            ids.append(name_to_id[key])
            continue
        # fallback: try matching by last name when unique
        last = name.split()[-1].strip().strip('.,').lower()
        matches = last_name_map.get(last, [])
        if len(matches) == 1:
            ids.append(matches[0])
        else:
            # no id found; keep the formatted name as fallback so information isn't lost
            ids.append(name)
    return ids if ids else None


def build_author_string(creators):
    if not creators:
        return None
    names = [format_creator(c) for c in creators]
    names = [n for n in names if n]
    return ", ".join(names) if names else None


def load_filtered_works(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Filtered works file not found: {filepath}")

    filtered = []
    item_ids = set()
    with open(filepath, "r", encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            record = json.loads(raw_line)
            item_id = record.get("item_id") or record.get("id")
            if not item_id:
                continue
            filtered.append(record)
            item_ids.add(item_id)
    return filtered, item_ids


def load_metadata_by_id(filepath, item_ids):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Metadata file not found: {filepath}")

    metadata = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            item_id = record.get("item_id")
            if item_id in item_ids:
                metadata[item_id] = record
                if len(metadata) == len(item_ids):
                    break
    return metadata


def normalize_journal(record):
    if not record:
        return None
    return record.get("publication_title") or record.get("journal") or record.get("is_part_of") or record.get("source")


def normalize_title(record, fallback_title):
    if not record:
        return fallback_title
    return record.get("title") or record.get("is_part_of") or fallback_title


def normalize_volume(record, filtered_record):
    if not record:
        return filtered_record.get("volume")
    return record.get("issue_volume") or filtered_record.get("volume")


def normalize_number(record, filtered_record):
    if not record:
        return filtered_record.get("issue_number")
    return record.get("issue_number") or filtered_record.get("issue_number")


def normalize_url(record, filtered_record):
    if not record:
        return filtered_record.get("url")
    return record.get("url") or filtered_record.get("url")


def transform(filtered_record, metadata_record, name_to_id, last_name_map):
    title = normalize_title(metadata_record, filtered_record.get("title"))
    creators = metadata_record.get("creators") if metadata_record else filtered_record.get("creators")
    authors = get_creator_ids(creators, name_to_id, last_name_map)
    year = parse_year(metadata_record.get("published_date") if metadata_record else filtered_record.get("published_date"))
    journal = normalize_journal(metadata_record) or None
    volume = normalize_volume(metadata_record, filtered_record)
    number = normalize_number(metadata_record, filtered_record)
    url = normalize_url(metadata_record, filtered_record)

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "type": "article",
        "journal": journal,
        "volume": volume,
        "number": number,
        "url": url,
        "alternative_titles": None
    }


def main():
    filtered_works, item_ids = load_filtered_works(FILTERED_FILE)
    metadata = load_metadata_by_id(METADATA_FILE, item_ids)
    name_to_id, last_name_map = load_authors_index(AUTHORS_FILE)

    output = {}
    missing = []
    for work in filtered_works:
        item_id = work.get("item_id") or work.get("id")
        metadata_record = metadata.get(item_id)
        if metadata_record is None:
            missing.append(item_id)
        output[item_id] = transform(work, metadata_record, name_to_id, last_name_map)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    print(f"Wrote {len(output)} works to {OUTPUT_FILE}.")
    if missing:
        print(f"Warning: {len(missing)} filtered works were missing metadata. Their fields were filled from the filtered record where possible.")


if __name__ == "__main__":
    main()
