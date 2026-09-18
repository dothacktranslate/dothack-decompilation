#!/usr/bin/env python3

from pathlib import Path
import argparse
import json
import re
import sys


FORBIDDEN_PATTERNS = [
    re.compile(r"/home/", re.IGNORECASE),
    re.compile(r"/mnt/", re.IGNORECASE),
    re.compile(r"/tmp/", re.IGNORECASE),
    re.compile(r"[A-Za-z]:\\\\"),
    re.compile(r"disc/infection/root", re.IGNORECASE),
    re.compile(r"tools/mwcc", re.IGNORECASE),
    re.compile(r"SLUS_202\.67", re.IGNORECASE),
    re.compile(r"mwccps2\.exe", re.IGNORECASE),
    re.compile(r'"(?:bytes|data_blob|raw_data)"\s*:', re.IGNORECASE),
]


def integer_measure(measures, name):
    value = measures.get(name, 0)

    if value is None:
        return 0

    return int(value)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "report",
        nargs="?",
        type=Path,
        default=Path(
            "config/infection/report.json"
        ),
    )

    args = parser.parse_args()

    text = args.report.read_text(
        encoding="utf-8"
    )

    for pattern in FORBIDDEN_PATTERNS:
        match = pattern.search(text)

        if match:
            raise SystemExit(
                "FAIL: report contains forbidden "
                f"text: {match.group(0)!r}"
            )

    report = json.loads(text)

    if report.get("version") != 2:
        raise SystemExit(
            "FAIL: report version must be 2"
        )

    units = report.get("units")

    if not isinstance(units, list):
        raise SystemExit(
            "FAIL: units must be a list"
        )

    root = report.get("measures", {})

    total_units = integer_measure(
        root,
        "total_units",
    )

    total_code = integer_measure(
        root,
        "total_code",
    )

    matched_code = integer_measure(
        root,
        "matched_code",
    )

    total_functions = integer_measure(
        root,
        "total_functions",
    )

    matched_functions = integer_measure(
        root,
        "matched_functions",
    )

    if total_units != len(units):
        raise SystemExit(
            "FAIL: total_units does not "
            "match unit count"
        )

    if total_code <= 0:
        raise SystemExit(
            "FAIL: total_code must be positive"
        )

    if not (
        0 <= matched_code <= total_code
    ):
        raise SystemExit(
            "FAIL: invalid matched_code"
        )

    if not (
        0
        <= matched_functions
        <= total_functions
    ):
        raise SystemExit(
            "FAIL: invalid matched_functions"
        )

    sum_total_code = 0
    sum_matched_code = 0
    sum_total_functions = 0
    sum_matched_functions = 0

    names = set()

    for unit in units:
        name = unit.get("name")

        if not isinstance(name, str):
            raise SystemExit(
                "FAIL: unit without string name"
            )

        if name in names:
            raise SystemExit(
                f"FAIL: duplicate unit {name}"
            )

        names.add(name)

        measures = unit.get(
            "measures",
            {},
        )

        unit_total_code = integer_measure(
            measures,
            "total_code",
        )

        unit_matched_code = integer_measure(
            measures,
            "matched_code",
        )

        unit_total_functions = (
            integer_measure(
                measures,
                "total_functions",
            )
        )

        unit_matched_functions = (
            integer_measure(
                measures,
                "matched_functions",
            )
        )

        if unit_matched_code > unit_total_code:
            raise SystemExit(
                "FAIL: matched code exceeds "
                f"total in {name}"
            )

        if (
            unit_matched_functions
            > unit_total_functions
        ):
            raise SystemExit(
                "FAIL: matched functions exceed "
                f"total in {name}"
            )

        sum_total_code += unit_total_code
        sum_matched_code += unit_matched_code
        sum_total_functions += (
            unit_total_functions
        )
        sum_matched_functions += (
            unit_matched_functions
        )

    checks = [
        (
            "total_code",
            total_code,
            sum_total_code,
        ),
        (
            "matched_code",
            matched_code,
            sum_matched_code,
        ),
        (
            "total_functions",
            total_functions,
            sum_total_functions,
        ),
        (
            "matched_functions",
            matched_functions,
            sum_matched_functions,
        ),
    ]

    for label, root_value, summed in checks:
        if root_value != summed:
            raise SystemExit(
                f"FAIL: root {label}="
                f"{root_value}, unit sum={summed}"
            )

    setanalog_name = (
        "prog/system/syspad/SetAnalogStick"
    )

    matches = [
        unit
        for unit in units
        if unit["name"]
        == setanalog_name
    ]

    if len(matches) != 1:
        raise SystemExit(
            "FAIL: SetAnalogStick unit missing"
        )

    sm = matches[0].get(
        "measures",
        {},
    )

    if integer_measure(
        sm,
        "total_code",
    ) != 364:
        raise SystemExit(
            "FAIL: SetAnalogStick size changed"
        )

    if integer_measure(
        sm,
        "matched_code",
    ) != 364:
        raise SystemExit(
            "FAIL: SetAnalogStick no longer "
            "reports as matched"
        )

    byte_percent = (
        matched_code
        / total_code
        * 100.0
    )

    function_percent = (
        matched_functions
        / total_functions
        * 100.0
        if total_functions
        else 0.0
    )

    print("Public report validation")
    print("========================")
    print(
        f"Units:              "
        f"{total_units}"
    )
    print(
        f"Functions:          "
        f"{matched_functions}/"
        f"{total_functions}"
    )
    print(
        f"Function progress:  "
        f"{function_percent:.6f}%"
    )
    print(
        f"Code bytes:         "
        f"{matched_code}/"
        f"{total_code}"
    )
    print(
        f"Byte progress:      "
        f"{byte_percent:.6f}%"
    )
    print()
    print(
        "PASS: public report is internally "
        "consistent and contains no prohibited "
        "local/game/toolchain paths."
    )


if __name__ == "__main__":
    main()
