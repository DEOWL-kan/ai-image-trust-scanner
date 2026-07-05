# ft_smogy_lora_v2 Model Card

Status: not included in public v1.

This directory is a placeholder for documentation only. The public v1
repository does not ship the adapter weights.

## Purpose

`ft_smogy_lora_v2` is intended as an optional PEFT/LoRA adapter for the
`Smogy/SMOGY-Ai-images-detector` base model in local HF mode.

## Training And Evaluation Summary

The private research archive contains adapter experiments and held-out replay
reports. Public v1 does not include the generated training manifests, datasets,
or adapter weights.

Before publishing weights, add:

- training command
- base model revision
- adapter checksum
- dataset provenance summary
- evaluation protocol
- metrics by dataset/source

## Data Provenance

License status is not yet cleared for redistribution. Do not publish adapter
weights until the base model, training data, and generated derivatives are
reviewed.

## License Status

Unknown / not cleared for public redistribution in v1.

## Intended Use

- Local, opt-in evidence generation for image trust review.
- Research and evaluation by users who can legally obtain the adapter and base
  model.

## Out-of-Scope Use

- Legal or forensic certainty claims.
- Automated enforcement without human review.
- Surveillance, biometric identification, or claims about a person.
- Use without respecting base model and dataset licenses.

## Metrics

Public v1 does not publish adapter metrics as reproducible release evidence.
Metrics should be added only with pinned revisions, checksums, and public or
properly licensed evaluation data.

## Bias And Robustness Warnings

AI-image detection can be sensitive to generator family, compression, resizing,
screenshots, camera metadata, and dataset collection bias. Real images can be
false positives. AI images can be false negatives. Treat outputs as review
signals, not truth.
