#!/usr/bin/env python3

from pathlib import Path
import argparse
import json
import re


SAFE_METADATA_KEYS = {
    "demangled_name",
    "auto_generated",
    "category",
}

FORBIDDEN_PATTERNS = [
    re.compile(r"/home/", re.IGNORECASE),
    re.compile(r"/mnt/", re.IGNORECASE),
    re.compile(r"/tmp/", re.IGNORECASE),
    re.compile(r"[A-Za-z]:\\\\"),
    re.compile(r"disc/infection/root", re.IGNORECASE),
    re.compile(r"tools/mwcc", re.IGNORECASE),
    re.compile(r"SLUS_202\.67", re.IGNORECASE),
    re.compile(r"mwccps2\.exe", re.IGNORECASE),
]


def scalar(value):
    return (
        value is None
        or isinstance(
            value,
            (str, int, float, bool),
        )
    )


def clean_measures(value):
    if not isinstance(value, dict):
        return {}

    result = {}

    for key, item in value.items():
        if scalar(item):
            result[str(key)] = item

    return result


def clean_metadata(value):
    if not isinstance(value, dict):
        return {}

    result = {}

    for key in SAFE_METADATA_KEYS:
        if key not in value:
            continue

        item = value[key]

        if scalar(item):
            result[key] = item

    return result


def clean_section(section):
    result = {}

    if "name" in section:
        result["name"] = section["name"]

    if "size" in section:
        result["size"] = section["size"]

    if "fuzzy_match_percent" in section:
        result["fuzzy_match_percent"] = (
            section["fuzzy_match_percent"]
        )

    result["metadata"] = clean_metadata(
        section.get("metadata", {})
    )

    return result


def clean_function(function):
    result = {}

    for key in (
        "name",
        "size",
        "fuzzy_match_percent",
        "address",
    ):
        if key in function:
            result[key] = function[key]

    result["metadata"] = clean_metadata(
        function.get("metadata", {})
    )

    return result


def clean_unit(unit):
    result = {
        "name": unit["name"],
        "measures": clean_measures(
            unit.get("measures", {})
        ),
        "sections": [
            clean_section(section)
            for section in unit.get(
                "sections",
                [],
            )
        ],
        "functions": [
            clean_function(function)
            for function in unit.get(
                "functions",
                [],
            )
        ],
        "metadata": clean_metadata(
            unit.get("metadata", {})
        ),
    }

    return result


def check_forbidden(text):
    for pattern in FORBIDDEN_PATTERNS:
        match = pattern.search(text)

        if match:
            raise RuntimeError(
                "public report contains forbidden "
                f"text: {match.group(0)!r}"
            )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "build/objdiff/report.json"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "config/infection/report.json"
        ),
    )

    args = parser.parse_args()

    raw = json.loads(
        args.input.read_text(
            encoding="utf-8"
        )
    )

    if raw.get("version") != 2:
        raise RuntimeError(
            "expected objdiff report version 2"
        )

    public = {
        "measures": clean_measures(
            raw.get("measures", {})
        ),
        "units": [
            clean_unit(unit)
            for unit in raw.get(
                "units",
                [],
            )
        ],
        "version": 2,
    }

    text = json.dumps(
        public,
        separators=(",", ":"),
        ensure_ascii=False,
    ) + "\n"

    check_forbidden(text)

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        text,
        encoding="utf-8",
    )

    measures = public["measures"]

    print("Public report exported")
    print("======================")
    print(f"Output:            {args.output}")
    print(
        f"Units:             "
        f"{len(public['units'])}"
    )
    print(
        f"Total functions:   "
        f"{measures.get('total_functions')}"
    )
    print(
        f"Matched functions: "
        f"{measures.get('matched_functions')}"
    )
    print(
        f"Total code:        "
        f"{measures.get('total_code')}"
    )
    print(
        f"Matched code:      "
        f"{measures.get('matched_code')}"
    )


if __name__ == "__main__":
    main()
