import re
from pathlib import Path

import yaml


_VARIABLE_EXPRESSION = re.compile(
    r"[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*"
)


def resolve(value, variables):
    if not isinstance(value, str):
        return value

    # Resolve nested references recursively and track the chain to report cycles.
    def resolve_expression(expression, references):
        if _VARIABLE_EXPRESSION.fullmatch(expression) is None:
            raise ValueError(f"Invalid variable expression: {{{expression}}}")

        name = expression
        if name in references:
            raise ValueError(f"Circular variable reference: {{{name}}}")

        result = variables
        for part in name.split("."):
            if not isinstance(result, dict) or part not in result:
                raise ValueError(f"Unknown variable: {{{name}}}")
            result = result[part]

        if isinstance(result, str):
            result = resolve_string(result, references | {name})

        return str(result)

    def resolve_string(text, references=frozenset()):
        return re.sub(
            r"\{([^{}]+)\}",
            lambda match: resolve_expression(match.group(1), references),
            text,
        )

    return resolve_string(value)


class BureauManifest(object):
    __LOG_PREFIX = "BureauManifest:"

    def __init__(self, path, environment):
        self.path = Path(path)

        with self.path.open(encoding="utf-8") as stream:
            self.data = yaml.safe_load(stream)

        if not isinstance(self.data, dict):
            raise ValueError("Manifest must contain a YAML mapping")

        manifest_environment = self._mapping("environment")
        self.environment = {
            **manifest_environment,
            "root": str(environment.root),
            "source": str(environment.source),
            "formulars": str(environment.formulars),
        }
        self.context = self._mapping("context")
        variables = {
            "context": self.context,
            "environment": self.environment,
        }

        # Application-provided environment paths take precedence over manifest values.
        self.data["environment"] = self.environment
        self.data = self._normalize(self.data, variables)
        self.environment = self.data["environment"]
        self.instructions = self.data.get("instructions", "")
        self.header = self.data.get("header", "")
        self.footer = self.data.get("footer", "")
        self.context = self.data["context"]
        self.tasks = self._tasks()

    def _mapping(self, name):
        value = self.data.get(name, {})
        if not isinstance(value, dict):
            raise ValueError(f"Manifest field '{name}' must be a mapping")
        return value

    def _list(self, name):
        value = self.data.get(name, [])
        if not isinstance(value, list):
            raise ValueError(f"Manifest field '{name}' must be a list")
        if not all(isinstance(item, dict) for item in value):
            raise ValueError(f"Items in manifest field '{name}' must be mappings")
        return value

    def _normalize(
        self,
        value,
        variables,
        task_definition=False,
        task_index=None,
    ):
        if isinstance(value, dict):
            if task_definition:
                # Task-local substitutions can use generated task.number and task fields.
                value = {**value, "number": f"{task_index:02d}"}
                variables = {**variables, "task": value}
            return {
                key: self._normalize(
                    item,
                    variables,
                    key in {"tasks", "forms", "copy"},
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            if task_definition:
                return [
                    self._normalize(item, variables, True, index)
                    for index, item in enumerate(value, start=1)
                ]
            return [
                self._normalize(item, variables)
                for item in value
            ]
        return resolve(value, variables)

    def _tasks(self):
        if "tasks" in self.data:
            tasks = self._list("tasks")
        else:
            # Accept the earlier split form/copy sections as shorthand for tasks.
            tasks = [{"type": "form", **item} for item in self._list("forms") 
                ] + [{"type": "copy", **item} for item in self._list("copy") ]

        required_fields = {
            "form": "filled_pattern",
            "copy": None,
            "image_to_pdf": None,
            "pdf_merge": "inputs",
            "skip": None,
        }
        for index, task in enumerate(tasks, start=1):
            task_type = task.get("type")
            if task_type not in required_fields:
                raise ValueError(
                    f"Task {index} has unsupported type: {task_type}"
                )
            if task_type in {"copy", "image_to_pdf"}:
                has_path = "path" in task
                has_paths = "paths" in task
                if has_path == has_paths:
                    raise ValueError(
                        f"Task {index} ({task_type}) requires exactly one of 'path' or 'paths'"
                    )
                if has_path and not isinstance(task["path"], str):
                    raise ValueError(
                        f"Task {index} ({task_type}) field 'path' must be a string"
                    )
                if has_paths and (
                    not isinstance(task["paths"], list)
                    or not task["paths"]
                    or not all(isinstance(path, str) for path in task["paths"])
                ):
                    raise ValueError(
                        f"Task {index} ({task_type}) field 'paths' must be a non-empty list of strings"
                    )
                continue

            required_field = required_fields[task_type]
            if required_field and required_field not in task:
                raise ValueError(
                    f"Task {index} ({task_type}) requires '{required_field}'"
                )

        return tasks

    def dump(self):
        return yaml.safe_dump(
            self.data,
            allow_unicode=True,
            sort_keys=False,
        )

    def __str__(self):
        return (
            "%s\n"
            "   %-16s = %s\n"
            "   %-16s = %s\n"
            "   %-16s = %s" % (
                self.__LOG_PREFIX,
                "path", self.path,
                "context", self.context,
                "tasks", [task["type"] for task in self.tasks],
            )
        )