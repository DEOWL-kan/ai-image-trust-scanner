# Day10 Dataset Format Audit

## Scope

- Scanned `data/test_images/ai` and `data/test_images/real`.
- This script only audits metadata and does not modify source images.

## Format Counts

| true_label | count | detected formats | extensions | PNG | JPEG |
| --- | ---: | --- | --- | ---: | ---: |
| ai | 30 | PNG: 30 | .png: 30 | 30 | 0 |
| real | 30 | JPG: 30 | .jpg: 30 | 0 | 30 |

## Average Size

| true_label | avg width | avg height | avg megapixels | avg file size KB |
| --- | ---: | ---: | ---: | ---: |
| ai | 1404.53 | 1128.13 | 1.5726 | 2431.7 |
| real | 2023.47 | 2762.77 | 7.4515 | 2038.11 |

## Bias Checks

- AI PNG ratio: 100.00%
- Real JPEG ratio: 100.00%
- AI-mostly-PNG vs Real-mostly-JPEG bias: yes
- Dimension bias flag: yes
- File-size bias flag: no

## Conclusion

- The current test set has an obvious format confound: AI samples are mostly PNG while Real samples are mostly JPEG.
- Because the format distribution is not balanced, this original test set cannot be used alone for a final accuracy claim.
- Resolution or file-size differences are large enough to treat current metrics as potentially source-biased.
- Day10 should re-evaluate with controlled PNG/JPEG versions before drawing detector-performance conclusions.

## Output Files

- `reports\day10_dataset_format_audit.csv`
- `reports\day10_dataset_format_audit.md`

_Generated at 2026-05-02T02:05:11+08:00._
