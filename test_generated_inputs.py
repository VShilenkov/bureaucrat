import logging
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from bureauExecutor import BureauExecutor


class GeneratedInputsTests(unittest.TestCase):
    def _execute_check(self, root, tasks):
        manifest = SimpleNamespace(
            path=root / "manifest.yaml",
            context={"target_date": "20261016"},
            tasks=tasks,
            header="",
            footer="",
        )
        environment = SimpleNamespace(
            config=SimpleNamespace(command="check", dry_run=False),
            root=root,
        )
        return BureauExecutor(environment, manifest).execute()

    def test_prior_copy_output_is_not_reported_missing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "input.pdf"
            source.write_bytes(b"source")
            tasks = [
                {
                    "type": "copy",
                    "number": "01",
                    "path": str(source),
                },
                {
                    "type": "pdf_merge",
                    "number": "02",
                    "inputs": ["input.pdf", "absent.pdf"],
                    "output": "merged.pdf",
                },
            ]

            with self.assertLogs("bureauTasks", level=logging.INFO) as captured:
                result = self._execute_check(root, tasks)

        output = "\n".join(captured.output)
        self.assertEqual(result, 0)
        self.assertIn(
            f"[OK-GENERATED] {Path('20261016') / 'input.pdf'} (task 01)",
            output,
        )
        self.assertIn(
            f"[MISSING] merge inputs: {Path('20261016') / 'absent.pdf'}",
            output,
        )

    def test_later_task_does_not_satisfy_an_earlier_input(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "input.pdf"
            source.write_bytes(b"source")
            tasks = [
                {
                    "type": "pdf_merge",
                    "number": "01",
                    "inputs": ["input.pdf"],
                    "output": "merged.pdf",
                },
                {
                    "type": "copy",
                    "number": "02",
                    "path": str(source),
                },
            ]

            with self.assertLogs("bureauTasks", level=logging.INFO) as captured:
                result = self._execute_check(root, tasks)

        output = "\n".join(captured.output)
        self.assertEqual(result, 0)
        self.assertIn(
            f"[MISSING] merge inputs: {Path('20261016') / 'input.pdf'}",
            output,
        )
        self.assertNotIn("[OK-GENERATED]", output)

    def test_generated_file_can_match_form_pattern(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "filled.pdf"
            source.write_bytes(b"source")
            tasks = [
                {
                    "type": "copy",
                    "number": "01",
                    "path": str(source),
                },
                {
                    "type": "form",
                    "number": "02",
                    "filled_pattern": "filled*.pdf",
                    "optional": True,
                },
            ]

            with self.assertLogs("bureauTasks", level=logging.INFO) as captured:
                result = self._execute_check(root, tasks)

        output = "\n".join(captured.output)
        self.assertEqual(result, 0)
        self.assertIn(
            f"[OK-GENERATED] filled form {Path('20261016') / 'filled.pdf'} (task 01)",
            output,
        )
        self.assertNotIn("[OPTIONAL] filled form not found", output)

    def test_missing_upstream_input_does_not_generate_a_downstream_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            tasks = [
                {
                    "type": "copy",
                    "number": "01",
                    "path": str(root / "absent.pdf"),
                },
                {
                    "type": "pdf_merge",
                    "number": "02",
                    "inputs": ["absent.pdf"],
                    "output": "merged.pdf",
                },
            ]

            with self.assertLogs("bureauTasks", level=logging.INFO) as captured:
                result = self._execute_check(root, tasks)

        output = "\n".join(captured.output)
        self.assertEqual(result, 0)
        self.assertNotIn("[OK-GENERATED]", output)
        self.assertIn("[MISSING]", output)


if __name__ == "__main__":
    unittest.main()
