# Benchmarks & Accuracy

**Read this before quoting any number.** This project is an evidence-chain scanner, not a single-score detector. The pipeline emits three outcomes — `real`, `ai`, and `uncertain` (routed to human review) — so there are two very different "accuracy" figures:

- **Strict accuracy** counts every `uncertain` as wrong. It is deliberately conservative (~69–76% on hard sets).
- **Decided accuracy** measures only the images the system was confident enough to label. It is high (~93–95%) *because* ambiguous cases are sent to review instead of guessed.

> Approved wording: *"In clear decisions, roughly 94–95% accuracy on current local API sample tests, with low real-image false positives; ambiguous cases are routed to review."*
> Do **not** claim "95% universal AI-image detection accuracy." That is not what these numbers mean.

All figures below are measured on modest samples (hundreds, not tens of thousands), against unpinned upstream model revisions. Treat them as directional evidence, not universal guarantees.

---

## What actually runs in each mode

| Mode | Ships in v1 | What produces the verdict |
| --- | --- | --- |
| **CPU-safe default** (`stub`) | ✅ yes | Lightweight baseline + C2PA provenance + EXIF/metadata + forensic heuristics + policy + review |
| **Optional base HF models** (`local_hf`) | ⚙️ opt-in, you download the models | Adds `Smogy/SMOGY-Ai-images-detector` (primary) and `Ateeqq/ai-vs-human-image-detector` (secondary) |
| **Optional LoRA adapter** (`ft_smogy_lora_v2`) | ❌ **not shipped** | Fine-tuned Smogy adapter — the strongest numbers, but not redistributed in v1 |

The three tiers below map to these three rows. **The impressive numbers require the optional models. The default mode's value is the evidence chain and review workflow, not standalone detection accuracy.**

---

## Tier 1 — CPU-safe default (lightweight baseline)

The bundled default does **not** run a trained deep detector. On hard AI-vs-real sets the lightweight baseline alone is near chance (accuracy ≈ 49% on Mirage-Test, with most images routed to `uncertain`). Its job is **not** to be a strong standalone classifier — it is to:

- surface C2PA provenance when present (fast, exact, but only on unmodified originals),
- read EXIF/metadata signals,
- run cheap forensic heuristics,
- and route anything ambiguous into the review queue with an auditable evidence trail.

**If you need detection accuracy, enable the optional models below.** Use the default for provenance/metadata triage and as a safe, dependency-free starting point.

## Tier 2 — Optional base HF models (reproducible)

Standalone base `Smogy/SMOGY-Ai-images-detector`, raw classifier, no adapter, no policy gate, on cached **Mirage-Test (n=500, 250 AI / 250 real)**:

| Detector | Accuracy | AUROC | AI recall | Real false-positive rate |
| --- | --- | --- | --- | --- |
| **Smogy (primary)** | **88.4%** | **0.921** | 86.4% | 9.6% |
| Ateeqq (secondary) | 79.6% | 0.861 | — | 28.4% (high) |
| dima806 (diagnostic) | 48.8% | 0.465 | 4.4% | — (not recommended) |
| lightweight baseline | 48.8% | — | — | — |

*Source: internal Day36 detector benchmark, single domain (Mirage only). Reproducible if you download the base model; numbers are against unpinned upstream weights.*

## Tier 3 — Optional LoRA adapter `ft_smogy_lora_v2` (NOT shipped in v1)

> ⚠️ **These numbers are not reproducible from this repository.** The adapter weights are not redistributed pending license review of the base model and training data. They are documented here for honesty and to justify the tuning direction — not as a claim you can verify by cloning.

Full product pipeline (Smogy + LoRA v2 + Ateeqq secondary, `strict_safe_plus` policy, `ai_threshold=0.85`), measured 2026-05-31:

| Dataset (n) | Strict acc | Decided acc | AI recall | Real FP | macro-F1 | Uncertain→review |
| --- | --- | --- | --- | --- | --- | --- |
| **Defactify (400)** | 76.25% | ~95% | 73.5% | **1.0%** | 0.859 | 22.5% |
| **Mirage (300)** | 71.33% | ~94% | 92.67% | 7.33% | 0.794 | 24.33% |

LoRA v2 vs base on a leakage-free held-out set (n=1144): overall AI recall **74.0% → 88.8%**, real FP **7.3% → 5.6%**, with large gains on weak generators (SDXL 58.8%→95.0%, SD3 36.2%→76.2%).

---

## Methodology & datasets

- **Datasets:** Defactify (DALL·E 3 / Midjourney / SD 2.1 / SD3 / SDXL), Mirage, DiTFake, plus CIFAKE for sanity checks only. Balanced real/AI splits, fixed seeds.
- **Leakage control:** LoRA evaluation used a held-out split with no training overlap (verified by sha256 intersection).
- **Policy:** `strict_safe_plus` prioritizes low real-image false positives and routes ambiguous cases to review.
- **Hardware/latency:** CPU-capable; p50 ≈ 1.1 s, p95 up to 8–10 s on large real images in HF mode.

## Known limitations — what NOT to conclude

- **No single headline accuracy.** Strict vs decided accuracy measure different things; always state which.
- **Modest sample sizes** (hundreds). No large-scale (10k+) independent real-world evaluation.
- **Model revisions are not pinned** — upstream HF weights can change; pin revisions locally before comparing.
- **Weak spots:** per-generator recall is lower on SD3 (~45–57%) and Midjourney (~50–54%); Mirage real-image false positives (~7–9%, up to ~15% for the raw adapter) are the known safety burden; 60–75% review rate is by design.
- **CIFAKE accuracy (≈98%) is deliberately not cited** — its 32×32 images likely overlap public detector training distributions and do not reflect real-world performance.
- **C2PA "100%" is provenance matching, not detection accuracy** — it only applies to unmodified originals and does not survive re-save, crop, or metadata stripping. Missing metadata does **not** imply an image is AI-generated.

*Numbers sourced from the private research archive (2026-05 evaluation runs). Detection results are risk signals for review, not legal or forensic proof.*
