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

import logging
import sys

from .__version__ import __version__
from ._doctest_runner import _test


logger = logging.getLogger(__name__)

from .helpers import _Array, fsdecode_if_pathlike
from .reader import Reader
from .shapes import (
    NullShape,
    Point,
    Polygon,
    # ...add other shape classes as needed
    Polyline,
    Shape,
)
from .types import (
    FIELD_TYPE_ALIASES,
    BBox,
    BinaryFileStreamT,
    BinaryFileT,
    Coord,
    Coords,
    FieldType,
    FieldTypeT,
    MBox,
    Point2D,
    Point3D,
    PointMT,
    PointsT,
    PointT,
    PointZT,
    ReadableBinStream,
    ReadSeekableBinStream,
    ReadWriteSeekableBinStream,
    RecordValue,
    RecordValueNotDate,
    WriteableBinStream,
    WriteSeekableBinStream,
    ZBox,
)


def main() -> None:
    """
    Doctests are contained in the file 'README.md', and are tested using the built-in
    testing libraries.
    """
    failure_count = _test()
    sys.exit(failure_count)


if __name__ == "__main__":
    main()
