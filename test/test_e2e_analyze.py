import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "test" / "e2e_analyze.py"
SPEC = importlib.util.spec_from_file_location("message_triage_e2e_analyze", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
e2e_analyze = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(e2e_analyze)


class E2EAnalyzeTests(unittest.TestCase):
    def records_for(self, filename, path):
        records = {topic: [] for topic in e2e_analyze.TOPIC_ORDER}
        for topic in path:
            records[topic].append({"filename": filename})
        return records

    def test_all_repository_samples_have_expectations(self):
        samples = sorted(
            str(path.relative_to(REPO_ROOT / "data" / "sample"))
            for path in (REPO_ROOT / "data" / "sample").glob("*/*")
            if path.is_file()
        )

        self.assertEqual(23, len(samples))
        for sample in samples:
            self.assertTrue(e2e_analyze.expected_paths(sample))

    def test_expected_path_passes(self):
        sample = "sales/prospect-bulk-order-1.txt"
        expected = e2e_analyze.expected_paths(sample)[0]
        records = self.records_for(Path(sample).name, expected)

        result = e2e_analyze.analyze([sample], records)[0]

        self.assertEqual("PASS", result["status"])
        self.assertEqual(list(expected), result["observed_path"])

    def test_duplicate_records_do_not_fail(self):
        sample = "finance/duplicate-charge-1.txt"
        expected = e2e_analyze.expected_paths(sample)[0]
        records = self.records_for(Path(sample).name, expected)
        records["finance"].append({"filename": Path(sample).name})

        result = e2e_analyze.analyze([sample], records)[0]

        self.assertEqual("PASS", result["status"])
        self.assertEqual(2, result["occurrences"]["finance"])

    def test_unexpected_topic_fails(self):
        sample = "bad/bad-message-1.txt"
        expected = e2e_analyze.expected_paths(sample)[0]
        records = self.records_for(Path(sample).name, expected)
        records["sales"].append({"filename": Path(sample).name})

        result = e2e_analyze.analyze([sample], records)[0]

        self.assertEqual("FAIL", result["status"])
        self.assertEqual(["sales"], result["unexpected_topics"])


if __name__ == "__main__":
    unittest.main()
