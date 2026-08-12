#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools" / "IxAdapter"))

import ix_adapter  # noqa: E402


class _Completed:
    def __init__(self, returncode: int = 0, stdout: str = "{}", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _args(operation: str, target: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        operation=operation,
        target=target,
        repo_root=str(ROOT),
        timeout=10,
        min_confidence=0.5,
        depth=3,
        cap=100,
        direction="both",
        kind=None,
        include_tests=False,
    )


class IxAdapterTests(unittest.TestCase):
    def test_missing_cli_is_unavailable_and_falls_back(self) -> None:
        with patch("ix_adapter.shutil.which", return_value=None):
            result = ix_adapter.execute(_args("probe"))

        self.assertEqual("unavailable", result["status"])
        self.assertFalse(result["available"])
        self.assertEqual("targeted_source_read", result["fallback"])

    def test_trace_is_bounded(self) -> None:
        args = _args("trace", "RenderPipeline")
        command, expect_json = ix_adapter.build_operation_args(args)

        self.assertTrue(expect_json)
        self.assertEqual("trace", command[0])
        self.assertIn("--depth", command)
        self.assertIn("3", command)
        self.assertIn("--cap", command)
        self.assertIn("100", command)
        self.assertNotIn("reset", command)

    def test_target_cannot_be_option_injection(self) -> None:
        args = _args("impact", "--reset")
        with self.assertRaises(ValueError):
            ix_adapter.build_operation_args(args)

    def test_subprocess_never_uses_shell(self) -> None:
        with (
            patch("ix_adapter.shutil.which", return_value="/usr/local/bin/ix"),
            patch("ix_adapter.subprocess.run", return_value=_Completed()) as run,
        ):
            result = ix_adapter.execute(_args("impact", "Foo"))

        self.assertEqual("ok", result["status"])
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_non_json_query_output_is_error(self) -> None:
        with (
            patch("ix_adapter.shutil.which", return_value="/usr/local/bin/ix"),
            patch("ix_adapter.subprocess.run", return_value=_Completed(stdout="not-json")),
        ):
            result = ix_adapter.execute(_args("explain", "Foo"))

        self.assertEqual("error", result["status"])
        self.assertEqual("ix_non_json_output", result["diagnostics"][0]["code"])

    def test_low_confidence_is_preserved_as_diagnostic(self) -> None:
        payload = '{"entity":{"name":"Foo","confidence":0.2}}'
        with (
            patch("ix_adapter.shutil.which", return_value="/usr/local/bin/ix"),
            patch("ix_adapter.subprocess.run", return_value=_Completed(stdout=payload)),
        ):
            result = ix_adapter.execute(_args("impact", "Foo"))

        self.assertEqual("ok", result["status"])
        self.assertTrue(result["low_confidence"])
        self.assertAlmostEqual(0.2, result["confidence_min"])


if __name__ == "__main__":
    unittest.main()
