import logging

from bureauTasks import CopyTask, FormTask, ImageToPdfTask, PdfMergeTask, SkipTask


log = logging.getLogger(__name__)

class BureauExecutor(object):
    __LOG_PREFIX = "BureauExecutor:"
    _TASK_TYPES = {
        "form": FormTask,
        "copy": CopyTask,
        "image_to_pdf": ImageToPdfTask,
        "pdf_merge": PdfMergeTask,
        "skip": SkipTask,
    }

    def __init__(self, environment, manifest):
        self.environment = environment
        self.manifest = manifest

    def execute(self):
        config = self.environment.config
        command = config.command
        dry_run = config.dry_run

        log.info("%s Start executing %s command for %s", self.__LOG_PREFIX, command, self.manifest.path)

        if self.manifest.header:
            for line in self.manifest.header.rstrip().splitlines():
                log.info("%s %s", self.__LOG_PREFIX, line)

        return_code = 0
        context = self.manifest.context
        output = self.manifest.path.parent / str(context["target_date"])

        for definition in self.manifest.tasks:
            task_type = definition["type"]
            task_class = self._TASK_TYPES.get(task_type)
            if task_class is None:
                raise ValueError(f"Unsupported task type: {task_type}")

            task = task_class(
                self.environment,
                definition,
                command,
                dry_run,
                output,
            )
            log.debug(
                "%s created task %s %s for command %s (dry_run=%s)",
                self.__LOG_PREFIX,
                task.number,
                task_class.__name__,
                command,
                dry_run,
            )

            if task.execute():
                return_code = 1

        if self.manifest.footer:
            for line in self.manifest.footer.rstrip().splitlines():
                log.info("%s %s", self.__LOG_PREFIX, line)


        return return_code