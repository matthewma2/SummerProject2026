import json
from pathlib import Path


def split_strings_by_length(source_path: Path, max_length: int = 25) -> tuple[list[str], list[str]]:
    with source_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {source_path}, got {type(data).__name__}")

    shorter_or_equal = [item for item in data if isinstance(item, str) and len(item) <= max_length]
    longer = [item for item in data if isinstance(item, str) and len(item) > max_length]
    return shorter_or_equal, longer


def write_json(data: list[str], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Split a JSON array of strings into two files by string length."
    )
    parser.add_argument(
        "source",
        type=Path,
        nargs="?",
        default=Path("active_data/jsl_unresolved_reference_strings_rest_with_author.json"),
        help="Path to the source JSON file containing a list of strings.",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=25,
        help="Maximum length for the first output file (inclusive).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("active_data"),
        help="Directory to write the output files.",
    )

    args = parser.parse_args()

    shorter_or_equal, longer = split_strings_by_length(args.source, args.max_length)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    small_path = output_dir / "less_than_or_equal_25.json"
    large_path = output_dir / "more_than_25.json"

    write_json(shorter_or_equal, small_path)
    write_json(longer, large_path)

    print(f"Wrote {len(shorter_or_equal)} strings <= {args.max_length} to {small_path}")
    print(f"Wrote {len(longer)} strings > {args.max_length} to {large_path}")
