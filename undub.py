#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from zeroundub.cli.cmdline.undub import main


if __name__ == '__main__':
    main()
