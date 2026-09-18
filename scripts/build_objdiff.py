#!/usr/bin/env python3

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]

TARGET = (
    ROOT
    / "build/objdiff/target/prog/system/syspad/SetAnalogStick.o"
)

BASE = (
    ROOT
    / "build/objdiff/base/prog/system/syspad/SetAnalogStick.o"
)

SOURCE = (
    ROOT
    / "src/infection/prog/system/syspad.cpp"
)

WRAPPER = ROOT / "scripts/mwcc-r301.sh"

GENERATOR = (
    ROOT
    / "scripts/generate_setanalogstick_target.py"
)

RETAIL = (
    ROOT
    / "disc/infection/root/SLUS_202.67"
)


def build_base():
    BASE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    subprocess.run(
        [
            str(WRAPPER),
            "--gcc-compat",
            "-nosyspath",
            "-O3,p",
            "-str=readonly",
            "-g",
            "-c",
            "-o",
            str(BASE),
            str(SOURCE),
        ],
        cwd=ROOT,
        check=True,
    )


def build_target():
    # Copy MIPS architecture flags from a real R3.01 object.
    if not BASE.exists():
        build_base()

    TARGET.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "--retail",
            str(RETAIL),
            "--flags-from",
            str(BASE),
            "--output",
            str(TARGET),
        ],
        cwd=ROOT,
        check=True,
    )


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: build_objdiff.py <object-path>"
        )

    requested = Path(sys.argv[1])

    if not requested.is_absolute():
        requested = ROOT / requested

    requested = requested.resolve()

    if requested == BASE.resolve():
        build_base()
        return

    if requested == TARGET.resolve():
        build_target()
        return

    raise SystemExit(
        f"unknown objdiff build target: {requested}"
    )


if __name__ == "__main__":
    main()
