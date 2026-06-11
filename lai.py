#!/usr/bin/env python3
"""lai - the local AI programming environment.

Thin entry point; the implementation lives in laicore/ (core, stack, work,
projects, webui, cli). Run `python lai.py --help` or see the README.
"""
from laicore.cli import main

if __name__ == "__main__":
    main()
