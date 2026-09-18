# decomp.dev Reporting

The project publishes an objdiff version 2 progress report through GitHub
Actions.

The public report is intentionally build-free in CI because the complete
matching build currently depends on two inputs that must not be committed to
the repository:

- the original retail executable
- the proprietary Metrowerks PlayStation 2 compiler

Matching is therefore verified locally first.

The local workflow is:

    scripts/objdiff_report.sh
    python3 scripts/export_public_report.py
    python3 scripts/validate_public_report.py

The first command performs the real objdiff measurement using locally
generated targets and compiled source.

The exporter then produces:

    config/infection/report.json

This file contains progress information only. It does not contain retail
machine code, original game files, compiler binaries, or local filesystem
paths.

GitHub Actions validates the committed report on pushes and pull requests.

On pushes to main, and on manual workflow runs, Actions also uploads:

    infection_report

The artifact contains:

    report.json

This is the report artifact intended for decomp.dev ingestion.

## Trust Model

The public CI job validates the structure and safety of the committed report.
It does not independently compile Metrowerks source because the proprietary
compiler and retail executable are deliberately unavailable to GitHub-hosted
runners.

Before progress changes are committed, contributors should regenerate the
report locally using the matching toolchain.

A future self-hosted or otherwise securely provisioned runner could perform
the complete matching build in CI without changing the public report format.
