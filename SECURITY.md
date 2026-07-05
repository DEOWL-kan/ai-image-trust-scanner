# Security Policy

## Supported Versions

Public v1 is pre-release software. Security fixes should target the current
default branch until formal releases are created.

## Reporting A Vulnerability

Please do not open public issues for vulnerabilities involving secrets, private
files, path traversal, generated report disclosure, or unsafe model loading.

Report privately to the project maintainers through the repository security
contact or GitHub private vulnerability reporting when enabled.

Include:

- affected version or commit
- reproduction steps
- impact
- whether private images, reports, or local paths can be exposed

## Data Handling

The app is designed for local use. Do not upload private images or reports to
public issues. Runtime outputs are written under `.tmp/` by default and are
ignored by git.

## Model Safety

Optional model mode can load local Hugging Face models and adapters. Only load
weights from sources you trust and licenses you can comply with.
