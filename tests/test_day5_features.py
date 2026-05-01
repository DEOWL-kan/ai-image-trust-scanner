from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.day5_reports import run_day5_analysis
from src.explainable import classify_features
from src.features import extract_image_features


def create_sample_image(path: Path, size: tuple[int, int] = (32, 24)) -> None:
    image = Image.new("RGB", size)
    pixels = []
    for y in range(size[1]):
        for x in range(size[0]):
            pixels.append(((x * 7) % 256, (y * 11) % 256, ((x + y) * 5) % 256))
    image.putdata(pixels)
    image.save(path)


class Day5FeatureTests(unittest.TestCase):
    def test_single_image_extracts_features(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "sample.png"
            create_sample_image(image_path)

            features = extract_image_features(image_path)

            self.assertEqual(features["file_name"], "sample.png")
            self.assertEqual(features["width"], 32)
            self.assertEqual(features["height"], 24)
            self.assertIn("sharpness_score", features)
            self.assertIn("edge_density", features)
            self.assertIn("color_entropy", features)

    def test_empty_directory_writes_reports_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "empty"
            output_dir = root / "reports"
            input_dir.mkdir()

            result = run_day5_analysis(input_dir, output_dir, project_root=root)

            self.assertEqual(result["metrics"]["total_images"], 0)
            self.assertEqual(result["metrics"]["found_image_count"], 0)
            self.assertTrue((output_dir / "feature_report.jsonl").exists())
            self.assertTrue((output_dir / "feature_summary.csv").exists())
            self.assertTrue((output_dir / "explainable_report.md").exists())
            self.assertTrue((output_dir / "day5_metrics.json").exists())
            self.assertTrue((output_dir / "calibration_analysis.md").exists())
            report = (output_dir / "explainable_report.md").read_text(encoding="utf-8")
            self.assertIn("No supported image files found under input path.", report)

    def test_unsupported_file_type_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "dataset"
            output_dir = root / "reports"
            input_dir.mkdir()
            (input_dir / "notes.txt").write_text("not an image", encoding="utf-8")

            result = run_day5_analysis(input_dir, output_dir, project_root=root)

            self.assertEqual(result["metrics"]["total_images"], 0)
            self.assertEqual(result["metrics"]["skipped_file_count"], 1)
            summary_rows = (output_dir / "feature_summary.csv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(summary_rows), 1)

    def test_recursive_directory_images_are_found(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested_dir = root / "dataset" / "real" / "nested"
            output_dir = root / "reports"
            nested_dir.mkdir(parents=True)
            create_sample_image(nested_dir / "deep_sample.png")

            result = run_day5_analysis(root / "dataset", output_dir, project_root=root)

            self.assertEqual(result["metrics"]["found_image_count"], 1)
            self.assertEqual(result["metrics"]["processed_count"], 1)

    def test_uppercase_suffix_image_is_found(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "dataset" / "ai"
            output_dir = root / "reports"
            input_dir.mkdir(parents=True)
            create_sample_image(input_dir / "upper.JPG")

            result = run_day5_analysis(root / "dataset", output_dir, project_root=root)

            self.assertEqual(result["metrics"]["found_image_count"], 1)
            self.assertEqual(result["metrics"]["processed_count"], 1)

    def test_report_files_exist_for_supported_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "dataset" / "real"
            output_dir = root / "reports"
            input_dir.mkdir(parents=True)
            create_sample_image(input_dir / "real_sample.jpg")

            result = run_day5_analysis(root / "dataset", output_dir, project_root=root)

            self.assertEqual(result["metrics"]["total_images"], 1)
            self.assertEqual(result["metrics"]["found_image_count"], 1)
            self.assertTrue((output_dir / "feature_report.jsonl").exists())
            self.assertTrue((output_dir / "feature_summary.csv").exists())
            self.assertTrue((output_dir / "explainable_report.md").exists())
            self.assertTrue((output_dir / "day5_metrics.json").exists())
            self.assertTrue((output_dir / "calibration_analysis.md").exists())

            jsonl = (output_dir / "feature_report.jsonl").read_text(encoding="utf-8").strip()
            payload = json.loads(jsonl)
            self.assertEqual(payload["true_label"], "real")

    def test_corrupted_supported_image_is_recorded_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "dataset" / "ai"
            output_dir = root / "reports"
            input_dir.mkdir(parents=True)
            (input_dir / "broken.png").write_text("not actually an image", encoding="utf-8")

            result = run_day5_analysis(root / "dataset", output_dir, project_root=root)

            self.assertEqual(result["metrics"]["found_image_count"], 1)
            self.assertEqual(result["metrics"]["processed_count"], 0)
            self.assertEqual(result["metrics"]["error_count"], 1)
            jsonl = (output_dir / "feature_report.jsonl").read_text(encoding="utf-8").strip()
            payload = json.loads(jsonl)
            self.assertEqual(payload["status"], "error")

    def test_risk_score_stays_between_zero_and_one_hundred(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "sample.png"
            create_sample_image(image_path)
            features = extract_image_features(image_path)

            explanation = classify_features(features)

            self.assertGreaterEqual(explanation["risk_score"], 0)
            self.assertLessEqual(explanation["risk_score"], 100)
            self.assertIn(explanation["prediction"], {"likely_real", "uncertain", "likely_ai"})


if __name__ == "__main__":
    unittest.main()
