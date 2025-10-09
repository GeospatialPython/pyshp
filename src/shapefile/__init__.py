"""
shapefile.py
Provides read and write support for ESRI Shapefiles.
authors: jlawhead<at>geospatialpython.com
maintainer: karim.bahgat.norway<at>gmail.com
Compatible with Python versions >=3.9
"""

from __future__ import annotations

__all__ = [
    "__version__"

]

from .__version__ import __version__
from ._doctest_runner import _test

import logging
import sys
# import io
# import os
# import tempfile
# import time
# import zipfile
# from collections.abc import Container, Iterable, Iterator, Reversible, Sequence
# from datetime import date
# from os import PathLike
# from struct import Struct, calcsize, error, pack, unpack
# from types import TracebackType
# from typing import (
#     IO,
#     Any,
#     Final,
#     Generic,
#     Literal,
#     NamedTuple,
#     NoReturn,
#     Optional,
#     Protocol,
#     SupportsIndex,
#     TypedDict,
#     TypeVar,
#     Union,
#     cast,
#     overload,
# )

# Create named logger
logger = logging.getLogger(__name__)













def main() -> None:
    """
    Doctests are contained in the file 'README.md', and are tested using the built-in
    testing libraries.
    """
    failure_count = _test()
    sys.exit(failure_count)


if __name__ == "__main__":
    main()
