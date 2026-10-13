import pathlib
import sys

class Environment(object):
    __LOG_PREFIX="Environment:"

    def __init__(self, config):
        if getattr(sys, "frozen", False):
            self.root = pathlib.Path(sys.executable).parent
        else:
            self.root = pathlib.Path(__file__).parent
        self.source = pathlib.Path.cwd()
        self.config = config
        self.formulars = self.root / "Formulars"
        if not self.formulars.is_dir():
            raise FileNotFoundError(
                f"Formulars directory not found: {self.formulars}"
            )

    def __str__(self):
        return (
            "%s\n"
            "   %-16s = %s\n"
            "   %-16s = %s\n"
            "   %-16s = %s\n" % (
                self.__LOG_PREFIX,
                'root', self.root,
                'source', self.source,
                'formulars', self.formulars,
            )
        )