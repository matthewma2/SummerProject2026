import json
from pathlib import Path


src = Path("active_data/2b_unresolved.json")
less_than_25_path = Path("active_data/3a_less_than_25.json")
between_25_and_43_path = Path("active_data/3b_between_25_and_43.json")
more_than_43_path = Path("active_data/3c_more_than_43.json")


items = json.loads(src.read_text(encoding="utf-8"))

less_than_25 = []
between_25_and_43 = []
more_than_43 = []

for item in items:
    item_len = len(item)

    if item_len < 25:
        less_than_25.append(item)
    elif item_len <= 43:
        between_25_and_43.append(item)
    else:
        more_than_43.append(item)


less_than_25_path.write_text(
    json.dumps(less_than_25, indent=4, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

between_25_and_43_path.write_text(
    json.dumps(between_25_and_43, indent=4, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

more_than_43_path.write_text(
    json.dumps(more_than_43, indent=4, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

print(
    f"total={len(items)} "
    f"less_than_25={len(less_than_25)} "
    f"between_25_and_43={len(between_25_and_43)} "
    f"more_than_43={len(more_than_43)}"
)
print(less_than_25_path)
print(between_25_and_43_path)
print(more_than_43_path)
