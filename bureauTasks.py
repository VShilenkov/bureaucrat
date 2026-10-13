import logging
import re
import shutil
from pathlib import Path


log = logging.getLogger(__name__)


class BureauTask(object):
    LOG_PREFIX = "BureauTask:"
    DRY_RUN_COMMANDS = frozenset()
    COMMANDS = frozenset({"check", "build", "clean"})

    def __init__(self, environment, definition, command, dry_run, output):
        self.environment = environment
        self.definition = definition
        self.number = definition.get("number", "??")
        self.command = command
        self.dry_run = dry_run and command in self.DRY_RUN_COMMANDS
        self.output = output

    def _log(self, level, message, *args):
        marker = " [DRY-RUN]" if self.dry_run else ""
        log.log(level, "%s " + message, f"{self.LOG_PREFIX} {self.number}.{marker}", *args)

    def info(self, message, *args):
        self._log(logging.INFO, message, *args)

    def warning(self, message, *args):
        self._log(logging.WARNING, message, *args)

    def error(self, message, *args):
        self._log(logging.ERROR, message, *args)

    def _display_path(self, value):
        path = Path(value)
        root = Path(self.environment.root).resolve()
        try:
            return str(path.resolve().relative_to(root))
        except (OSError, RuntimeError, ValueError):
            return str(path)

    def _display_message(self, value):
        message = str(value)
        for task_value in self.definition.values():
            if not isinstance(task_value, str):
                continue
            path = Path(task_value)
            if path.is_absolute():
                message = message.replace(task_value, self._display_path(path))

        roots = {
            str(self.environment.root),
            str(Path(self.environment.root).resolve()),
        }
        for root in roots:
            root = root.rstrip("\\/")
            if message.casefold() == root.casefold():
                return "."
            message = re.sub(
                re.escape(root) + r"[\\/]+",
                "",
                message,
                flags=re.IGNORECASE,
            )
        return message

    def _input_paths(self):
        values = self.definition.get("paths", self.definition.get("path"))
        if isinstance(values, (str, Path)):
            values = [values]
        if not isinstance(values, list) or not values:
            raise ValueError("Task requires a non-empty path or paths field")
        if not all(isinstance(value, (str, Path)) for value in values):
            raise ValueError("Task paths must contain only path strings")
        return [Path(value) for value in values]

    def _check_destinations(self, destinations):
        normalized = [str(path.resolve()).casefold() for path in destinations]
        if len(normalized) != len(set(normalized)):
            self.error("multiple inputs map to the same output filename")
            return False

        existing = [path for path in destinations if path.exists()]
        if existing:
            self.error("output file already exists; refusing to overwrite: %s", ", ".join(self._display_path(path) for path in existing))
            return False
        return True

    def _rollback_files(self, paths):
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError as error:
                self.error("could not roll back %s: %s", self._display_path(path),
                    self._display_message(error),
                )

    def _clean_file(self, destination):
        if not destination.exists() and not destination.is_symlink():
            self.info("[CLEAN] already absent: %s", self._display_path(destination),
            )
            return 0

        if destination.is_dir() and not destination.is_symlink():
            self.error("refusing to remove directory: %s", self._display_path(destination),
            )
            return 1

        if self.dry_run:
            self.info("[CLEAN] %s", self._display_path(destination),
            )
            return 0

        try:
            destination.unlink()
        except OSError as error:
            self.error("could not remove %s: %s", self._display_path(destination),
                self._display_message(error),
            )
            return 1

        self.info("[CLEAN] removed %s", self._display_path(destination),
        )
        return 0

    def execute(self) -> int:
        if self.command not in self.COMMANDS:
            raise ValueError(f"Unsupported command: {self.command}")
        operation = getattr(self, self.command, None)
        if operation is None:
            raise NotImplementedError(
                f"{type(self).__name__} does not implement {self.command}"
            )
        return operation()


