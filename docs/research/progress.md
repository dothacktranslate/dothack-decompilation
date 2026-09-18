# Decompilation Progress

Progress is measured with objdiff against target objects generated locally
from the user's legally obtained retail executable.

The repository does not contain the retail executable, extracted retail
machine code, or the proprietary Metrowerks compiler.

## Current Progress Scope

The initial progress denominator covers symbolized resident Emotion Engine
functions in the address range:

`0x00100000-0x001DAC80`

This currently contains:

- 2,232 functions
- 886,144 bytes of function code

The denominator is generated from the retail ELF symbol table by
`scripts/configure_objdiff.py`.

Exact-range aliases and overlapping function ranges are checked before the
inventory is generated so that code is not silently counted twice.

## Current Matching Progress

The first matching function is:

`SetAnalogStick__FPfPUcii`

Demangled:

`SetAnalogStick(float*, unsigned char*, int, int)`

Retail address:

`0x00102390`

Size:

`0x16C` bytes / 364 bytes

Current resident progress:

- Matching functions: 1 / 2,232
- Function progress: approximately 0.044803%
- Matching function bytes: 364 / 886,144
- Byte progress: approximately 0.041077%

The matched function has identical machine code after normalizing the three
link-time `R_MIPS_26` call relocations for `sqrtf`, `fptosi`, and `atan2f`.

## Scope Not Yet Included

The resident denominator does not yet include:

- loadable game overlays
- VU microcode
- IOP modules

Those components use different extraction and/or execution models and will
be added as separate progress scopes once their build pipelines are defined.

## Reproducing the Report

After supplying the required local game files and compiler toolchain:

    scripts/objdiff_report.sh

The generated report is written to:

`build/objdiff/report.json`

Generated target objects and `objdiff.json` are build artifacts and are not
committed to the repository.
