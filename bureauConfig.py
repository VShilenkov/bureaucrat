import logging
import sys

class Config(object):
    __LOG_PREFIX='Config:'

    def __init__(self, options):
        self.debug = bool(getattr(options, 'debug', False))
        self.manifest = options.manifest.absolute()
        self.command = options.command
        self.dry_run = bool(getattr(options, 'dry_run', False))
        if not self.manifest.is_file():
            raise FileNotFoundError(f"ERROR: Manifest file not found: {options.manifest}")


        self._configure_logger()

    def _configure_logger(self):
        logging.basicConfig(
            level   = logging.DEBUG if self.debug else logging.INFO,
            format  = '%(asctime)s %(levelname)-8s %(filename)s:%(lineno)d %(funcName)s %(message)s' if self.debug else '%(message)s',
            datefmt = '%Y%m%d%H%M%S',
            stream  = sys.stdout
        )

    def __str__(self):
        return (
            "%s\n"
            "   %-16s = %s\n"
            "   %-16s = %s\n"
            "   %-16s = %s\n"
            "   %-16s = %s\n" % (
                self.__LOG_PREFIX,
                'debug', self.debug,
                'manifest', self.manifest,
                'command', self.command,
                'dry_run', self.dry_run,
            )
        )