class FormTask(BureauTask):
    LOG_PREFIX = "FormTask:"

    def clean(self) -> int:
        self.info("[KEEP] filled forms are existing inputs")
        return 0

    def _find_filled_form(self, root=None, exclude_output=False):
        filename = self.definition["filled_pattern"]
        search_root = root or self.environment.root
        output = self.output.resolve()
        matches = [
            path for path in search_root.rglob(filename)
            if path.is_file()
            and (not exclude_output or output not in path.resolve().parents)
        ]

        if len(matches) == 1:
            return matches[0], None, False
        if not matches:
            return (
                None,
                self.definition.get("on_missing", f"Missing form: {filename}"),
                True,
            )
        return (
            None,
            f"Ambiguous form {filename}: "
            + ", ".join(self._display_path(path) for path in matches),
            False,
        )

    def check(self) -> int:
        optional = bool(self.definition.get("optional", False))
        template = self.definition.get("source")
        if template:
            template_path = Path(template)
            if template_path.is_file():
                self.info("[OK] form template %s", self._display_path(template_path))
            elif optional:
                self.info("[OPTIONAL] form template not found: %s", self._display_path(template_path))
            else:
                self.warning("[MISSING] form template %s", self._display_path(template_path),
                )
        elif optional:
            self.info("[OPTIONAL] form template source is not configured")
        else:
            self.warning("[MISSING] form template source is not configured")

        try:
            source, error, missing = self._find_filled_form(self.output)
        except OSError as error:
            self.error(
                "could not inspect result folder %s: %s",
                self._display_path(self.output),
                self._display_message(error),
            )
            return 0

        if source is None:
            if missing and optional:
                self.info("[OPTIONAL] filled form not found in %s", self._display_path(self.output))
            elif missing:
                self.warning("[MISSING] filled form in %s: %s", self._display_path(self.output), self._display_message(error))
            else:
                self.warning("[AMBIGUOUS] filled form in %s: %s", self._display_path(self.output), self._display_message(error))
        else:
            self.info("[OK] filled form %s", self._display_path(source))

        return 0

    def build(self) -> int:
        optional = bool(self.definition.get("optional", False))
        try:
            source, error, missing = self._find_filled_form(self.output)
        except OSError as error:
            self.error("could not inspect result folder %s: %s", self._display_path(self.output), self._display_message(error))
            return 1

        if source is not None:
            self.info("[OK] filled form %s", self._display_path(source))
            return 0

        if missing and optional:
            self.info("[OPTIONAL] filled form not found in %s", self._display_path(self.output))
            return 0

        if source is None:
            if missing:
                self.error("[MISSING] filled form in %s: %s", self._display_path(self.output),self._display_message(error))
            else:
                self.error("[AMBIGUOUS] filled form in %s: %s", self._display_path(self.output),self._display_message(error))
        return 1


class CopyTask(BureauTask):
    LOG_PREFIX = "CopyTask:"
    DRY_RUN_COMMANDS = frozenset({"build", "clean"})

    def check(self) -> int:
        for source in self._input_paths():
            if source.is_file():
                self.info("[OK] %s", self._display_path(source))
            else:
                message = self.definition.get("on_missing", f"Missing file: {self._display_path(source)}")
                self.warning("[MISSING] %s", self._display_message(message))
        return 0

    def build(self) -> int:
        sources = self._input_paths()
        missing = [source for source in sources if not source.is_file()]
        if missing:
            message = self.definition.get("on_missing") or (
                "Missing files: "
                + ", ".join(self._display_path(source) for source in missing)
            )
            if self.definition.get("optional", False):
                self.info("[OPTIONAL] %s", self._display_message(message))
                return 0
            self.error("[MISSING] %s", self._display_message(message))
            return 1

        destinations = [self.output / source.name for source in sources]
        if not self._check_destinations(destinations):
            return 1

        if self.dry_run:
            for source, destination in zip(sources, destinations):
                self.info("%s -> %s", self._display_path(source), self._display_path(destination))
            return 0

        attempted = []
        try:
            self.output.mkdir(parents=True, exist_ok=True)
            for source, destination in zip(sources, destinations):
                attempted.append(destination)
                shutil.copy2(source, destination)
        except OSError as error:
            self._rollback_files(attempted)
            self.error("could not copy files: %s", self._display_message(error))
            return 1

        for destination in destinations:
            self.info("[COPY] %s", self._display_path(destination))
        return 0

    def clean(self) -> int:
        return_code = 0
        for source in self._input_paths():
            if self._clean_file(self.output / source.name):
                return_code = 1
        return return_code


