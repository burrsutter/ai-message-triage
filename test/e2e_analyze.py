#!/usr/bin/env python3
"""Analyze Kafka topic captures produced by openshift/e2e-test.sh."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


TOPIC_ORDER = (
    "intake",
    "structured",
    "cleared",
    "ready",
    "support",
    "finance",
    "website",
    "outflow",
    "review",
    "sales",
)


def expected_paths(sample: str) -> list[tuple[str, ...]]:
    common = ("intake", "structured")

    if sample.startswith("bad/"):
        return [common + ("review",)]
    if sample.startswith("finance/"):
        return [common + ("cleared", "ready", "finance", "outflow")]
    if sample.startswith("support/"):
        return [common + ("cleared", "ready", "support", "outflow")]
    if sample.startswith("sales/"):
        return [common + ("cleared", "ready", "review", "sales")]
    if sample == "hr/job-applicant-1.txt":
        # The sample contains mild profanity. Depending on the guardian model it
        # can be reviewed there, or it can clear the guardian and be reviewed as
        # an unsupported HR route.
        return [
            common + ("review",),
            common + ("cleared", "ready", "review"),
        ]
    if sample == "website/bug-report.txt":
        return [common + ("cleared", "ready", "website", "review")]
    if sample == "website/help-login-1.txt":
        # The tool-calling model may interpret a generic login problem as a
        # password reset. Both outcomes are valid for this intentionally vague
        # sample.
        return [
            common + ("cleared", "ready", "website", "outflow"),
            common + ("cleared", "ready", "website", "review"),
        ]
    if sample.startswith("website/"):
        return [common + ("cleared", "ready", "website", "outflow")]

    raise ValueError(f"No end-to-end expectation is defined for {sample}")


def read_samples(samples_file: Path) -> list[str]:
    samples = [line.strip() for line in samples_file.read_text().splitlines() if line.strip()]
    if not samples:
        raise ValueError(f"No samples found in {samples_file}")

    filenames = [Path(sample).name for sample in samples]
    duplicates = sorted(name for name, count in Counter(filenames).items() if count > 1)
    if duplicates:
        raise ValueError(
            "Sample basenames must be unique because intake messages carry only the basename: "
            + ", ".join(duplicates)
        )

    for sample in samples:
        expected_paths(sample)
    return samples


def read_topic_records(topics_dir: Path) -> tuple[dict[str, list[dict]], dict[str, int]]:
    records: dict[str, list[dict]] = {}
    invalid_lines: dict[str, int] = {}

    for topic in TOPIC_ORDER:
        topic_records: list[dict] = []
        invalid = 0
        topic_file = topics_dir / f"{topic}.jsonl"
        if topic_file.exists():
            for raw_line in topic_file.read_text(errors="replace").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    invalid += 1
                    continue
                if isinstance(value, dict):
                    topic_records.append(value)
                else:
                    invalid += 1
        records[topic] = topic_records
        invalid_lines[topic] = invalid

    return records, invalid_lines


def analyze(samples: Iterable[str], records: dict[str, list[dict]]) -> list[dict]:
    occurrences: dict[str, Counter] = defaultdict(Counter)
    for topic in TOPIC_ORDER:
        for record in records.get(topic, []):
            filename = record.get("filename")
            if isinstance(filename, str) and filename:
                occurrences[filename][topic] += 1

    results = []
    for sample in samples:
        filename = Path(sample).name
        observed = tuple(topic for topic in TOPIC_ORDER if occurrences[filename][topic] > 0)
        alternatives = expected_paths(sample)
        passed = observed in alternatives

        closest = min(
            alternatives,
            key=lambda expected: len(set(expected) ^ set(observed)),
        )
        missing = [topic for topic in closest if topic not in observed]
        unexpected = [topic for topic in observed if topic not in closest]

        results.append(
            {
                "sample": sample,
                "filename": filename,
                "status": "PASS" if passed else "FAIL",
                "expected_paths": [list(path) for path in alternatives],
                "observed_path": list(observed),
                "missing_topics": missing,
                "unexpected_topics": unexpected,
                "occurrences": {
                    topic: occurrences[filename][topic]
                    for topic in TOPIC_ORDER
                    if occurrences[filename][topic] > 0
                },
            }
        )
    return results


def path_text(path: Iterable[str]) -> str:
    values = list(path)
    return " → ".join(values) if values else "—"


def write_reports(
    output_dir: Path,
    results: list[dict],
    records: dict[str, list[dict]],
    invalid_lines: dict[str, int],
    submission_failures: list[str],
) -> None:
    passed = sum(result["status"] == "PASS" for result in results)
    failed = len(results) - passed
    overall_failed = failed > 0 or bool(submission_failures)
    generated_at = datetime.now(timezone.utc).isoformat()

    report = {
        "generated_at": generated_at,
        "status": "FAIL" if overall_failed else "PASS",
        "sample_count": len(results),
        "passed": passed,
        "failed": failed,
        "submission_failures": submission_failures,
        "topic_record_counts": {topic: len(records.get(topic, [])) for topic in TOPIC_ORDER},
        "invalid_capture_lines": invalid_lines,
        "samples": results,
    }
    (output_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n")

    tsv_lines = [
        "status\tsample\texpected_paths\tobserved_path\tmissing_topics\tunexpected_topics"
    ]
    for result in results:
        expected = " OR ".join(path_text(path) for path in result["expected_paths"])
        tsv_lines.append(
            "\t".join(
                (
                    result["status"],
                    result["sample"],
                    expected,
                    path_text(result["observed_path"]),
                    ",".join(result["missing_topics"]),
                    ",".join(result["unexpected_topics"]),
                )
            )
        )
    (output_dir / "results.tsv").write_text("\n".join(tsv_lines) + "\n")

    summary_lines = [
        "# AI Message Triage end-to-end test",
        "",
        f"- Result: **{report['status']}**",
        f"- Samples: **{len(results)}**",
        f"- Passed: **{passed}**",
        f"- Failed: **{failed}**",
        f"- Submission failures: **{len(submission_failures)}**",
        f"- Generated: `{generated_at}`",
        "",
        "## Topic record counts",
        "",
        "| Topic | Records | Invalid capture lines |",
        "|---|---:|---:|",
    ]
    for topic in TOPIC_ORDER:
        summary_lines.append(
            f"| `{topic}` | {len(records.get(topic, []))} | {invalid_lines.get(topic, 0)} |"
        )

    summary_lines.extend(
        (
            "",
            "## Per-message paths",
            "",
            "| Result | Sample | Observed path | Difference |",
            "|---|---|---|---|",
        )
    )
    for result in results:
        differences = []
        if result["missing_topics"]:
            differences.append("missing: " + ", ".join(result["missing_topics"]))
        if result["unexpected_topics"]:
            differences.append("unexpected: " + ", ".join(result["unexpected_topics"]))
        summary_lines.append(
            f"| **{result['status']}** | `{result['sample']}` | "
            f"{path_text(result['observed_path'])} | {'; '.join(differences) or '—'} |"
        )

    summary_lines.extend(
        (
            "",
            "Duplicate Kafka records are counted in `results.json` but do not fail this demo test. "
            "Validation compares the set of topics visited by each filename.",
            "",
        )
    )
    (output_dir / "summary.md").write_text("\n".join(summary_lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-file", type=Path, required=True)
    parser.add_argument("--topics-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--submission-failures", type=Path)
    parser.add_argument("--check-samples-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    samples = read_samples(args.samples_file)
    if args.check_samples_only:
        print(f"Expectations are defined for all {len(samples)} samples")
        return 0
    if args.topics_dir is None or args.output_dir is None:
        raise SystemExit("--topics-dir and --output-dir are required unless --check-samples-only is used")
    records, invalid_lines = read_topic_records(args.topics_dir)
    results = analyze(samples, records)
    submission_failures = []
    if args.submission_failures and args.submission_failures.exists():
        submission_failures = [
            line.strip()
            for line in args.submission_failures.read_text().splitlines()
            if line.strip()
        ]
    write_reports(args.output_dir, results, records, invalid_lines, submission_failures)

    failed = [result for result in results if result["status"] == "FAIL"]
    print(
        f"Validated {len(results)} samples: {len(results) - len(failed)} passed, "
        f"{len(failed)} failed, {len(submission_failures)} submission failures"
    )
    for result in failed:
        print(
            f"FAIL {result['sample']}: observed {path_text(result['observed_path'])}; "
            f"missing={','.join(result['missing_topics']) or '-'}; "
            f"unexpected={','.join(result['unexpected_topics']) or '-'}"
        )
    return 1 if failed or submission_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
