"""
shapefile.py
Provides read and write support for ESRI Shapefiles.
authors: jlawhead<at>geospatialpython.com
maintainer: karim.bahgat.norway<at>gmail.com
Compatible with Python versions >=3.9
"""

from __future__ import annotations

import logging
import sys

from .__version__ import __version__
from ._doctest_runner import _test
from .classes import Field, ShapeRecord, ShapeRecords, Shapes
from .constants import (
    MULTIPATCH,
    MULTIPOINT,
    MULTIPOINTM,
    MULTIPOINTZ,
    NULL,
    POINT,
    POINTM,
    POINTZ,
    POLYGON,
    POLYGONM,
    POLYGONZ,
    POLYLINE,
    POLYLINEM,
    POLYLINEZ,
    REPLACE_REMOTE_URLS_WITH_LOCALHOST,
    SHAPETYPE_LOOKUP,
)
from .exceptions import GeoJSON_Error, RingSamplingError, ShapefileException
from .geometric_calculations import bbox_overlap
from .helpers import _Array, fsdecode_if_pathlike
from .reader import Reader
from .shapes import (
    SHAPE_CLASS_FROM_SHAPETYPE,
    MultiPatch,
    MultiPoint,
    MultiPointM,
    MultiPointZ,
    NullShape,
    Point,
    PointM,
    PointM_shapeTypes,
    PointZ,
    PointZ_shapeTypes,
    Polygon,
    PolygonM,
    PolygonZ,
    Polyline,
    PolylineM,
    PolylineZ,
    Shape,
    _CanHaveBBox_shapeTypes,
    _HasM,
    _HasM_shapeTypes,
    _HasZ,
    _HasZ_shapeTypes,
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
from .writer import Writer

__all__ = [
    "__version__",
    "NULL",
    "POINT",
    "POLYLINE",
    "POLYGON",
    "MULTIPOINT",
    "POINTZ",
    "POLYLINEZ",
    "POLYGONZ",
    "MULTIPOINTZ",
    "POINTM",
    "POLYLINEM",
    "POLYGONM",
    "MULTIPOINTM",
    "MULTIPATCH",
    "SHAPETYPE_LOOKUP",
    "REPLACE_REMOTE_URLS_WITH_LOCALHOST",
    "Reader",
    "Writer",
    "fsdecode_if_pathlike",
    "_Array",
    "Shape",
    "NullShape",
    "Point",
    "Polyline",
    "Polygon",
    "MultiPoint",
    "MultiPointM",
    "MultiPointZ",
    "PolygonM",
    "PolygonZ",
    "PolylineM",
    "PolylineZ",
    "MultiPatch",
    "PointM",
    "PointZ",
    "SHAPE_CLASS_FROM_SHAPETYPE",
    "PointM_shapeTypes",
    "PointZ_shapeTypes",
    "_CanHaveBBox_shapeTypes",
    "_HasM",
    "_HasM_shapeTypes",
    "_HasZ",
    "_HasZ_shapeTypes",
    "Point2D",
    "Point3D",
    "PointMT",
    "PointZT",
    "Coord",
    "Coords",
    "PointT",
    "PointsT",
    "BBox",
    "MBox",
    "ZBox",
    "WriteableBinStream",
    "ReadableBinStream",
    "WriteSeekableBinStream",
    "ReadSeekableBinStream",
    "ReadWriteSeekableBinStream",
    "BinaryFileT",
    "BinaryFileStreamT",
    "FieldTypeT",
    "FieldType",
    "FIELD_TYPE_ALIASES",
    "RecordValueNotDate",
    "RecordValue",
    "ShapefileException",
    "RingSamplingError",
    "GeoJSON_Error",
    "Field",
    "Shapes",
    "ShapeRecord",
    "ShapeRecords",
    "bbox_overlap",
]

logger = logging.getLogger(__name__)


def main() -> None:
    """
    Doctests are contained in the file 'README.md', and are tested using the built-in
    testing libraries.
    """
    failure_count = _test()
    sys.exit(failure_count)