class ImageToPdfTask(BureauTask):
    LOG_PREFIX = "PDFCTask:"
    DRY_RUN_COMMANDS = frozenset({"build", "clean"})

    def check(self) -> int:
        for source in self._input_paths():
            if source.is_file():
                self.info("[OK] %s", self._display_path(source))
            else:
                message = self.definition.get("on_missing", f"Missing image: {self._display_path(source)}")
                self.warning("[MISSING] %s", self._display_message(message))
        return 0

    def build(self) -> int:
        sources = self._input_paths()
        missing = [source for source in sources if not source.is_file()]
        if missing:
            message = self.definition.get("on_missing") or (
                "Missing images: "
                + ", ".join(self._display_path(source) for source in missing)
            )
            if self.definition.get("optional", False):
                self.info("[OPTIONAL] %s", self._display_message(message))
                return 0
            self.error("[MISSING] %s", self._display_message(message))
            return 1

        destinations = [self.output / f"{source.stem}.pdf" for source in sources]
        if not self._check_destinations(destinations):
            return 1

        if self.dry_run:
            for source, destination in zip(sources, destinations):
                self.info("%s -> %s", self._display_path(source), self._display_path(destination))
            return 0

        attempted = []
        try:
            from PIL import Image, ImageOps

            self.output.mkdir(parents=True, exist_ok=True)
            for source, destination in zip(sources, destinations):
                attempted.append(destination)
                with Image.open(source) as image:
                    oriented = ImageOps.exif_transpose(image)
                    if "A" in oriented.getbands() or "transparency" in oriented.info:
                        rgba = oriented.convert("RGBA")
                        converted = Image.new("RGB", rgba.size, "white")
                        converted.paste(rgba, mask=rgba.getchannel("A"))
                        rgba.close()
                    else:
                        converted = oriented.convert("RGB")
                    try:
                        converted.save(destination, "PDF", resolution=300.0)
                    finally:
                        converted.close()
        except (OSError, ValueError) as error:
            self._rollback_files(attempted)
            self.error("could not convert image batch: %s", self._display_message(error))
            return 1

        for destination in destinations:
            self.info("[PDF] %s", self._display_path(destination))
        return 0

    def clean(self) -> int:
        return_code = 0
        for source in self._input_paths():
            if self._clean_file(self.output / f"{source.stem}.pdf"):
                return_code = 1
        return return_code


class PdfMergeTask(BureauTask):
    LOG_PREFIX = "PDFMTask:"
    DRY_RUN_COMMANDS = frozenset({"build", "clean"})

    def _inputs(self):
        return [
            Path(value) if Path(value).is_absolute() else self.output / value
            for value in self.definition["inputs"]
        ]

    def _destination(self):
        output_name = Path(self.definition["output"])
        destination = (
            output_name
            if output_name.is_absolute()
            else self.output / output_name
        )
        if destination.resolve().parent != self.output.resolve():
            raise ValueError("PDF merge output must be a file inside the result folder")
        return destination

    def check(self) -> int:
        missing = [path for path in self._inputs() if not path.is_file()]
        if missing:
            self.warning("[MISSING] merge inputs: %s", ", ".join(self._display_path(path) for path in missing))
        else:
            self.info("[OK] %s PDF inputs", len(self.definition["inputs"]))
        return 0

    def build(self) -> int:
        inputs = self._inputs()
        missing = [path for path in inputs if not path.is_file()]
        if missing:
            self.error("[MISSING] merge inputs: %s", ", ".join(self._display_path(path) for path in missing))
            return 1

        if any(path.suffix.lower() != ".pdf" for path in inputs):
            self.error("all merge inputs must be PDFs")
            return 1

        destination = self._destination()
        if destination.exists():
            self.error("refusing to overwrite existing PDF: %s", self._display_path(destination))
            return 1

        if self.dry_run:
            self.info("merge %s -> %s", ", ".join(self._display_path(path) for path in inputs), self._display_path(destination))
            return 0

        try:
            import fitz

            self.output.mkdir(parents=True, exist_ok=True)
            merged = fitz.open()
            try:
                for source in inputs:
                    with fitz.open(source) as document:
                        merged.insert_pdf(document)
                if merged.page_count == 0:
                    self.error("no pages to merge")
                    return 1
                merged.save(destination)
            finally:
                merged.close()
        except Exception as error:
            self.error(
                "could not merge PDFs into %s: %s",
                self._display_path(destination),
                self._display_message(error),
            )
            return 1

        self.info("[MERGED] %s PDFs -> %s", len(inputs), self._display_path(destination))
        return 0

    def clean(self) -> int:
        return self._clean_file(self._destination())


class SkipTask(BureauTask):
    LOG_PREFIX = "SkipTask:"

    def execute(self) -> int:
        name = self.definition.get("name", "")
        self.info("[SKIP] %s", name)
        return 0