
## Matching Decompilation Workflow

The project uses objdiff to measure matching reconstructed source against
locally generated target objects.

Do not commit original game executables, disc images, extracted retail
objects, proprietary compiler binaries, or reverse-engineering database
exports.

Local prerequisites currently include:

- a legally obtained `.hack//INFECTION` NTSC-U `SLUS_202.67`
- the locally installed Metrowerks PS2 R3.01 compiler
- Wibo
- Python
- objdiff-cli

The expected retail executable location is:

`disc/infection/root/SLUS_202.67`

The expected local compiler location is:

`tools/mwcc/r301/mwccps2.exe`

The compiler may alternatively be selected with `MWCC_R301`.

To regenerate the current target inventory and objdiff report:

    scripts/objdiff_report.sh

To verify the first matching function independently:

    python3 scripts/verify_setanalogstick.py

The initial progress scope covers resident EE functions only. Overlays, VU
microcode, and IOP modules will be tracked separately when their pipelines
are introduced.

## Updating the Public Progress Report

When a matching-source contribution changes decompilation progress, regenerate
the local objdiff report before committing:

    scripts/objdiff_report.sh

Then export and validate the public snapshot:

    python3 scripts/export_public_report.py
    python3 scripts/validate_public_report.py

The resulting file is:

    config/infection/report.json

Commit that report together with the source change that caused the progress
change.

GitHub Actions does not receive the retail executable or proprietary
Metrowerks compiler. CI validates and publishes the locally verified progress
snapshot instead.
