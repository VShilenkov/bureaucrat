
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bureauConfig import Config
from bureauEnvironment import Environment
from bureauExecutor import BureauExecutor
from bureauManifest import BureauManifest

log = logging.getLogger(__name__)

def parse_options():
    parser = argparse.ArgumentParser(description="Validate and assemble a document package")
    parser.add_argument("-m", "--manifest", type=Path, default=Path("manifest.yaml"), help="Path to manifest file",)
    parser.add_argument("-c",  "--command", type=str,  default="check",               help="What to do",  choices=["check", "build", "clean"],)
    parser.add_argument(         "--debug", action="store_true",                      help="More verbose output",)
    parser.add_argument(       "--dry-run", action="store_true", dest="dry_run",      help="Do not perform write operations",)

    return parser.parse_args()


def main():
    def _instantiate(cls, *args):
        try:
            obj = cls(*args)
        except Exception as e:
            log.error(str(e))
            sys.exit(1)

        log.debug(str(obj))
        return obj

    config   = _instantiate(Config, parse_options())
    env      = _instantiate(Environment, config)
    manifest = _instantiate(BureauManifest, config.manifest, env)
    executor = _instantiate(BureauExecutor, env, manifest)

    return executor.execute()


if __name__ == "__main__":
    sys.exit(main())