import os
import sys
import tqdm

from typing import Type

from .error import AbstractProgressError


# noinspection PyBroadException
def remove_ctrl_c_echo():
    try:
        if "linux" in sys.platform and sys.stdout.isatty():
            os.system("stty -echoctl")
    except Exception:
        pass


class Progress:
    def __init__(self, desc: str, error: Type[AbstractProgressError], tpad=20, ncols=50):
        self.error = error
        self.pbar = tqdm.tqdm(
            bar_format=f"{{desc}}: {{percentage:3.0f}}% ┤{{bar:{ncols}}}├ {{n_fmt}}/{{total_fmt}}{{bar:-{ncols}b}}",
            desc=f"  \x1b[93m{desc:{tpad}s}\x1b[0m",
            smoothing=1,
            colour="blue",
            file=sys.stdout,
        )

    def __enter__(self):
        remove_ctrl_c_echo()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if exc_type is not None or self.pbar.n < self.pbar.total:
            self.pbar.colour = "red"
            self.pbar.refresh()
            self.pbar.close()

            self.error.print()
            sys.exit(1)

        if self.pbar.n > self.pbar.total:
            self.pbar.n = self.pbar.total

        self.pbar.colour = "green"
        self.pbar.refresh()
        self.pbar.close()

    def __call__(self, total=None):
        if total:
            self.pbar.total = total
            self.pbar.n = 0
        else:
            self.pbar.update(1)

        self.pbar.refresh()
