import sys
from abc import ABC
from dataclasses import dataclass


@dataclass
class AbstractProgressError(ABC):
    error_msg: str
    explanation: str
    suggestion: str

    def __post_init__(self):
        raise RuntimeError("Cannot instantiate ProgressError")

    @classmethod
    def print(cls, file=sys.stdout):
        file.flush()
        file.write("\n")
        file.write("  " + cls.error_msg.replace("Error", "\x1b[1;31mError\x1b[0m") + ".\n")
        file.write("  " + f"\x1b[4m{cls.explanation}\x1b[0m" + ".\n")
        file.write("  " + cls.suggestion + ".\n")
        file.write("\n")
        file.flush()
