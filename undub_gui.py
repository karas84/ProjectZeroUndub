#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))


from zeroundub.gui.tkgui import main  # pylint: disable=wrong-import-position  # noqa: E402


if __name__ == "__main__":
    main()
