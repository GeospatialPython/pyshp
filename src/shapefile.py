"""
shapefile.py
Provides read and write support for ESRI Shapefiles.
authors: jlawhead<at>geospatialpython.com
maintainers: james<at>jamesparrott.dev and karim.bahgat.norway<at>gmail.com
Compatible with Python versions >=3.9
"""

from __future__ import annotations

__version__ = "3.0.9"

import abc
import array
import doctest
import functools
import io
import itertools
import logging
import os
import re
import sys
import tempfile
import time
import warnings
import zipfile
from collections.abc import Container, Iterable, Iterator, Reversible, Sequence
from contextlib import AbstractContextManager, ExitStack
from datetime import date
from os import PathLike
from pathlib import Path
from struct import Struct, calcsize, error, pack, unpack
from types import TracebackType
from typing import (
    IO,
    Any,
    Final,
    Generic,
    Literal,
    NamedTuple,
    Optional,
    Protocol,
    SupportsIndex,
    TypedDict,
    TypeVar,
    Union,
    cast,
    overload,
    runtime_checkable,
)
from urllib.error import HTTPError
from urllib.parse import SplitResult, urlsplit, urlunsplit
from urllib.request import Request, urlopen

# Preserve error in namespace in case a user imported it from PyShp
StructError = error

# Create named logger
logger = logging.getLogger(__name__)

# Module settings
VERBOSE = True

# Test config (for the Doctest runner and test_shapefile.py)
REPLACE_REMOTE_URLS_WITH_LOCALHOST = (
    os.getenv("REPLACE_REMOTE_URLS_WITH_LOCALHOST", "").lower() == "true"
)

IS_WINDOWS = sys.platform == "win32"

# Constants for shape types
NULL = 0
POINT = 1
POLYLINE = 3
POLYGON = 5
MULTIPOINT = 8
POINTZ = 11
POLYLINEZ = 13
POLYGONZ = 15
MULTIPOINTZ = 18
POINTM = 21
POLYLINEM = 23
POLYGONM = 25
MULTIPOINTM = 28
MULTIPATCH = 31

SHAPETYPE_LOOKUP = {
    NULL: "NULL",
    POINT: "POINT",
    POLYLINE: "POLYLINE",
    POLYGON: "POLYGON",
    MULTIPOINT: "MULTIPOINT",
    POINTZ: "POINTZ",
    POLYLINEZ: "POLYLINEZ",
    POLYGONZ: "POLYGONZ",
    MULTIPOINTZ: "MULTIPOINTZ",
    POINTM: "POINTM",
    POLYLINEM: "POLYLINEM",
    POLYGONM: "POLYGONM",
    MULTIPOINTM: "MULTIPOINTM",
    MULTIPATCH: "MULTIPATCH",
}

SHAPETYPENUM_LOOKUP = {name: code for code, name in SHAPETYPE_LOOKUP.items()}

TRIANGLE_STRIP = 0
TRIANGLE_FAN = 1
OUTER_RING = 2
INNER_RING = 3
FIRST_RING = 4
RING = 5

PARTTYPE_LOOKUP = {
    0: "TRIANGLE_STRIP",
    1: "TRIANGLE_FAN",
    2: "OUTER_RING",
    3: "INNER_RING",
    4: "FIRST_RING",
    5: "RING",
}

## Custom type variables

T = TypeVar("T")
Point2D = tuple[float, float]
Point3D = tuple[float, float, float]
PointMT = tuple[float, float, Optional[float]]
PointZT = tuple[float, float, float, Optional[float]]

Coord = Union[Point2D, Point3D]
Coords = list[Coord]

PointT = Union[Point2D, PointMT, PointZT]
PointsT = list[PointT]


class BBox(NamedTuple):
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    # = tuple[float, float, float, float]


def _min_not_None(m1: float | None, m2: float | None) -> float | None:
    if m1 is None:
        return m2
    if m2 is None:
        return m1
    return min(m1, m2)


def _max_not_None(m1: float | None, m2: float | None) -> float | None:
    if m1 is None:
        return m2
    if m2 is None:
        return m1
    return max(m1, m2)


class MBox(NamedTuple):
    mmin: float | None
    mmax: float | None

    def expand(self, other: MBox) -> MBox:
        return MBox(
            _min_not_None(self.mmin, other.mmin),
            _max_not_None(self.mmax, other.mmax),
        )

    # = tuple[float, float]


class ZBox(NamedTuple):
    zmin: float
    zmax: float
    # = tuple[float, float]


class WriteableBinStream(Protocol):
    def write(self, b: bytes) -> int: ...


class ReadableBinStream(Protocol):
    def read(self, size: int = -1) -> bytes: ...


@runtime_checkable
class WriteSeekableBinStream(Protocol):
    def write(self, b: bytes) -> int: ...
    def seek(self, offset: int, whence: int = 0) -> int: ...
    def tell(self) -> int: ...


@runtime_checkable
class ReadSeekableBinStream(Protocol):
    def seek(self, offset: int, whence: int = 0) -> int: ...
    def tell(self) -> int: ...
    def read(self, size: int = -1) -> bytes: ...


class ReadWriteSeekableBinStream(Protocol):
    def write(self, b: bytes) -> int: ...
    def seek(self, offset: int, whence: int = 0) -> int: ...
    def tell(self) -> int: ...
    def read(self, size: int = -1) -> bytes: ...


# File name, file object or anything with a read() method that returns bytes.
BinaryFileT = Union[str, PathLike[Any], IO[bytes]]
BinaryFileStreamT = Union[IO[bytes], io.BytesIO, WriteSeekableBinStream]

FieldTypeT = Literal["C", "D", "F", "L", "M", "N"]


# https://en.wikipedia.org/wiki/.dbf#Database_records
class FieldType:
    """A bare bones 'enum', as the enum library noticeably slows performance."""

    C: Final = "C"  # "Character"  # (str)
    D: Final = "D"  # "Date"
    F: Final = "F"  # "Floating point"
    L: Final = "L"  # "Logical"  # (bool)
    M: Final = "M"  # "Memo"  # Legacy. (10 digit str, starting block in an .dbt file)
    N: Final = "N"  # "Numeric"  # (int)
    __members__: set[FieldTypeT] = {
        "C",
        "D",
        "F",
        "L",
        "M",
        "N",
    }


FIELD_TYPE_ALIASES: dict[str | bytes, FieldTypeT] = {}
for c in FieldType.__members__:
    FIELD_TYPE_ALIASES[c.upper()] = c
    FIELD_TYPE_ALIASES[c.lower()] = c
    FIELD_TYPE_ALIASES[c.encode("ascii").lower()] = c
    FIELD_TYPE_ALIASES[c.encode("ascii").upper()] = c


# Use functional syntax to have an attribute named type, a Python keyword
class Field(NamedTuple):
    name: str
    field_type: FieldTypeT
    size: int
    decimal: int

    @classmethod
    def from_unchecked(
        cls,
        name: str,
        field_type: str | bytes | FieldTypeT = "C",
        size: int = 50,
        decimal: int = 0,
    ) -> Field:
        try:
            type_ = FIELD_TYPE_ALIASES[field_type]
        except KeyError:
            raise ShapefileException(
                f"field_type must be in {{FieldType.__members__}}. Got: {field_type=}. "
            )

        if type_ is FieldType.D:
            size = 8
            decimal = 0
        elif type_ is FieldType.L:
            size = 1
            decimal = 0

        # A doctest in README.md previously passed in a string ('40') for size,
        # so explictly convert name to str, and size and decimal to ints.
        return cls(
            name=str(name), field_type=type_, size=int(size), decimal=int(decimal)
        )

    def __repr__(self) -> str:
        return f'Field(name="{self.name}", field_type=FieldType.{self.field_type}, size={self.size}, decimal={self.decimal})'


RecordValueNotDate = Union[bool, int, float, str]

# A Possible value in a Shapefile dbf record, i.e. L, N, M, F, C, or D types
RecordValue = Union[RecordValueNotDate, date]


class HasGeoInterface(Protocol):
    @property
    def __geo_interface__(self) -> GeoJSONHomogeneousGeometryObject: ...


class GeoJSONPoint(TypedDict):
    type: Literal["Point"]
    # We fix to a tuple (to statically check the length is 2, 3 or 4) but
    # RFC7946 only requires: "A position is an array of numbers.  There MUST be two or more
    # elements.  "
    # RFC7946 also requires long/lat easting/northing which we do not enforce,
    # and despite the SHOULD NOT, we may use a 4th element for Shapefile M Measures.
    coordinates: PointT | tuple[()]


class GeoJSONMultiPoint(TypedDict):
    type: Literal["MultiPoint"]
    coordinates: PointsT


class GeoJSONLineString(TypedDict):
    type: Literal["LineString"]
    # "Two or more positions" not enforced by type checker
    # https://datatracker.ietf.org/doc/html/rfc7946#section-3.1.4
    coordinates: PointsT


class GeoJSONMultiLineString(TypedDict):
    type: Literal["MultiLineString"]
    coordinates: list[PointsT]


class GeoJSONPolygon(TypedDict):
    type: Literal["Polygon"]
    # Other requirements for Polygon not enforced by type checker
    # https://datatracker.ietf.org/doc/html/rfc7946#section-3.1.6
    coordinates: list[PointsT]


class GeoJSONMultiPolygon(TypedDict):
    type: Literal["MultiPolygon"]
    coordinates: list[list[PointsT]]


GeoJSONHomogeneousGeometryObject = Union[
    GeoJSONPoint,
    GeoJSONMultiPoint,
    GeoJSONLineString,
    GeoJSONMultiLineString,
    GeoJSONPolygon,
    GeoJSONMultiPolygon,
]

GEOJSON_TO_SHAPETYPE: dict[str, int] = {
    "Null": NULL,
    "Point": POINT,
    "LineString": POLYLINE,
    "Polygon": POLYGON,
    "MultiPoint": MULTIPOINT,
    "MultiLineString": POLYLINE,
    "MultiPolygon": POLYGON,
}


class GeoJSONGeometryCollection(TypedDict):
    type: Literal["GeometryCollection"]
    geometries: list[GeoJSONHomogeneousGeometryObject]


# RFC7946 3.1
GeoJSONObject = Union[GeoJSONHomogeneousGeometryObject, GeoJSONGeometryCollection]


class GeoJSONFeature(TypedDict):
    type: Literal["Feature"]
    properties: (
        dict[str, Any] | None
    )  # RFC7946 3.2 "(any JSON object or a JSON null value)"
    geometry: GeoJSONObject | None


class GeoJSONFeatureCollection(TypedDict):
    type: Literal["FeatureCollection"]
    features: list[GeoJSONFeature]


class GeoJSONFeatureCollectionWithBBox(GeoJSONFeatureCollection):
    # bbox is technically optional under the spec but this seems
    # a very minor improvement that would require NotRequired
    # from the typing-extensions backport for Python 3.9
    # (PyShp's resisted having any other dependencies so far!)
    bbox: list[float]


# Helpers

MISSING = (None, "")  # Don't make a set, as user input may not be Hashable
ISDATA_LOWER_BOUND = -1e38  # as per the ESRI shapefile spec, only used for m-values.
NODATA = (
    10 * ISDATA_LOWER_BOUND
)  # value to encode m=None as.  Must be < ISDATA_LOWER_BOUND


# Begin

ARR_TYPE = TypeVar("ARR_TYPE", int, float)


class _Array(array.array, Generic[ARR_TYPE]):  # type: ignore[type-arg]
    """Converts python tuples to lists of the appropriate type.
    Used to unpack different shapefile header parts."""

    def __repr__(self) -> str:
        return str(self.tolist())


def signed_area(
    coords: PointsT,
    fast: bool = False,
) -> float:
    """Return the signed area enclosed by a ring using the linear time
    algorithm. A value >= 0 indicates a counter-clockwise oriented ring.
    A faster version is possible by setting 'fast' to True, which returns
    2x the area, e.g. if you're only interested in the sign of the area.
    """
    xs, ys = map(list, list(zip(*coords))[:2])  # ignore any z or m values
    xs.append(xs[1])
    ys.append(ys[1])
    area2: float = sum(xs[i] * (ys[i + 1] - ys[i - 1]) for i in range(1, len(coords)))
    if fast:
        return area2

    return area2 / 2.0


def is_cw(coords: PointsT) -> bool:
    """Returns True if a polygon ring has clockwise orientation, determined
    by a negatively signed area.
    """
    area2 = signed_area(coords, fast=True)
    return area2 < 0


def rewind(coords: Reversible[PointT]) -> PointsT:
    """Returns the input coords in reversed order."""
    return list(reversed(coords))


def ring_bbox(coords: PointsT) -> BBox:
    """Calculates and returns the bounding box of a ring."""
    xs, ys = map(list, list(zip(*coords))[:2])  # ignore any z or m values
    # bbox = BBox(xmin=min(xs), ymin=min(ys), xmax=max(xs), ymax=max(ys))
    # return bbox
    return BBox(min(xs), min(ys), max(xs), max(ys))


def bbox_overlap(bbox1: BBox, bbox2: BBox) -> bool:
    """Tests whether two bounding boxes overlap."""
    xmin1, ymin1, xmax1, ymax1 = bbox1
    xmin2, ymin2, xmax2, ymax2 = bbox2
    overlap = xmin1 <= xmax2 and xmin2 <= xmax1 and ymin1 <= ymax2 and ymin2 <= ymax1
    return overlap


def bbox_contains(bbox1: BBox, bbox2: BBox) -> bool:
    """Tests whether bbox1 fully contains bbox2."""
    xmin1, ymin1, xmax1, ymax1 = bbox1
    xmin2, ymin2, xmax2, ymax2 = bbox2
    contains = xmin1 < xmin2 and xmax2 < xmax1 and ymin1 < ymin2 and ymax2 < ymax1
    return contains


def ring_contains_point(coords: PointsT, p: Point2D) -> bool:
    """Fast point-in-polygon crossings algorithm, MacMartin optimization.

    Adapted from code by Eric Haynes
    http://www.realtimerendering.com/resources/GraphicsGems//gemsiv/ptpoly_haines/ptinpoly.c

    Original description:
        Shoot a test ray along +X axis.  The strategy, from MacMartin, is to
        compare vertex Y values to the testing point's Y and quickly discard
        edges which are entirely to one side of the test ray.
    """
    tx, ty = p

    # get initial test bit for above/below X axis
    vtx0 = coords[0]
    yflag0 = vtx0[1] >= ty

    inside_flag = False
    for vtx1 in coords[1:]:
        yflag1 = vtx1[1] >= ty
        # check if endpoints straddle (are on opposite sides) of X axis
        # (i.e. the Y's differ); if so, +X ray could intersect this edge.
        if yflag0 != yflag1:
            xflag0 = vtx0[0] >= tx
            # check if endpoints are on same side of the Y axis (i.e. X's
            # are the same); if so, it's easy to test if edge hits or misses.
            if xflag0 == (vtx1[0] >= tx):
                # if edge's X values both right of the point, must hit
                if xflag0:
                    inside_flag = not inside_flag
            else:
                # compute intersection of pgon segment with +X ray, note
                # if >= point's X; if so, the ray hits it.
                if (
                    vtx1[0] - (vtx1[1] - ty) * (vtx0[0] - vtx1[0]) / (vtx0[1] - vtx1[1])
                ) >= tx:
                    inside_flag = not inside_flag

        # move to next pair of vertices, retaining info as possible
        yflag0 = yflag1
        vtx0 = vtx1

    return inside_flag


class RingSamplingError(Exception):
    pass


def ring_sample(coords: PointsT, ccw: bool = False) -> Point2D:
    """Return a sample point guaranteed to be within a ring, by efficiently
    finding the first centroid of a coordinate triplet whose orientation
    matches the orientation of the ring and passes the point-in-ring test.
    The orientation of the ring is assumed to be clockwise, unless ccw
    (counter-clockwise) is set to True.
    """
    triplet = []

    def itercoords() -> Iterator[PointT]:
        # iterate full closed ring
        yield from coords
        # finally, yield the second coordinate to the end to allow checking the last triplet
        yield coords[1]

    for p in itercoords():
        # add point to triplet (but not if duplicate)
        if p not in triplet:
            triplet.append(p)

        # new triplet, try to get sample
        if len(triplet) == 3:
            # check that triplet does not form a straight line (not a triangle)
            is_straight_line = (triplet[0][1] - triplet[1][1]) * (
                triplet[0][0] - triplet[2][0]
            ) == (triplet[0][1] - triplet[2][1]) * (triplet[0][0] - triplet[1][0])
            if not is_straight_line:
                # get triplet orientation
                closed_triplet = triplet + [triplet[0]]
                triplet_ccw = not is_cw(closed_triplet)
                # check that triplet has the same orientation as the ring (means triangle is inside the ring)
                if ccw == triplet_ccw:
                    # get triplet centroid
                    xs, ys = zip(*triplet)
                    xmean, ymean = sum(xs) / 3.0, sum(ys) / 3.0
                    # check that triplet centroid is truly inside the ring
                    if ring_contains_point(coords, (xmean, ymean)):
                        return xmean, ymean

            # failed to get sample point from this triplet
            # remove oldest triplet coord to allow iterating to next triplet
            triplet.pop(0)

    raise RingSamplingError(
        f"Unexpected error: Unable to find a ring sample point in: {coords}."
        "Ensure the ring's coordinates are oriented clockwise, "
        "and ensure the area enclosed is non-zero. "
    )


def ring_contains_ring(coords1: PointsT, coords2: list[PointT]) -> bool:
    """Returns True if all vertexes in coords2 are fully inside coords1."""
    # Ignore Z and M values in coords2
    return all(ring_contains_point(coords1, p2[:2]) for p2 in coords2)


def organize_polygon_rings(
    rings: Iterable[PointsT], return_errors: dict[str, int] | None = None
) -> list[list[PointsT]]:
    """Organize a list of coordinate rings into one or more polygons with holes.
    Returns a list of polygons, where each polygon is composed of a single exterior
    ring, and one or more interior holes. If a return_errors dict is provided (optional),
    any errors encountered will be added to it.

    Rings must be closed, and cannot intersect each other (non-self-intersecting polygon).
    Rings are determined as exteriors if they run in clockwise direction, or interior
    holes if they run in counter-clockwise direction. This method is used to construct
    GeoJSON (multi)polygons from the shapefile polygon shape type, which does not
    explicitly store the structure of the polygons beyond exterior/interior ring orientation.
    """
    # first iterate rings and classify as exterior or hole
    exteriors = []
    holes = []
    for ring in rings:
        # shapefile format defines a polygon as a sequence of rings
        # where exterior rings are clockwise, and holes counterclockwise
        if is_cw(ring):
            # ring is exterior
            exteriors.append(ring)
        else:
            # ring is a hole
            holes.append(ring)

    # if only one exterior, then all holes belong to that exterior
    if len(exteriors) == 1:
        # exit early
        poly = [exteriors[0]] + holes
        polys = [poly]
        return polys

    # multiple exteriors, ie multi-polygon, have to group holes with correct exterior
    # shapefile format does not specify which holes belong to which exteriors
    # so have to do efficient multi-stage checking of hole-to-exterior containment
    if len(exteriors) > 1:
        # exit early if no holes
        if not holes:
            polys = []
            for ext in exteriors:
                poly = [ext]
                polys.append(poly)
            return polys

        # first determine each hole's candidate exteriors based on simple bbox contains test
        hole_exteriors: dict[int, list[int]] = {
            hole_i: [] for hole_i in range(len(holes))
        }
        exterior_bboxes = [ring_bbox(ring) for ring in exteriors]
        for hole_i in hole_exteriors.keys():
            hole_bbox = ring_bbox(holes[hole_i])
            for ext_i, ext_bbox in enumerate(exterior_bboxes):
                if bbox_contains(ext_bbox, hole_bbox):
                    hole_exteriors[hole_i].append(ext_i)

        # then, for holes with still more than one possible exterior, do more detailed hole-in-ring test
        for hole_i, exterior_candidates in hole_exteriors.items():
            if len(exterior_candidates) > 1:
                # get hole sample point
                ccw = not is_cw(holes[hole_i])
                hole_sample = ring_sample(holes[hole_i], ccw=ccw)
                # collect new exterior candidates
                new_exterior_candidates = []
                for ext_i in exterior_candidates:
                    # check that hole sample point is inside exterior
                    hole_in_exterior = ring_contains_point(
                        exteriors[ext_i], hole_sample
                    )
                    if hole_in_exterior:
                        new_exterior_candidates.append(ext_i)

                # set new exterior candidates
                hole_exteriors[hole_i] = new_exterior_candidates

        # if still holes with more than one possible exterior, means we have an exterior hole nested inside another exterior's hole
        for hole_i, exterior_candidates in hole_exteriors.items():
            if len(exterior_candidates) > 1:
                # exterior candidate with the smallest area is the hole's most immediate parent
                ext_i = sorted(
                    exterior_candidates,
                    key=lambda x: abs(signed_area(exteriors[x], fast=True)),
                )[0]
                hole_exteriors[hole_i] = [ext_i]

        # separate out holes that are orphaned (not contained by any exterior)
        orphan_holes = []
        for hole_i, exterior_candidates in list(hole_exteriors.items()):
            if not exterior_candidates:
                orphan_holes.append(hole_i)
                del hole_exteriors[hole_i]
                continue

        # each hole should now only belong to one exterior, group into exterior-holes polygons
        polys = []
        for ext_i, ext in enumerate(exteriors):
            poly = [ext]
            # find relevant holes
            poly_holes = []
            for hole_i, exterior_candidates in list(hole_exteriors.items()):
                # hole is relevant if previously matched with this exterior
                if exterior_candidates[0] == ext_i:
                    poly_holes.append(holes[hole_i])
            poly += poly_holes
            polys.append(poly)

        # add orphan holes as exteriors
        for hole_i in orphan_holes:
            ext = holes[hole_i]
            # add as single exterior without any holes
            poly = [ext]
            polys.append(poly)

        if orphan_holes and return_errors is not None:
            return_errors["polygon_orphaned_holes"] = len(orphan_holes)

        return polys

    # no exteriors, be nice and assume due to incorrect winding order
    if return_errors is not None:
        return_errors["polygon_only_holes"] = len(holes)
    exteriors = holes
    # add as single exterior without any holes
    polys = [[ext] for ext in exteriors]
    return polys


class GeoJSON_Error(Exception):
    pass


class _NoShapeTypeSentinel:
    """For use as a default value for Shape.__init__ to
    preserve old behaviour for anyone who explictly
    called Shape(shapeType=None).
    """


_NO_SHAPE_TYPE_SENTINEL: Final = _NoShapeTypeSentinel()


def _m_from_point(point: PointMT | PointZT, mpos: int) -> float | None:
    if len(point) > mpos and point[mpos] is not None:
        return cast(float, point[mpos])
    return None


def _ms_from_points(
    points: list[PointMT] | list[PointZT], mpos: int
) -> Iterator[float | None]:
    return (_m_from_point(p, mpos) for p in points)


def _z_from_point(point: PointZT) -> float:
    if len(point) >= 3 and point[2] is not None:
        return point[2]
    return 0.0


def _zs_from_points(points: Iterable[PointZT]) -> Iterator[float]:
    return (_z_from_point(p) for p in points)


class CanHaveBboxNoLinesKwargs(TypedDict, total=False):
    oid: int | None
    points: PointsT | None
    parts: Sequence[int] | None  # index of start point of each part
    partTypes: Sequence[int] | None
    bbox: BBox | None
    m: Sequence[float | None] | None
    z: Sequence[float] | None
    mbox: MBox | None
    zbox: ZBox | None


class Shape:
    def __init__(
        self,
        shapeType: int | _NoShapeTypeSentinel = _NO_SHAPE_TYPE_SENTINEL,
        points: PointsT | None = None,
        parts: Sequence[int] | None = None,  # index of start point of each part
        lines: list[PointsT] | None = None,
        partTypes: Sequence[int] | None = None,
        oid: int | None = None,
        *,
        m: Sequence[float | None] | None = None,
        z: Sequence[float] | None = None,
        bbox: BBox | None = None,
        mbox: MBox | None = None,
        zbox: ZBox | None = None,
    ):
        """Stores the geometry of the different shape types
        specified in the Shapefile spec. Shape types are
        usually point, polyline, or polygons. Every shape type
        except the "Null" type contains points at some level for
        example vertices in a polygon. If a shape type has
        multiple shapes containing points within a single
        geometry record then those shapes are called parts. Parts
        are designated by their starting index in geometry record's
        list of shapes. For MultiPatch geometry, partTypes designates
        the patch type of each of the parts.
        Lines allows the points-lists and parts to be denoted together
        in one argument.  It is intended for multiple point shapes
        (polylines, polygons and multipatches) but if used as a length-1
        nested list for a multipoint (instead of points for some reason)
        PyShp will not complain, as multipoints only have 1 part internally.
        """

        # Preserve previous behaviour for anyone who set self.shapeType = None
        if shapeType is not _NO_SHAPE_TYPE_SENTINEL:
            self.shapeType = cast(int, shapeType)
        else:
            class_name = self.__class__.__name__
            self.shapeType = SHAPETYPENUM_LOOKUP.get(class_name.upper(), NULL)

        if partTypes is not None:
            self.partTypes = partTypes

        default_points: PointsT = []
        default_parts: list[int] = []

        if lines is not None:
            if self.shapeType in Polygon_shapeTypes:
                lines = list(lines)
                self._ensure_polygon_rings_closed(lines)

            default_points, default_parts = self._points_and_parts_indexes_from_lines(
                lines
            )
        elif points and self.shapeType in _CanHaveBBox_shapeTypes:
            # TODO:  Raise issue.
            # This ensures Polylines, Polygons and Multipatches with no part information are a single
            # Polyline, Polygon or Multipatch respectively.
            #
            # However this also allows MultiPoints shapes to have a single part index 0 as
            # documented in README.md,also when set from points
            # (even though this is just an artefact of initialising them as a length-1 nested
            # list of points via _points_and_parts_indexes_from_lines).
            #
            # Alternatively single points could be given parts = [0] too, as they do if formed
            # _from_geojson.
            default_parts = [0]

        self.points: PointsT = points or default_points

        self.parts: Sequence[int] = parts or default_parts

        # and a dict to silently record any errors encountered in GeoJSON
        self._errors: dict[str, int] = {}

        # add oid
        self.__oid: int = -1 if oid is None else oid

        if bbox is not None:
            self.bbox: BBox = bbox
        elif len(self.points) >= 2:
            self.bbox = self._bbox_from_points()

        ms_found = True
        if m:
            self.m: Sequence[float | None] = m
        elif self.shapeType in _HasM_shapeTypes:
            mpos = 3 if self.shapeType in _HasZ_shapeTypes | PointZ_shapeTypes else 2
            points_m_z = cast(Union[list[PointMT], list[PointZT]], self.points)
            self.m = list(_ms_from_points(points_m_z, mpos))
        elif self.shapeType in PointM_shapeTypes:
            mpos = 3 if self.shapeType == POINTZ else 2
            point_m_z = cast(Union[PointMT, PointZT], self.points[0])
            self.m = (_m_from_point(point_m_z, mpos),)
        else:
            ms_found = False

        zs_found = True
        if z:
            self.z: Sequence[float] = z
        elif self.shapeType in _HasZ_shapeTypes:
            points_z = cast(list[PointZT], self.points)
            self.z = list(_zs_from_points(points_z))
        elif self.shapeType == POINTZ:
            point_z = cast(PointZT, self.points[0])
            self.z = (_z_from_point(point_z),)
        else:
            zs_found = False

        if mbox is not None:
            self.mbox: MBox = mbox
        elif ms_found:
            self.mbox = self._mbox_from_ms()

        if zbox is not None:
            self.zbox: ZBox = zbox
        elif zs_found:
            self.zbox = self._zbox_from_zs()

    @staticmethod
    def _ensure_polygon_rings_closed(
        parts: list[PointsT],  # Mutated
    ) -> None:
        for part in parts:
            if part[0] != part[-1]:
                part.append(part[0])

    @staticmethod
    def _points_and_parts_indexes_from_lines(
        parts: list[PointsT],
    ) -> tuple[PointsT, list[int]]:
        # Intended for Union[Polyline, Polygon, MultiPoint, MultiPatch]
        """From a list of parts (each part a list of points) return
        a flattened list of points, and a list of indexes into that
        flattened list corresponding to the start of each part.

        Internal method for both multipoints (formed entirely by a single part),
        and shapes that have multiple collections of points (each one
        a part): (poly)lines, polygons, and multipatchs.
        """
        part_indexes: list[int] = []
        points: PointsT = []

        for part in parts:
            # set part index position
            part_indexes.append(len(points))
            points.extend(part)

        return points, part_indexes

    def _bbox_from_points(self) -> BBox:
        xs: list[float] = []
        ys: list[float] = []

        for point in self.points:
            xs.append(point[0])
            ys.append(point[1])

        return BBox(min(xs), min(ys), max(xs), max(ys))

    def _mbox_from_ms(self) -> MBox:
        ms: list[float] = [m for m in self.m if m is not None]

        if not ms:
            return MBox(None, None)
            # # only if none of the shapes had m values, should mbox be set to missing m values
            # ms.append(NODATA)

        return MBox(min(ms), max(ms))

    def _zbox_from_zs(self) -> ZBox:
        return ZBox(min(self.z), max(self.z))

    @property
    def __geo_interface__(self) -> GeoJSONHomogeneousGeometryObject:
        if self.shapeType in {POINT, POINTM, POINTZ}:
            # point
            if len(self.points) == 0:
                # the shape has no coordinate information, i.e. is 'empty'
                # the geojson spec does not define a proper null-geometry type
                # however, it does allow geometry types with 'empty' coordinates to be interpreted as null-geometries
                return {"type": "Point", "coordinates": ()}

            return {"type": "Point", "coordinates": self.points[0]}

        if self.shapeType in {MULTIPOINT, MULTIPOINTM, MULTIPOINTZ}:
            if len(self.points) == 0:
                # the shape has no coordinate information, i.e. is 'empty'
                # the geojson spec does not define a proper null-geometry type
                # however, it does allow geometry types with 'empty' coordinates to be interpreted as null-geometries
                return {"type": "MultiPoint", "coordinates": []}

            # multipoint
            return {
                "type": "MultiPoint",
                "coordinates": self.points,
            }

        if self.shapeType in {POLYLINE, POLYLINEM, POLYLINEZ}:
            if len(self.parts) == 0:
                # the shape has no coordinate information, i.e. is 'empty'
                # the geojson spec does not define a proper null-geometry type
                # however, it does allow geometry types with 'empty' coordinates to be interpreted as null-geometries
                return {"type": "LineString", "coordinates": []}

            if len(self.parts) == 1:
                # linestring
                return {
                    "type": "LineString",
                    "coordinates": self.points,
                }

            # multilinestring
            ps = None
            coordinates = []
            for part in self.parts:
                if ps is None:
                    ps = part
                    continue

                coordinates.append(list(self.points[ps:part]))
                ps = part

            # assert len(self.parts) > 1
            # from previous if len(self.parts) checks so part is defined
            coordinates.append(list(self.points[part:]))
            return {"type": "MultiLineString", "coordinates": coordinates}

        if self.shapeType in {POLYGON, POLYGONM, POLYGONZ}:
            if len(self.parts) == 0:
                # the shape has no coordinate information, i.e. is 'empty'
                # the geojson spec does not define a proper null-geometry type
                # however, it does allow geometry types with 'empty' coordinates to be interpreted as null-geometries
                return {"type": "Polygon", "coordinates": []}

            # get all polygon rings
            rings = []
            for i, start in enumerate(self.parts):
                # get indexes of start and end points of the ring
                try:
                    end = self.parts[i + 1]
                except IndexError:
                    end = len(self.points)

                # extract the points that make up the ring
                ring = list(self.points[start:end])
                rings.append(ring)

            # organize rings into list of polygons, where each polygon is defined as list of rings.
            # the first ring is the exterior and any remaining rings are holes (same as GeoJSON).
            polys = organize_polygon_rings(rings, self._errors)

            # if VERBOSE is True, issue detailed warning about any shape errors
            # encountered during the Shapefile to GeoJSON conversion
            if VERBOSE and self._errors:
                header = f"Possible issue encountered when converting Shape #{self.oid} to GeoJSON: "
                orphans = self._errors.get("polygon_orphaned_holes", None)
                if orphans:
                    msg = (
                        header
                        + "Shapefile format requires that all polygon interior holes be contained by an exterior ring, \
but the Shape contained interior holes (defined by counter-clockwise orientation in the shapefile format) that were \
orphaned, i.e. not contained by any exterior rings. The rings were still included but were \
encoded as GeoJSON exterior rings instead of holes."
                    )
                    logger.warning(msg)
                only_holes = self._errors.get("polygon_only_holes", None)
                if only_holes:
                    msg = (
                        header
                        + "Shapefile format requires that polygons contain at least one exterior ring, \
but the Shape was entirely made up of interior holes (defined by counter-clockwise orientation in the shapefile format). The rings were \
still included but were encoded as GeoJSON exterior rings instead of holes."
                    )
                    logger.warning(msg)

            # return as geojson
            if len(polys) == 1:
                return {"type": "Polygon", "coordinates": polys[0]}

            return {"type": "MultiPolygon", "coordinates": polys}

        raise GeoJSON_Error(
            f'Shape type "{SHAPETYPE_LOOKUP[self.shapeType]}" cannot be represented as GeoJSON.'
        )

    @staticmethod
    def _from_geojson(geoj: GeoJSONHomogeneousGeometryObject) -> Shape:
        # create empty shape
        # set shapeType
        geojType = geoj["type"] if geoj else "Null"
        if geojType in GEOJSON_TO_SHAPETYPE:
            shapeType = GEOJSON_TO_SHAPETYPE[geojType]
        else:
            raise GeoJSON_Error(f"Cannot create Shape from GeoJSON type '{geojType}'")

        coordinates = geoj["coordinates"]

        if coordinates == ():
            raise GeoJSON_Error(f"Cannot create non-Null Shape from: {coordinates=}")

        points: PointsT
        parts: list[int]

        # set points and parts
        if geojType == "Point":
            points = [cast(PointT, coordinates)]
            parts = [0]
        elif geojType in ("MultiPoint", "LineString"):
            points = cast(PointsT, coordinates)
            parts = [0]
        elif geojType == "Polygon":
            points = []
            parts = []
            index = 0
            for i, ext_or_hole in enumerate(cast(list[PointsT], coordinates)):
                # although the latest GeoJSON spec states that exterior rings should have
                # counter-clockwise orientation, we explicitly check orientation since older
                # GeoJSONs might not enforce this.
                if i == 0 and not is_cw(ext_or_hole):
                    # flip exterior direction
                    ext_or_hole = rewind(ext_or_hole)
                elif i > 0 and is_cw(ext_or_hole):
                    # flip hole direction
                    ext_or_hole = rewind(ext_or_hole)
                points.extend(ext_or_hole)
                parts.append(index)
                index += len(ext_or_hole)
        elif geojType == "MultiLineString":
            points = []
            parts = []
            index = 0
            for linestring in cast(list[PointsT], coordinates):
                points.extend(linestring)
                parts.append(index)
                index += len(linestring)
        elif geojType == "MultiPolygon":
            points = []
            parts = []
            index = 0
            for polygon in cast(list[list[PointsT]], coordinates):
                for i, ext_or_hole in enumerate(polygon):
                    # although the latest GeoJSON spec states that exterior rings should have
                    # counter-clockwise orientation, we explicitly check orientation since older
                    # GeoJSONs might not enforce this.
                    if i == 0 and not is_cw(ext_or_hole):
                        # flip exterior direction
                        ext_or_hole = rewind(ext_or_hole)
                    elif i > 0 and is_cw(ext_or_hole):
                        # flip hole direction
                        ext_or_hole = rewind(ext_or_hole)
                    points.extend(ext_or_hole)
                    parts.append(index)
                    index += len(ext_or_hole)
        return Shape(shapeType=shapeType, points=points, parts=parts)

    @property
    def oid(self) -> int:
        """The index position of the shape in the original shapefile"""
        return self.__oid

    @property
    def shapeTypeName(self) -> str:
        return SHAPETYPE_LOOKUP[self.shapeType]

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        if class_name == "Shape":
            return f"Shape #{self.__oid}: {self.shapeTypeName}"
        return f"{class_name} #{self.__oid}"


# Need unused arguments to keep the same call signature for
# different implementations of from_byte_stream and write_to_byte_stream
class NullShape(Shape):
    # Shape.shapeType = NULL already,
    # to preserve handling of default args in Shape.__init__
    # Repeated for the avoidance of doubt.
    def __init__(
        self,
        oid: int | None = None,
    ):
        Shape.__init__(self, shapeType=NULL, oid=oid)

    @staticmethod
    def from_byte_stream(
        shapeType: int,
        b_io: ReadSeekableBinStream,
        next_shape_pos: int,
        oid: int | None = None,
        bbox: BBox | None = None,
    ) -> NullShape:
        # Shape.__init__ sets self.points = points or []
        return NullShape(oid=oid)

    @staticmethod
    def write_to_byte_stream(
        b_io: WriteableBinStream,
        s: Shape,
        i: int,
    ) -> int:
        return 0


_CanHaveBBox_shapeTypes = frozenset(
    [
        POLYLINE,
        POLYLINEM,
        POLYLINEZ,
        MULTIPOINT,
        MULTIPOINTM,
        MULTIPOINTZ,
        POLYGON,
        POLYGONM,
        POLYGONZ,
        MULTIPATCH,
    ]
)


class _CanHaveBBox(Shape):
    """As well as setting bounding boxes, we also utilize the
    fact that this mixin only applies to all the shapes that are
    not a single point (polylines, polygons, multipatches and multipoints).
    """

    @staticmethod
    def _read_bbox_from_byte_stream(b_io: ReadableBinStream) -> BBox:
        return BBox(*unpack("<4d", b_io.read(32)))

    @staticmethod
    def _write_bbox_to_byte_stream(
        b_io: WriteableBinStream, i: int, bbox: BBox | None
    ) -> int:
        if not bbox or len(bbox) != 4:
            raise ShapefileException(f"Four numbers required for bbox. Got: {bbox}")
        try:
            return b_io.write(pack("<4d", *bbox))
        except StructError:
            raise ShapefileException(
                f"Failed to write bounding box for record {i}. Expected floats."
            )

    @staticmethod
    def _read_npoints_from_byte_stream(b_io: ReadableBinStream) -> int:
        (nPoints,) = unpack("<i", b_io.read(4))
        return cast(int, nPoints)

    @staticmethod
    def _write_npoints_to_byte_stream(b_io: WriteableBinStream, s: _CanHaveBBox) -> int:
        return b_io.write(pack("<i", len(s.points)))

    @staticmethod
    def _read_points_from_byte_stream(
        b_io: ReadableBinStream, nPoints: int
    ) -> list[Point2D]:
        flat = unpack(f"<{2 * nPoints}d", b_io.read(16 * nPoints))
        return list(zip(*(iter(flat),) * 2))

    @staticmethod
    def _write_points_to_byte_stream(
        b_io: WriteableBinStream, s: _CanHaveBBox, i: int
    ) -> int:
        x_ys: list[float] = []
        for point in s.points:
            x_ys.extend(point[:2])
        try:
            return b_io.write(pack(f"<{len(x_ys)}d", *x_ys))
        except StructError:
            raise ShapefileException(
                f"Failed to write points for record {i}. Expected floats."
            )

    @classmethod
    def from_byte_stream(
        cls,
        shapeType: int,
        b_io: ReadSeekableBinStream,
        next_shape_pos: int,
        oid: int | None = None,
        bbox: BBox | None = None,
    ) -> Shape | None:
        ShapeClass = cast(type[_CanHaveBBox], SHAPE_CLASS_FROM_SHAPETYPE[shapeType])

        kwargs: CanHaveBboxNoLinesKwargs = {"oid": oid}  # "shapeType": shapeType}
        kwargs["bbox"] = shape_bbox = cls._read_bbox_from_byte_stream(b_io)

        # if bbox specified and no overlap, skip this shape
        if bbox is not None and not bbox_overlap(bbox, shape_bbox):
            # because we stop parsing this shape, caller must skip to beginning of
            # next shape after we return (as done in f.seek(next_shape_pos))
            return None

        nParts: int | None = (
            _CanHaveParts._read_nparts_from_byte_stream(b_io)
            if shapeType in _CanHaveParts_shapeTypes
            else None
        )
        nPoints: int = cls._read_npoints_from_byte_stream(b_io)
        # Previously, we also set __zmin = __zmax = __mmin = __mmax = None

        if nParts:
            kwargs["parts"] = _CanHaveParts._read_parts_from_byte_stream(b_io, nParts)
            if shapeType == MULTIPATCH:
                kwargs["partTypes"] = MultiPatch._read_part_types_from_byte_stream(
                    b_io, nParts
                )

        if nPoints:
            kwargs["points"] = cast(
                PointsT, cls._read_points_from_byte_stream(b_io, nPoints)
            )

            if shapeType in _HasZ_shapeTypes:
                kwargs["zbox"], kwargs["z"] = _HasZ._read_zs_from_byte_stream(
                    b_io, nPoints
                )

            if shapeType in _HasM_shapeTypes:
                kwargs["mbox"], kwargs["m"] = _HasM._read_ms_from_byte_stream(
                    b_io, nPoints, next_shape_pos
                )

        return ShapeClass(**kwargs)

    @staticmethod
    def write_to_byte_stream(
        b_io: WriteableBinStream,
        s: Shape,
        i: int,
    ) -> int:
        # We use static methods here and below,
        # to support s only being an instance of the
        # Shape base class (with shapeType set)
        # i.e. not necessarily one of our newer shape specific
        # sub classes.

        n = 0

        if s.shapeType in _CanHaveBBox_shapeTypes:
            n += _CanHaveBBox._write_bbox_to_byte_stream(b_io, i, s.bbox)

        if s.shapeType in _CanHaveParts_shapeTypes:
            n += _CanHaveParts._write_nparts_to_byte_stream(
                b_io, cast(_CanHaveParts, s)
            )
        # Shape types with multiple points per record
        if s.shapeType in _CanHaveBBox_shapeTypes:
            n += _CanHaveBBox._write_npoints_to_byte_stream(b_io, cast(_CanHaveBBox, s))
        # Write part indexes.  Includes MultiPatch
        if s.shapeType in _CanHaveParts_shapeTypes:
            n += _CanHaveParts._write_part_indices_to_byte_stream(
                b_io, cast(_CanHaveParts, s)
            )

        if s.shapeType in MultiPatch_shapeTypes:
            n += MultiPatch._write_part_types_to_byte_stream(b_io, cast(MultiPatch, s))
        # Write points for multiple-point records
        if s.shapeType in _CanHaveBBox_shapeTypes:
            n += _CanHaveBBox._write_points_to_byte_stream(
                b_io, cast(_CanHaveBBox, s), i
            )
        if s.shapeType in _HasZ_shapeTypes:
            n += _HasZ._write_zs_to_byte_stream(b_io, cast(_HasZ, s), i, s.zbox)

        if s.shapeType in _HasM_shapeTypes:
            n += _HasM._write_ms_to_byte_stream(b_io, cast(_HasM, s), i, s.mbox)

        return n


_CanHaveParts_shapeTypes = frozenset(
    [
        POLYLINE,
        POLYLINEM,
        POLYLINEZ,
        POLYGON,
        POLYGONM,
        POLYGONZ,
        MULTIPATCH,
    ]
)


class _CanHaveParts(_CanHaveBBox):
    # The parts attribute is initialised by
    # the base class Shape's __init__, to parts or [].
    # "Can Have Parts" should be read as "Can Have non-empty parts".

    @staticmethod
    def _read_nparts_from_byte_stream(b_io: ReadableBinStream) -> int:
        (nParts,) = unpack("<i", b_io.read(4))
        return cast(int, nParts)

    @staticmethod
    def _write_nparts_to_byte_stream(b_io: WriteableBinStream, s: _CanHaveParts) -> int:
        return b_io.write(pack("<i", len(s.parts)))

    @staticmethod
    def _read_parts_from_byte_stream(
        b_io: ReadableBinStream, nParts: int
    ) -> _Array[int]:
        return _Array[int]("i", unpack(f"<{nParts}i", b_io.read(nParts * 4)))

    @staticmethod
    def _write_part_indices_to_byte_stream(
        b_io: WriteableBinStream, s: _CanHaveParts
    ) -> int:
        return b_io.write(pack(f"<{len(s.parts)}i", *s.parts))


Point_shapeTypes = frozenset([POINT, POINTM, POINTZ])


class Point(Shape):
    # We also use the fact that the single Point types are the only
    # shapes that cannot have their own bounding box (a user supplied
    # bbox is still used to filter out points).
    def __init__(
        self,
        x: float,
        y: float,
        oid: int | None = None,
    ):
        Shape.__init__(self, points=[(x, y)], oid=oid)

    @staticmethod
    def _x_y_from_byte_stream(b_io: ReadableBinStream) -> tuple[float, float]:
        x, y = unpack("<2d", b_io.read(16))
        # Convert to tuple
        return x, y

    @staticmethod
    def _write_x_y_to_byte_stream(
        b_io: WriteableBinStream, x: float, y: float, i: int
    ) -> int:
        try:
            return b_io.write(pack("<2d", x, y))
        except StructError:
            raise ShapefileException(
                f"Failed to write point for record {i}. Expected floats."
            )

    @classmethod
    def from_byte_stream(
        cls,
        shapeType: int,
        b_io: ReadSeekableBinStream,
        next_shape_pos: int,
        oid: int | None = None,
        bbox: BBox | None = None,
    ) -> Shape | None:
        x, y = cls._x_y_from_byte_stream(b_io)

        if bbox is not None:
            # create bounding box for Point by duplicating coordinates
            # skip shape if no overlap with bounding box
            if not bbox_overlap(bbox, BBox(x, y, x, y)):
                return None
        elif shapeType == POINT:
            return Point(x=x, y=y, oid=oid)

        if shapeType == POINTZ:
            z = PointZ._read_single_point_zs_from_byte_stream(b_io)[0]

        m = PointM._read_single_point_ms_from_byte_stream(b_io, next_shape_pos)[0]

        if shapeType == POINTZ:
            return PointZ(x=x, y=y, z=z, m=m, oid=oid)

        return PointM(x=x, y=y, m=m, oid=oid)
        # return Shape(shapeType=shapeType, points=[(x, y)], z=zs, m=ms, oid=oid)

    @staticmethod
    def write_to_byte_stream(b_io: WriteableBinStream, s: Shape, i: int) -> int:
        # Serialize a single point
        x, y = s.points[0][0], s.points[0][1]
        n = Point._write_x_y_to_byte_stream(b_io, x, y, i)

        # Write a single Z value
        if s.shapeType in PointZ_shapeTypes:
            n += PointZ._write_single_point_z_to_byte_stream(b_io, s, i)

        # Write a single M value
        if s.shapeType in PointM_shapeTypes:
            n += PointM._write_single_point_m_to_byte_stream(b_io, s, i)

        return n


Polyline_shapeTypes = frozenset([POLYLINE, POLYLINEM, POLYLINEZ])


class Polyline(_CanHaveParts):
    def __init__(
        self,
        *args: PointsT,
        lines: list[PointsT] | None = None,
        points: PointsT | None = None,
        parts: list[int] | None = None,
        bbox: BBox | None = None,
        oid: int | None = None,
    ):
        if args:
            if lines:
                raise ShapefileException(
                    "Specify Either: a) positional args, or: b) the keyword arg lines. "
                    f"Not both.  Got both: {args} and {lines=}. "
                    "If this was intentional, after the other positional args, "
                    "the arg passed to lines can be unpacked (arg1, arg2, *more_args, *lines, oid=oid,...)"
                )
            lines = list(args)
        Shape.__init__(
            self,
            lines=lines,
            points=points,
            parts=parts,
            bbox=bbox,
            oid=oid,
        )


Polygon_shapeTypes = frozenset([POLYGON, POLYGONM, POLYGONZ])


class Polygon(_CanHaveParts):
    def __init__(
        self,
        *args: PointsT,
        lines: list[PointsT] | None = None,
        parts: list[int] | None = None,
        points: PointsT | None = None,
        bbox: BBox | None = None,
        oid: int | None = None,
    ):
        lines = list(args) if args else lines
        Shape.__init__(
            self,
            lines=lines,
            points=points,
            parts=parts,
            bbox=bbox,
            oid=oid,
        )


MultiPoint_shapeTypes = frozenset([MULTIPOINT, MULTIPOINTM, MULTIPOINTZ])


class MultiPoint(_CanHaveBBox):
    def __init__(
        self,
        *args: PointT,
        points: PointsT | None = None,
        bbox: BBox | None = None,
        oid: int | None = None,
    ):
        if args:
            if points:
                raise ShapefileException(
                    "Specify Either: a) positional args, or: b) the keyword arg points. "
                    f"Not both.  Got both: {args} and {points=}. "
                    "If this was intentional, after the other positional args, "
                    "the arg passed to points can be unpacked, e.g. "
                    " (arg1, arg2, *more_args, *points, oid=oid,...)"
                )
            points = list(args)
        Shape.__init__(
            self,
            points=points,
            bbox=bbox,
            oid=oid,
        )


# Not a PointM or a PointZ
_HasM_shapeTypes = frozenset(
    [
        POLYLINEM,
        POLYLINEZ,
        POLYGONM,
        POLYGONZ,
        MULTIPOINTM,
        MULTIPOINTZ,
        MULTIPATCH,
    ]
)


def replace_None_with_NODATA(ms: Iterable[float | None]) -> list[float]:
    return [m if m is not None else NODATA for m in ms]


class _HasM(_CanHaveBBox):
    m: Sequence[float | None]

    @staticmethod
    def _read_ms_from_byte_stream(
        b_io: ReadSeekableBinStream, nPoints: int, next_shape_pos: int
    ) -> tuple[MBox | None, list[float | None]]:
        mbox = None  # Ensure mbox is always defined
        if next_shape_pos - b_io.tell() >= 16:
            mbox = MBox(*unpack("<2d", b_io.read(16)))
        # Measure values less than -10e38 are nodata values according to the spec
        if next_shape_pos - b_io.tell() >= nPoints * 8:
            ms = []
            for m in unpack(f"<{nPoints}d", b_io.read(nPoints * 8)):
                if m >= ISDATA_LOWER_BOUND:
                    ms.append(m)
                else:
                    ms.append(None)
        else:
            ms = [None for _ in range(nPoints)]
        return mbox, ms

    @staticmethod
    def _write_ms_to_byte_stream(
        b_io: WriteableBinStream, s: Shape, i: int, mbox: MBox | None
    ) -> int:
        if not mbox or len(mbox) != 2:
            raise ShapefileException(f"Two numbers required for mbox. Got: {mbox}")
        # Write m extremes and values
        # When reading a file, pyshp converts NODATA m values to None, so here we make sure to convert them back to NODATA
        # Note: missing m values are autoset to NODATA.
        try:
            num_bytes_written = b_io.write(pack("<2d", *replace_None_with_NODATA(mbox)))
        except StructError:
            raise ShapefileException(
                f"Failed to write measure extremes for record {i}. Expected floats"
            )
        try:
            ms = cast(_HasM, s).m

            ms_to_encode = replace_None_with_NODATA(ms)

            num_bytes_written += b_io.write(pack(f"<{len(ms)}d", *ms_to_encode))
        except StructError:
            raise ShapefileException(
                f"Failed to write measure values for record {i}. Expected floats"
            )

        return num_bytes_written


# Not a PointZ
_HasZ_shapeTypes = frozenset(
    [
        POLYLINEZ,
        POLYGONZ,
        MULTIPOINTZ,
        MULTIPATCH,
    ]
)


class _HasZ(_CanHaveBBox):
    z: Sequence[float]

    @staticmethod
    def _read_zs_from_byte_stream(
        b_io: ReadableBinStream, nPoints: int
    ) -> tuple[ZBox, Sequence[float]]:
        zbox = ZBox(*unpack("<2d", b_io.read(16)))
        return zbox, _Array[float]("d", unpack(f"<{nPoints}d", b_io.read(nPoints * 8)))

    @staticmethod
    def _write_zs_to_byte_stream(
        b_io: WriteableBinStream, s: Shape, i: int, zbox: ZBox | None
    ) -> int:
        if not zbox or len(zbox) != 2:
            raise ShapefileException(f"Two numbers required for zbox. Got: {zbox}")

        # Write z extremes and values
        # Note: missing z values are autoset to 0, but not sure if this is ideal.
        try:
            num_bytes_written = b_io.write(pack("<2d", *zbox))
        except StructError:
            raise ShapefileException(
                f"Failed to write elevation extremes for record {i}. Expected floats."
            )
        try:
            zs = cast(_HasZ, s).z
            num_bytes_written += b_io.write(pack(f"<{len(zs)}d", *zs))
        except StructError:
            raise ShapefileException(
                f"Failed to write elevation values for record {i}. Expected floats."
            )

        return num_bytes_written


MultiPatch_shapeTypes = frozenset([MULTIPATCH])


class MultiPatch(_HasM, _HasZ, _CanHaveParts):
    def __init__(
        self,
        *args: PointsT,
        lines: list[PointsT] | None = None,
        partTypes: list[int] | None = None,
        z: list[float] | None = None,
        m: list[float | None] | None = None,
        points: PointsT | None = None,
        parts: list[int] | None = None,
        bbox: BBox | None = None,
        mbox: MBox | None = None,
        zbox: ZBox | None = None,
        oid: int | None = None,
    ):
        if args:
            if lines:
                raise ShapefileException(
                    "Specify Either: a) positional args, or: b) the keyword arg lines. "
                    f"Not both.  Got both: {args} and {lines=}. "
                    "If this was intentional, after the other positional args, "
                    "the arg passed to lines can be unpacked (arg1, arg2, *more_args, *lines, oid=oid,...)"
                )
            lines = list(args)
        Shape.__init__(
            self,
            lines=lines,
            points=points,
            parts=parts,
            partTypes=partTypes,
            z=z,
            m=m,
            bbox=bbox,
            zbox=zbox,
            mbox=mbox,
            oid=oid,
        )

    @staticmethod
    def _read_part_types_from_byte_stream(
        b_io: ReadableBinStream, nParts: int
    ) -> Sequence[int]:
        return _Array[int]("i", unpack(f"<{nParts}i", b_io.read(nParts * 4)))

    @staticmethod
    def _write_part_types_to_byte_stream(b_io: WriteableBinStream, s: Shape) -> int:
        return b_io.write(pack(f"<{len(s.partTypes)}i", *s.partTypes))


PointM_shapeTypes = frozenset([POINTM, POINTZ])


class PointM(Point):
    def __init__(
        self,
        x: float,
        y: float,
        # same default as in Writer._shp_record (if s.shapeType in (11, 21):)
        # PyShp encodes None m values as NODATA
        m: float | None = None,
        oid: int | None = None,
    ):
        Shape.__init__(self, points=[(x, y)], m=(m,), oid=oid)

    @staticmethod
    def _read_single_point_ms_from_byte_stream(
        b_io: ReadSeekableBinStream, next_shape_pos: int
    ) -> tuple[float | None]:
        if next_shape_pos - b_io.tell() >= 8:
            (m,) = unpack("<d", b_io.read(8))
        else:
            m = NODATA
        # Measure values less than -10e38 are nodata values according to the spec
        if m >= ISDATA_LOWER_BOUND:
            return (m,)
        else:
            return (None,)

    @staticmethod
    def _write_single_point_m_to_byte_stream(
        b_io: WriteableBinStream, s: Shape, i: int
    ) -> int:
        try:
            s = cast(_HasM, s)
            m = s.m[0] if s.m else None
        except StructError:
            raise ShapefileException(
                f"Failed to write measure value for record {i}. Expected floats."
            )

        # Note: missing m values are autoset to NODATA.
        m_to_encode = m if m is not None else NODATA

        return b_io.write(pack("<1d", m_to_encode))


PolylineM_shapeTypes = frozenset([POLYLINEM, POLYLINEZ])


class PolylineM(Polyline, _HasM):
    def __init__(
        self,
        *args: PointsT,
        lines: list[PointsT] | None = None,
        parts: list[int] | None = None,
        m: Sequence[float | None] | None = None,
        points: PointsT | None = None,
        bbox: BBox | None = None,
        mbox: MBox | None = None,
        oid: int | None = None,
    ):
        if args:
            if lines:
                raise ShapefileException(
                    "Specify Either: a) positional args, or: b) the keyword arg lines. "
                    f"Not both.  Got both: {args} and {lines=}. "
                    "If this was intentional, after the other positional args, "
                    "the arg passed to lines can be unpacked (arg1, arg2, *more_args, *lines, oid=oid,...)"
                )
            lines = list(args)
        Shape.__init__(
            self,
            lines=lines,
            points=points,
            parts=parts,
            m=m,
            bbox=bbox,
            mbox=mbox,
            oid=oid,
        )


PolygonM_shapeTypes = frozenset([POLYGONM, POLYGONZ])


class PolygonM(Polygon, _HasM):
    def __init__(
        self,
        *args: PointsT,
        lines: list[PointsT] | None = None,
        parts: list[int] | None = None,
        m: list[float | None] | None = None,
        points: PointsT | None = None,
        bbox: BBox | None = None,
        mbox: MBox | None = None,
        oid: int | None = None,
    ):
        if args:
            if lines:
                raise ShapefileException(
                    "Specify Either: a) positional args, or: b) the keyword arg lines. "
                    f"Not both.  Got both: {args} and {lines=}. "
                    "If this was intentional, after the other positional args, "
                    "the arg passed to lines can be unpacked (arg1, arg2, *more_args, *lines, oid=oid,...)"
                )
            lines = list(args)
        Shape.__init__(
            self,
            lines=lines,
            points=points,
            parts=parts,
            m=m,
            bbox=bbox,
            mbox=mbox,
            oid=oid,
        )


MultiPointM_shapeTypes = frozenset([MULTIPOINTM, MULTIPOINTZ])


class MultiPointM(MultiPoint, _HasM):
    def __init__(
        self,
        *args: PointT,
        points: PointsT | None = None,
        m: Sequence[float | None] | None = None,
        bbox: BBox | None = None,
        mbox: MBox | None = None,
        oid: int | None = None,
    ):
        if args:
            if points:
                raise ShapefileException(
                    "Specify Either: a) positional args, or: b) the keyword arg points. "
                    f"Not both.  Got both: {args} and {points=}. "
                    "If this was intentional, after the other positional args, "
                    "the arg passed to points can be unpacked, e.g. "
                    " (arg1, arg2, *more_args, *points, oid=oid,...)"
                )
            points = list(args)
        Shape.__init__(
            self,
            points=points,
            m=m,
            bbox=bbox,
            mbox=mbox,
            oid=oid,
        )


PointZ_shapeTypes = frozenset([POINTZ])


class PointZ(PointM):
    def __init__(
        self,
        x: float,
        y: float,
        z: float = 0.0,
        m: float | None = None,
        oid: int | None = None,
    ):
        Shape.__init__(self, points=[(x, y)], z=(z,), m=(m,), oid=oid)

    # same default as in Writer._shp_record (if s.shapeType == 11:)
    z: Sequence[float] = (0.0,)

    @staticmethod
    def _read_single_point_zs_from_byte_stream(b_io: ReadableBinStream) -> tuple[float]:
        return unpack("<d", b_io.read(8))

    @staticmethod
    def _write_single_point_z_to_byte_stream(
        b_io: WriteableBinStream, s: Shape, i: int
    ) -> int:
        # Note: missing z values are autoset to 0, but not sure if this is ideal.
        z: float = 0.0
        # then write value

        try:
            if s.z:
                z = s.z[0]
        except StructError:
            raise ShapefileException(
                f"Failed to write elevation value for record {i}. Expected floats."
            )

        return b_io.write(pack("<d", z))


PolylineZ_shapeTypes = frozenset([POLYLINEZ])


class PolylineZ(PolylineM, _HasZ):
    def __init__(
        self,
        *args: PointsT,
        lines: list[PointsT] | None = None,
        z: list[float] | None = None,
        m: list[float | None] | None = None,
        points: PointsT | None = None,
        parts: list[int] | None = None,
        bbox: BBox | None = None,
        mbox: MBox | None = None,
        zbox: ZBox | None = None,
        oid: int | None = None,
    ):
        if args:
            if lines:
                raise ShapefileException(
                    "Specify Either: a) positional args, or: b) the keyword arg lines. "
                    f"Not both.  Got both: {args} and {lines=}. "
                    "If this was intentional, after the other positional args, "
                    "the arg passed to lines can be unpacked (arg1, arg2, *more_args, *lines, oid=oid,...)"
                )
            lines = list(args)
        Shape.__init__(
            self,
            lines=lines,
            points=points,
            parts=parts,
            z=z,
            m=m,
            bbox=bbox,
            zbox=zbox,
            mbox=mbox,
            oid=oid,
        )


PolygonZ_shapeTypes = frozenset([POLYGONZ])


class PolygonZ(PolygonM, _HasZ):
    def __init__(
        self,
        *args: PointsT,
        lines: list[PointsT] | None = None,
        parts: list[int] | None = None,
        z: list[float] | None = None,
        m: list[float | None] | None = None,
        points: PointsT | None = None,
        bbox: BBox | None = None,
        mbox: MBox | None = None,
        zbox: ZBox | None = None,
        oid: int | None = None,
    ):
        if args:
            if lines:
                raise ShapefileException(
                    "Specify Either: a) positional args, or: b) the keyword arg lines. "
                    f"Not both.  Got both: {args} and {lines=}. "
                    "If this was intentional, after the other positional args, "
                    "the arg passed to lines can be unpacked (arg1, arg2, *more_args, *lines, oid=oid,...)"
                )
            lines = list(args)
        Shape.__init__(
            self,
            lines=lines,
            points=points,
            parts=parts,
            z=z,
            m=m,
            bbox=bbox,
            mbox=mbox,
            zbox=zbox,
            oid=oid,
        )


MultiPointZ_shapeTypes = frozenset([MULTIPOINTZ])


class MultiPointZ(MultiPointM, _HasZ):
    def __init__(
        self,
        *args: PointT,
        points: PointsT | None = None,
        z: list[float] | None = None,
        m: Sequence[float | None] | None = None,
        bbox: BBox | None = None,
        mbox: MBox | None = None,
        zbox: ZBox | None = None,
        oid: int | None = None,
    ):
        if args:
            if points:
                raise ShapefileException(
                    "Specify Either: a) positional args, or: b) the keyword arg points. "
                    f"Not both. Got both: {args} and {points=}. "
                    "If this was intentional, after the other positional args, "
                    "the arg passed to points can be unpacked, e.g. "
                    " (arg1, arg2, , ..., *more_args, *points, oid=oid, ...)"
                )
            points = list(args)
        Shape.__init__(
            self,
            points=points,
            bbox=bbox,
            z=z,
            m=m,
            zbox=zbox,
            mbox=mbox,
            oid=oid,
        )


SHAPE_CLASS_FROM_SHAPETYPE: dict[int, type[NullShape | Point | _CanHaveBBox]] = {
    NULL: NullShape,
    POINT: Point,
    POLYLINE: Polyline,
    POLYGON: Polygon,
    MULTIPOINT: MultiPoint,
    POINTZ: PointZ,
    POLYLINEZ: PolylineZ,
    POLYGONZ: PolygonZ,
    MULTIPOINTZ: MultiPointZ,
    POINTM: PointM,
    POLYLINEM: PolylineM,
    POLYGONM: PolygonM,
    MULTIPOINTM: MultiPointM,
    MULTIPATCH: MultiPatch,
}


class _Record(list[RecordValue]):
    """
    A class to hold a record. Subclasses list to ensure compatibility with
    former work and to reuse all the optimizations of the builtin list.
    In addition to the list interface, the values of the record
    can also be retrieved using the field's name. For example if the dbf contains
    a field ID at position 0, the ID can be retrieved with the position, the field name
    as a key, or the field name as an attribute.

    >>> # Create a Record with one field, normally the record is created by the Reader class
    >>> r = _Record({'ID': 0}, [0])
    >>> print(r[0])
    >>> print(r['ID'])
    >>> print(r.ID)
    """

    def __init__(
        self,
        field_positions: dict[str, int],
        values: Iterable[RecordValue],
        oid: int | None = None,
    ):
        """
        A Record should be created by the Reader class

        :param field_positions: A dict mapping field names to field positions
        :param values: A sequence of values
        :param oid: The object id, an int (optional)
        """
        self.__field_positions = field_positions
        if oid is not None:
            self.__oid = oid
        else:
            self.__oid = -1
        list.__init__(self, values)

    def __getattr__(self, item: str) -> RecordValue:
        """
        __getattr__ is called if an attribute is used that does
        not exist in the normal sense. For example r=Record(...), r.ID
        calls r.__getattr__('ID'), but r.index(5) calls list.index(r, 5)
        :param item: The field name, used as attribute
        :return: Value of the field
        :raises: AttributeError, if item is not a field of the shapefile
                and IndexError, if the field exists but the field's
                corresponding value in the Record does not exist
        """
        try:
            if item == "__setstate__":  # Prevent infinite loop from copy.deepcopy()
                raise AttributeError("_Record does not implement __setstate__")
            index = self.__field_positions[item]
            return list.__getitem__(self, index)
        except KeyError:
            raise AttributeError(f"{item} is not a field name")
        except IndexError:
            raise IndexError(
                f"{item} found as a field but not enough values available."
            )

    def __setattr__(self, key: str, value: RecordValue) -> None:
        """
        Sets a value of a field attribute
        :param key: The field name
        :param value: the value of that field
        :return: None
        :raises: AttributeError, if key is not a field of the shapefile
        """
        if key.startswith("_"):  # Prevent infinite loop when setting mangled attribute
            return list.__setattr__(self, key, value)
        try:
            index = self.__field_positions[key]
            return list.__setitem__(self, index, value)
        except KeyError:
            raise AttributeError(f"{key} is not a field name")

    @overload
    def __getitem__(self, item: SupportsIndex) -> RecordValue: ...
    @overload
    def __getitem__(self, item: slice) -> list[RecordValue]: ...
    @overload
    def __getitem__(self, item: str) -> RecordValue: ...
    def __getitem__(
        self, item: SupportsIndex | slice | str
    ) -> RecordValue | list[RecordValue]:
        """
        Extends the normal list item access with
        access using a fieldname

        For example r['ID'], r[0]
        :param item: Either the position of the value or the name of a field
        :return: the value of the field
        """
        try:
            # Using | on types in Python 3.9 also raises TypeError, so
            # Union is needed, as we subsequently catch TypeError.
            return list.__getitem__(self, cast(Union[SupportsIndex, slice], item))
        except TypeError:
            try:
                index = self.__field_positions[cast(str, item)]
            except KeyError:
                index = None
        if index is not None:
            return list.__getitem__(self, index)

        raise IndexError(f'"{item}" is not a field name and not an int')

    @overload
    def __setitem__(self, key: SupportsIndex, value: RecordValue) -> None: ...
    @overload
    def __setitem__(self, key: slice, value: Iterable[RecordValue]) -> None: ...
    @overload
    def __setitem__(self, key: str, value: RecordValue) -> None: ...
    def __setitem__(
        self,
        key: SupportsIndex | slice | str,
        value: RecordValue | Iterable[RecordValue],
    ) -> None:
        """
        Extends the normal list item access with
        access using a fieldname

        For example r['ID']=2, r[0]=2
        :param key: Either the position of the value or the name of a field
        :param value: the new value of the field
        """
        ValidKVTuple = Union[
            tuple[SupportsIndex, RecordValue], tuple[slice, Iterable[RecordValue]]
        ]
        try:
            list.__setitem__(self, *cast(ValidKVTuple, (key, value)))
            return
        except TypeError:
            index = self.__field_positions.get(cast(str, key))
            if index is not None:
                list.__setitem__(self, index, cast(RecordValue, value))
                return

            raise IndexError(f"{key} is not a field name and not an int")

    @property
    def oid(self) -> int:
        """The index position of the record in the original shapefile"""
        return self.__oid

    def as_dict(self, date_strings: bool = False) -> dict[str, RecordValue]:
        """
        Returns this Record as a dictionary using the field names as keys
        :return: dict
        """
        dct = {f: self[i] for f, i in self.__field_positions.items()}
        if date_strings:
            for k, v in dct.items():
                if isinstance(v, date):
                    dct[k] = f"{v.year:04d}{v.month:02d}{v.day:02d}"
        return dct

    def __repr__(self) -> str:
        return f"Record #{self.__oid}: {list(self)}"

    def __dir__(self) -> list[str]:
        """
        Helps to show the field names in an interactive environment like IPython.
        See: http://ipython.readthedocs.io/en/stable/config/integrating.html

        :return: List of method names and fields
        """
        default = list(
            dir(type(self))
        )  # default list methods and attributes of this class
        fnames = list(
            self.__field_positions.keys()
        )  # plus field names (random order if Python version < 3.6)
        return default + fnames

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, _Record):
            if self.__field_positions != other.__field_positions:
                return False
        return list.__eq__(self, other)


class ShapeRecord:
    """A ShapeRecord object containing a shape along with its attributes.
    Provides the GeoJSON __geo_interface__ to return a Feature dictionary."""

    def __init__(self, shape: Shape | None = None, record: _Record | None = None):
        self.shape = shape
        self.record = record

    @property
    def __geo_interface__(self) -> GeoJSONFeature:
        return {
            "type": "Feature",
            "properties": None
            if self.record is None
            else self.record.as_dict(date_strings=True),
            "geometry": None
            if self.shape is None or self.shape.shapeType == NULL
            else self.shape.__geo_interface__,
        }


class Shapes(list[Optional[Shape]]):
    """A class to hold a list of Shape objects. Subclasses list to ensure compatibility with
    former work and to reuse all the optimizations of the builtin list.
    In addition to the list interface, this also provides the GeoJSON __geo_interface__
    to return a GeometryCollection dictionary."""

    def __repr__(self) -> str:
        return f"Shapes: {list(self)}"

    @property
    def __geo_interface__(self) -> GeoJSONGeometryCollection:
        # Note: currently this will fail if any of the shapes are null-geometries
        # could be fixed by storing the shapefile shapeType upon init, returning geojson type with empty coords
        collection = GeoJSONGeometryCollection(
            type="GeometryCollection",
            geometries=[shape.__geo_interface__ for shape in self if shape is not None],
        )
        return collection


class ShapeRecords(list[ShapeRecord]):
    """A class to hold a list of ShapeRecord objects. Subclasses list to ensure compatibility with
    former work and to reuse all the optimizations of the builtin list.
    In addition to the list interface, this also provides the GeoJSON __geo_interface__
    to return a FeatureCollection dictionary."""

    def __repr__(self) -> str:
        return f"ShapeRecords: {list(self)}"

    @property
    def __geo_interface__(self) -> GeoJSONFeatureCollection:
        return GeoJSONFeatureCollection(
            type="FeatureCollection",
            features=[shaperec.__geo_interface__ for shaperec in self],
        )


def _save_to_named_tmp_file(
    bytes_stream: ReadableBinStream,
    initial_bytes: bytes = b"",
    suffix: str | None = None,
) -> tempfile._TemporaryFileWrapper[bytes]:
    """Write stream to a read+write tempfile.
    Gets deleted when garbage collected.
    """
    tmp_file_obj = tempfile.NamedTemporaryFile(mode="w+b", suffix=suffix, delete=True)
    if initial_bytes:
        tmp_file_obj.write(initial_bytes)
    tmp_file_obj.write(bytes_stream.read())
    tmp_file_obj.seek(0)
    return tmp_file_obj


HTML_SIGNATURES_UC = (
    b"<!DOCTYPE",
    b"<HTML",
    b"<HEAD",
    b"<BODY",
)


class UnsuccessfulFileDownload(Warning): ...


class PossiblyCorruptFileHeader(Warning): ...


# Must be tuple of lower case strings (for str.lower.startswith(<tuple>)),
# and must not include Windows drive letters.
SUPPORTED_URL_SCHEMES = ("http", "https")
DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"


@overload
def _try_to_download_binary_file(
    urlinfo: SplitResult,
) -> tuple[bytes, ReadableBinStream]: ...
@overload
def _try_to_download_binary_file(
    urlinfo: SplitResult,
    ext: str | None,
    suppress_http_errors: bool,
    user_agent: str,
) -> tuple[bytes, ReadableBinStream | None]: ...
@overload
def _try_to_download_binary_file(
    urlinfo: SplitResult,
    ext: str | None,
    suppress_http_errors: bool,
) -> tuple[bytes, ReadableBinStream | None]: ...
def _try_to_download_binary_file(
    urlinfo: SplitResult,
    ext: str | None = None,
    suppress_http_errors: bool = False,
    user_agent: str = DEFAULT_USER_AGENT,
) -> tuple[bytes, ReadableBinStream | None]:
    """Tries to open a parsed url and download a file served from it.
    Warns if Content-Type is html and if bytes look like html
    """

    if ext is not None:
        urlinfo = urlinfo._replace(path=Path(urlinfo.path).with_suffix(ext).as_posix())

    url = urlunsplit(urlinfo)

    req = Request(
        url,
        headers={
            "User-agent": user_agent,
        },
        # Don't enforce method="GET", let urllib pick
        # whichever defaults it thinks are best,
        # to allow possible future
        # support for shapefiles via ftp or on local network addresses.
    )

    try:
        resp = urlopen(req)
    except HTTPError as e:
        msg = f"{e.msg}, {e.code} occurred when trying to open: {url}, reason: {e.reason}. "
        if not suppress_http_errors:
            e.msg = msg  # Add helpful info to the default abrupt 404 message.
            raise e
        elif ext != ".shx":
            # Technically the .shx is required for an ESRI Shapefile,
            # but it's not needed for PyShp.  It only contains indices of shapes.
            warnings.warn(msg, category=UnsuccessfulFileDownload)
        return b"", None

    content_type = resp.headers.get("Content-Type", "")
    if "text/html" in content_type:
        msg = f"Server returned HTML Content-Type: {content_type})"

        # It is preferable not to add special cases for every possible
        # hosting service, but Github is a frequent source of frustration
        # in our own tests, and there has literally been an issue open for
        # over a year to locate a shapefile downloadable from elsewhere
        # that nobody has yet answered.  So if someone requests support
        # for another service hosting a public shapefile, at least that
        # issue can finally be closed (and James can delete his Github
        # test data repo).
        if urlinfo.netloc.lower().endswith("github.com"):
            msg = f'{msg}\nAppend "?raw=true" after the file name to download from Github repos. '
        warnings.warn(msg, category=UnsuccessfulFileDownload)
        return b"", None

    initial_bytes = resp.read(40)
    if initial_bytes.upper().startswith(HTML_SIGNATURES_UC):
        msg = f"Response body appears to be HTML despite Content-Type: '{content_type}'"
        warnings.warn(msg, category=UnsuccessfulFileDownload)

    # All PyShp cares about is that the response has a .read method
    # that returns bytes.  But at the cost of importing http.client
    # we could type this stricter as tuple[bytes, HTTPResponse]:
    # "For HTTP and HTTPS URLs, this function returns a
    # http.client.HTTPResponse object slightly modified."
    return initial_bytes, cast(ReadableBinStream, resp)


def _try_get_open_constituent_file(
    file: Path,
    ext: Literal[".shp", ".shx", ".dbf"],
) -> IO[bytes] | None:
    """
    Attempts to open a .shp, .dbf or .shx file,
    with both lower case and upper case file extensions,
    and return it.  If it was not possible to open the file, None is returned.
    """
    exts = {ext, ext.upper(), ext.lower()}

    for candidate_ext in exts:
        try:
            return file.with_suffix(candidate_ext).open("rb")
        except OSError:
            pass
    return None


def ensure_within_bounds(i: int, num_records: int) -> int:
    """Provides list-like handling of a record index with a clearer
    error message if the index is out of bounds."""
    rmax = num_records - 1
    if abs(i) > rmax:
        raise IndexError(f"Shape or Record index: {i} out of range.  Max index: {rmax}")
    if i < 0:
        i = range(num_records)[i]
    return i


class ShapefileException(Exception):
    """An exception to handle shapefile specific problems."""


class dbfFileException(ShapefileException):
    """Indicates a problem with the .dbf file."""


# Use ExitStack to Support not closing opened file objects passed in e.g.(handled by some
# external context manager, or the caller manually calling .close).
#
# This will only ever hold at most one context manager.
# But an ExitStack is the right tool for the job
# when the number of context manager(s) depends on user input.
class _HasExitStack(AbstractContextManager["_HasExitStack", None]):
    def __init__(self) -> None:
        self.exit_stack = ExitStack()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self.exit_stack.close()


FileProtoT = TypeVar("FileProtoT")


class _FileObjChecker(_HasExitStack, Generic[FileProtoT]):
    """Base class that verifies its file-like object."""

    @property
    @abc.abstractmethod
    def FileProto(self) -> type[FileProtoT]: ...

    @property
    @abc.abstractmethod
    def new_file_obj_mode(self) -> Literal["rb", "w+b"]: ...

    @property
    @abc.abstractmethod
    def ext(self) -> Literal[".shp", ".shx", ".dbf", None]: ...

    ExceptionClass = ShapefileException

    def __init__(
        self,
        file: str | os.PathLike[Any] | FileProtoT | None,
    ):
        super().__init__()
        if self.ext is None:
            return
        self._file: Path | FileProtoT | None
        if isinstance(file, (str, os.PathLike)):
            self._file = Path(file).with_suffix(self.ext)
        else:
            self._file = file

    def _ensure_file_obj(
        self,
        f: str | os.PathLike[Any] | FileProtoT | None = None,
    ) -> FileProtoT:
        # Also used by Writer on constituent files self._shp & self._shx

        f = f or self._file

        if isinstance(f, (str, os.PathLike)):
            path = Path(f)
            dir_ = path.parent
            if dir_:
                dir_.mkdir(exist_ok=True, parents=True)
            fp = path.open(self.new_file_obj_mode)

            # Only push files created here to the exit stack.
            # The user must close their own file objects.
            self.exit_stack.enter_context(fp)
            return cast(FileProtoT, fp)

        # See Minor hack below.
        if isinstance(f, self.FileProto):
            return f

        # Ugly, but perhaps needed to avoid weird Python 3.14
        # specific bug in run_benchmarks.py on Windows
        # if (
        #     (attrs := getattr(self.FileProto, "__protocol_attrs__", None))
        #     and all(hasattr(f, attr) for attr in attrs)
        # ):
        #     return f

        raise self.ExceptionClass(
            f"Unsupported file-like object: {f}.  Must satisfy: {self.FileProto}"
        )


# Minor hack.  Relies on Protocols being ABC subclasses.
# They are currently ABCs anyway, so why not use that
# for something useful?
#
# tempfile.NamedTemporaryFile is a dynamic wrapper
# https://github.com/python/cpython/blob/2dd91d2b92a6c74d78cd3385ede328190cd8eaa9/Lib/tempfile.py#L510
# so normal (naive) isinstance checks of tempfile.NamedTemporaryFiles
# against @runtime_checkable Protocols are not possible.
ReadSeekableBinStream.register(tempfile._TemporaryFileWrapper)
WriteSeekableBinStream.register(tempfile._TemporaryFileWrapper)


class _HasCheckedReadableFile(_FileObjChecker[ReadSeekableBinStream]):
    def __init__(self, file: str | PathLike[Any] | ReadSeekableBinStream):

        super().__init__(file)

        self.file.seek(0, 2)  # offset=0, whence = 2 => EOF
        self.file_size_B = self.file.tell()
        self.file.seek(0)

    @functools.cached_property
    def file(self) -> ReadSeekableBinStream:
        return self._ensure_file_obj()


class DbfReader(_HasCheckedReadableFile):
    """Reads a dbf file's fields and records."""

    FileProto = ReadSeekableBinStream
    new_file_obj_mode = "rb"
    ext = ".dbf"
    ExceptionClass = dbfFileException

    def __init__(
        self,
        dbf: str | PathLike[Any] | ReadSeekableBinStream,
        *,
        encoding: str = "utf-8",
        encodingErrors: str = "strict",
    ):
        super().__init__(file=dbf)

        self.encoding = encoding
        self.encodingErrors = encodingErrors

        self.fields: list[Field] = []
        self.__fieldLookup: dict[str, int] = {}

        self._dbfHeader()

    def __len__(self) -> int:
        """Returns the number of records in the .dbf file."""
        return self.numRecords

    def _dbfHeader(self) -> None:
        """Reads a dbf header. Xbase-related code borrows heavily from
        ActiveState Python Cookbook Recipe 362715 by Raymond Hettinger
        """

        # read relevant header parts
        self.file.seek(0)
        self.numRecords, self.__dbfHdrLength, self._record_length = cast(
            tuple[int, int, int], unpack("<xxxxLHH20x", self.file.read(32))
        )

        # read fields
        numFields = (self.__dbfHdrLength - 33) // 32
        for __field in range(numFields):
            encoded_field_tuple: tuple[bytes, bytes, int, int] = unpack(
                "<11sc4xBB14x", self.file.read(32)
            )
            encoded_name, encoded_type_char, size, decimal = encoded_field_tuple

            if b"\x00" in encoded_name:
                idx = encoded_name.index(b"\x00")
            else:
                idx = len(encoded_name) - 1
            encoded_name = encoded_name[:idx]
            name = encoded_name.decode(self.encoding, self.encodingErrors)
            name = name.lstrip()

            field_type = FIELD_TYPE_ALIASES[encoded_type_char]

            self.fields.append(Field(name, field_type, size, decimal))
        terminator = self.file.read(1)
        if terminator != b"\r":
            raise ShapefileException(
                "Shapefile dbf header lacks expected terminator. (likely corrupt?)"
            )

        # insert deletion field at start
        self.fields.insert(0, Field("DeletionFlag", FieldType.C, 1, 0))

        # store all field positions for easy lookups
        # note: fieldLookup gives the index position of a field inside Reader.fields
        self.__fieldLookup = {f[0]: i for i, f in enumerate(self.fields)}

        # by default, read all fields except the deletion flag, hence "[1:]"
        # note: recLookup gives the index position of a field inside a _Record list
        fieldnames = [f[0] for f in self.fields[1:]]
        __fieldTuples, recLookup, recStruct = self._record_fields(fieldnames)
        self.__fullRecStruct = recStruct
        self.__fullRecLookup = recLookup

    def _record_fmt(self, fields: Container[str] | None = None) -> tuple[str, int]:
        """Calculates the format and size of a .dbf record. Optional 'fields' arg
        specifies which fieldnames to unpack and which to ignore. Note that this
        always includes the DeletionFlag at index 0, regardless of the 'fields' arg.
        """
        structcodes = [f"{fieldinfo.size}s" for fieldinfo in self.fields]
        if fields is not None:
            # only unpack specified fields, ignore others using padbytes (x)
            structcodes = [
                code
                if fieldinfo.name in fields
                or fieldinfo.name == "DeletionFlag"  # always unpack delflag
                else f"{fieldinfo.size}x"
                for fieldinfo, code in zip(self.fields, structcodes)
            ]
        fmt = "".join(structcodes)
        fmt_size = calcsize(fmt)
        # total size of fields should add up to recordlength from the header
        while fmt_size < self._record_length:
            # if not, pad byte until reaches recordlength
            fmt += "x"
            fmt_size += 1
        return (fmt, fmt_size)

    def _record_fields(
        self, fields: Iterable[str] | None = None
    ) -> tuple[list[Field], dict[str, int], Struct]:
        """Returns the necessary info required to unpack a record's fields,
        restricted to a subset of fieldnames 'fields' if specified.
        Returns a list of field info tuples, a name-index lookup dict,
        and a Struct instance for unpacking these fields. Note that DeletionFlag
        is not a valid field.
        """
        if fields is not None:
            # restrict info to the specified fields
            # first ignore repeated field names (order doesn't matter)
            unique_fields = list(set(fields))
            # get the struct
            fmt, __fmt_size = self._record_fmt(fields=unique_fields)
            recStruct = Struct(fmt)
            # make sure the given fieldnames exist
            for name in unique_fields:
                if name not in self.__fieldLookup or name == "DeletionFlag":
                    raise ValueError(f'"{name}" is not a valid field name')
            # fetch relevant field info tuples
            fieldTuples = []
            for fieldinfo in self.fields[1:]:
                name = fieldinfo[0]
                if name in unique_fields:
                    fieldTuples.append(fieldinfo)
            # store the field positions
            recLookup = {f[0]: i for i, f in enumerate(fieldTuples)}
        else:
            # use all the dbf fields
            fieldTuples = self.fields[1:]  # sans deletion flag
            recStruct = self.__fullRecStruct
            recLookup = self.__fullRecLookup
        return fieldTuples, recLookup, recStruct

    def _record(
        self,
        fieldTuples: list[Field],
        recLookup: dict[str, int],
        recStruct: Struct,
        oid: int | None = None,
    ) -> _Record | None:
        """Reads and returns a dbf record row as a list of values. Requires specifying
        a list of field info Field namedtuples 'fieldTuples', a record name-index dict 'recLookup',
        and a Struct instance 'recStruct' for unpacking these fields.

        None is returned for 'deleted' records (those with their deletion flag marked).
        """
        # The only format chars in from self._record_fmt, in recStruct from _record_fields,
        # are s and x (ascii encoded str and pad byte) so everything in recordContents is bytes
        # https://docs.python.org/3/library/struct.html#format-characters
        recordContents = recStruct.unpack(self.file.read(recStruct.size))

        # deletion flag field is always unpacked as first value (see _record_fmt)
        if recordContents[0] != b" ":
            # deleted record
            return None

        # drop deletion flag from values
        recordContents = recordContents[1:]

        # check that values match fields
        if len(fieldTuples) != len(recordContents):
            raise ShapefileException(
                f"Number of record values ({len(recordContents)}) is different from the requested "
                f"number of fields ({len(fieldTuples)})"
            )

        # parse each value
        record = []
        for (__name, typ, __size, decimal), value in zip(fieldTuples, recordContents):
            if typ is FieldType.N or typ is FieldType.F:
                # numeric or float: number stored as a string, right justified, and padded with blanks to the width of the field.
                value = value.split(b"\0")[0]
                value = value.replace(b"*", b"")  # QGIS NULL is all '*' chars
                if value == b"":
                    value = None
                elif decimal:
                    try:
                        value = float(value)
                    except ValueError:
                        # not parseable as float, set to None
                        value = None
                else:
                    # force to int
                    try:
                        # first try to force directly to int.
                        # forcing a large int to float and back to int
                        # will lose information and result in wrong nr.
                        value = int(value)
                    except ValueError:
                        # forcing directly to int failed, so was probably a float.
                        try:
                            value = int(float(value))
                        except ValueError:
                            # not parseable as int, set to None
                            value = None
            elif typ is FieldType.D:
                # date: 8 bytes - date stored as a string in the format YYYYMMDD.
                if (
                    not value.replace(b"\x00", b"")
                    .replace(b" ", b"")
                    .replace(b"0", b"")
                ):
                    # dbf date field has no official null value
                    # but can check for all hex null-chars, all spaces, or all 0s (QGIS null)
                    value = None
                else:
                    try:
                        # return as python date object
                        y, m, d = int(value[:4]), int(value[4:6]), int(value[6:8])
                        value = date(y, m, d)
                    except (TypeError, ValueError):
                        # if invalid date, just return as unicode string so user can decimalde
                        value = str(value.strip())
            elif typ is FieldType.L:
                # logical: 1 byte - initialized to 0x20 (space) otherwise T or F.
                if value == b" ":
                    value = None  # space means missing or not yet set
                else:
                    if value in b"YyTt1":
                        value = True
                    elif value in b"NnFf0":
                        value = False
                    else:
                        value = None  # unknown value is set to missing
            else:
                value = value.decode(self.encoding, self.encodingErrors)
                value = value.strip().rstrip(
                    "\x00"
                )  # remove null-padding at end of strings
            record.append(value)

        return _Record(recLookup, record, oid)

    def record(self, i: int = 0, fields: list[str] | None = None) -> _Record | None:
        """Returns a specific dbf record based on the supplied index.
        To only read some of the fields, specify the 'fields' arg as a
        list of one or more fieldnames.


        Returns None if record's deletion flag is marked.
        """
        i = ensure_within_bounds(i, self.numRecords)
        recSize = self._record_length
        self.file.seek(0)
        self.file.seek(self.__dbfHdrLength + (i * recSize))
        fieldTuples, recLookup, recStruct = self._record_fields(fields)
        return self._record(
            oid=i, fieldTuples=fieldTuples, recLookup=recLookup, recStruct=recStruct
        )

    def records(
        self,
        fields: list[str] | None = None,
        start: int = 0,
        stop: int | None = None,
        deleted_as_None: bool = False,
    ) -> list[_Record | None]:
        """Returns a list of records in a dbf file.
        To only read some of the fields, specify the 'fields' arg as a
        list of one or more fieldnames.
        By default returns all records.  Otherwise, specify start
        (default: 0) or stop (default: number_of_records)
        to only yield record numbers i, where
        start <= i < stop, (or
        start <= i < number_of_records + stop
        if stop < 0).

        Excludes 'deleted' records (those whose deletion flag is marked).
        Set deleted_as_None=True to insert None for these, to preserve
        the indexing, as for DbfReader.record
        """
        return [
            record for record in self.iterRecords(fields, start, stop, deleted_as_None)
        ]

    def iterRecords(
        self,
        fields: list[str] | None = None,
        start: int = 0,
        stop: int | None = None,
        deleted_as_None: bool = False,
    ) -> Iterator[_Record | None]:
        """Returns a generator of records in a dbf file.
        Useful for large shapefiles or dbf files.
        To only read some of the fields, specify the 'fields' arg as a
        list of one or more fieldnames.
        By default yields all records.  Otherwise, specify start
        (default: 0) or stop (default: number_of_records)
        to only yield record numbers i, where
        start <= i < stop, (or
        start <= i < number_of_records + stop
        if stop < 0).

        Excludes 'deleted' records (those whose deletion flag is marked).
        Set deleted_as_None=True to insert None for these, to preserve
        the indexing, as for DbfReader.record
        """
        if not isinstance(self.numRecords, int):
            raise ShapefileException(
                "Error when reading number of Records in dbf file header"
            )

        # Exit early if there are no records
        if self.numRecords == 0:
            return

        start = ensure_within_bounds(start, self.numRecords)
        if stop is None:
            stop = self.numRecords
        elif abs(stop) > self.numRecords:
            raise IndexError(
                f"abs(stop): {abs(stop)} exceeds number of records: {self.numRecords}."
            )
        elif stop < 0:
            stop = range(self.numRecords)[stop]
        recSize = self._record_length
        self.file.seek(self.__dbfHdrLength + (start * recSize))
        fieldTuples, recLookup, recStruct = self._record_fields(fields)
        for i in range(start, stop):
            r = self._record(
                oid=i, fieldTuples=fieldTuples, recLookup=recLookup, recStruct=recStruct
            )
            if r is not None or deleted_as_None:
                yield r


class ShxReader(_HasCheckedReadableFile):
    """Reads an shx file (a file of file positions
    of shapes in a .shp file).
    """

    FileProto = ReadSeekableBinStream
    new_file_obj_mode = "rb"
    ext = ".shx"

    def __init__(
        self,
        shx: str | PathLike[Any] | ReadSeekableBinStream,
    ):
        super().__init__(file=shx)
        self.numShapes: int
        self._shxHeader()
        self._shxRecords_16bw: _Array[int] | None = None

    def _shxHeader(self) -> None:
        """Reads the header information from a .shx file."""
        # File length (16-bit word * 2 = bytes) - header length
        self.file.seek(24)
        shx_records_length_B = (unpack(">i", self.file.read(4))[0] * 2) - 100
        self.numShapes = shx_records_length_B // 8

    @functools.cache
    def _read_shxRecords(self) -> None:
        """Reads the shape offset positions from a .shx file"""
        # Jump to the first record.
        self.file.seek(100)
        # Each index record consists of two nums.  We only want the first one
        self._shxRecords_16bw = _Array[int]("i", self.file.read(2 * self.numShapes * 4))
        if sys.byteorder != "big":
            self._shxRecords_16bw.byteswap()

    # Only read .shx file body lazily
    @functools.cached_property
    def offsets(self) -> list[int]:
        self._read_shxRecords()
        # Convert from offsets in 16b Words to Bytes (8b).
        offsets_ = [2 * el for el in cast(_Array[int], self._shxRecords_16bw)[::2]]
        assert len(offsets_) == self.numShapes, f"{self.numShapes=}, {len(offsets_)=}"
        return offsets_

    @functools.cached_property
    def shape_lengths_B(self) -> list[int]:
        self._read_shxRecords()
        return [2 * x for x in cast(_Array[int], self._shxRecords_16bw)[1::2]]


ShapeHeaderInfoT = tuple[int, int, int]


class ShpReader(_HasCheckedReadableFile):
    """Reads an shp file."""

    FileProto = ReadSeekableBinStream
    new_file_obj_mode = "rb"
    ext = ".shp"

    def __init__(
        self,
        shp: str | PathLike[Any] | ReadSeekableBinStream,
    ):
        super().__init__(file=shp)
        # self.bbox: BBox
        # self.zbox: ZBox
        # self.mbox: MBox
        self.shapeType: int
        self._shpHeader()
        self.headers_cache: list[ShapeHeaderInfoT] = []

    @property
    def shapeTypeName(self) -> str:
        return SHAPETYPE_LOOKUP[self.shapeType]

    def _shpHeader(self) -> None:
        """Reads the header information from a .shp file."""

        # File length (16-bit word * 2 = bytes)
        self.file.seek(24)
        self.shp_file_size_B = unpack(">i", self.file.read(4))[0] * 2
        # Shape type
        self.file.seek(32)
        self.shapeType = unpack("<i", self.file.read(4))[0]
        # The shapefile's bounding box (lower left, upper right)
        # self.bbox: BBox = tuple(_Array("d", unpack("<4d", shp.read(32))))
        self.bbox = BBox(*unpack("<4d", self.file.read(32)))
        # xmin, ymin, xmax, ymax = unpack("<4d", shp.read(32))
        # self.bbox = BBox(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)
        # Elevation
        # self.zbox: ZBox = tuple(_Array("d", unpack("<2d", shp.read(16))))
        self.zbox = ZBox(*unpack("<2d", self.file.read(16)))
        # zmin, zmax = unpack("<2d", shp.read(16))
        # self.zbox = ZBox(zmin=zmin, zmax=zmax)
        # Measure
        # Measure values less than -1e38 are nodata values according to the spec
        self.mbox = MBox(
            *(
                float(m_bound) if m_bound >= ISDATA_LOWER_BOUND else None
                for m_bound in unpack("<2d", self.file.read(16))
            )
        )

        if self.file_size_B != self.shp_file_size_B:
            file_name = getattr(self.file, "name", ".shp")
            msg = (
                f"Declared file size in {file_name} header: {self.shp_file_size_B} "
                f"not equal to actual file size: {self.file_size_B} "
                "(both in bytes)"
            )
            warnings.warn(msg, category=PossiblyCorruptFileHeader)

    @functools.cache  # Only read through the shape headers (e.g. on disk), at most once.
    def _headers_cached_gen(self) -> Iterator[ShapeHeaderInfoT]:

        header_pos = 100  # after .shp file header, before start of first shape's header

        while header_pos < self.file_size_B:
            self.file.seek(header_pos)
            # Unpack the shape header only
            recNum, recLength_16bw = unpack(">2i", self.file.read(8))

            shp_length_B = 2 * recLength_16bw
            shape_header_data = header_pos, shp_length_B, recNum
            self.headers_cache.append(shape_header_data)
            yield shape_header_data

            # Calculate next shape header position
            header_pos += 8 + shp_length_B

    def shape_header(self, index: int) -> ShapeHeaderInfoT:
        while index < 0 or index >= len(self.headers_cache):
            try:
                next(self._headers_cached_gen())
            except StopIteration:
                break
        return self.headers_cache[index]

    def headers_gen(self) -> Iterator[ShapeHeaderInfoT]:
        yield from self.headers_cache
        yield from self._headers_cached_gen()

    def cache_all_headers(self) -> None:
        self.shape_header(-1)

    @functools.cached_property
    def offsets(self) -> list[int]:
        return [header[0] for header in self.headers_gen()]

    def shape(
        self,
        index: int,
        offset: int | None = None,
        shape_len_B: int | None = None,
        bbox: BBox | None = None,
    ) -> Shape | None:
        """Returns the Shape at a given index, or None if it is outside the
        specified bbox.  If a corresponding .shx file is available, it
        is faster to provide offset and shape_len_B from it, e.g. via the main
        Shapefile Reader class.  Otherwise offsets (and record numbers
        and shape lengths) will be read on the fly as needed, and
        cached in memory.
        """
        if offset is None or shape_len_B is None:
            offset, shape_len_B, _recNum = self.shape_header(index)
        # Seek to 8B after the offset (past the shape's 8B header).
        self.file.seek(offset + 8)
        shape = self._shape(shape_len_B=shape_len_B, oid=index, bbox=bbox)
        return shape

    def _shape(
        self,
        shape_len_B: int,  # Excluding header
        oid: int | None = None,
        bbox: BBox | None = None,
    ) -> Shape | None:
        """Returns geometry for a single shape (or None if
        it is outside the specified bbox).

        Requires the size in B of the shaps, and the .shp
        file to have been .seeked to the start of the shape
        (immediately after the shape's header).
        """

        # Read entire record into memory to avoid having to call
        # seek on the file afterwards
        b_io: ReadSeekableBinStream = io.BytesIO(self.file.read(shape_len_B))
        # To avoid a .seek for the next shape's header (where we are already)
        b_io.seek(0)

        try:
            shapeType = unpack("<i", b_io.read(4))[0]
        except StructError as e:
            raise e

        ShapeClass = SHAPE_CLASS_FROM_SHAPETYPE[shapeType]
        shape = ShapeClass.from_byte_stream(
            shapeType, b_io, shape_len_B, oid=oid, bbox=bbox
        )

        # Seek to the end of this record as defined by the record header because
        # the shapefile spec doesn't require the actual content to meet the header
        # definition.  Probably allowed for lazy feature deletion.
        # self.file.seek(next_shape_pos)

        return shape

    def shapes(
        self,
        shape_lengths_B: list[int] | None = None,
        bbox: list[float] | tuple[float, float, float, float] | BBox | None = None,
    ) -> Shapes:
        """Returns all shapes in file.
        To only read shapes within a given spatial region, specify the 'bbox'
        arg as a list or tuple of xmin,ymin,xmax,ymax.
        """
        return Shapes(
            self.iterShapes(
                shape_lengths_B=shape_lengths_B,
                bbox=BBox(*bbox) if bbox else None,
            )
        )

    def iterShapes(
        self,
        shape_lengths_B: list[int] | None = None,
        bbox: BBox | None = None,
        outside_bbox_as_None: bool = False,
    ) -> Iterator[Shape | None]:
        """Returns a generator of shapes in a shapefile (or None for shapes
        outside a specified bbox). Useful for handling large shapefiles.
        bbox should be a tuple or list containing xmin,ymin,xmax,ymax.
        """

        bbox = BBox(*bbox) if bbox is not None else None

        # Found shapefiles which report incorrect
        # shp file length in the header. Can't trust
        # that so we seek to the end of the file
        # and figure it out.
        # self.file.seek(0, 2)
        # file_size_B = self.file.tell()
        if shape_lengths_B is not None:
            pos = 108  # Skip first shape's header
            # Iterate exactly the number of shapes as shape
            # lengths were provided for, e.g. from shx header
            for i, shape_len_B in enumerate(shape_lengths_B):
                self.file.seek(pos)
                shape = self._shape(shape_len_B=shape_len_B, oid=i, bbox=bbox)
                if shape is not None or outside_bbox_as_None:
                    yield shape
                pos += shape_len_B + 8

            # MAYBE: check if more left of file or exit early?
            return

        # No shx file, unknown nr of shapes
        # Instead iterate until reach end of file
        # Calculate the offset indices during iteration
        for i, (pos, shape_len_B, _recNum) in enumerate(self.headers_gen()):
            self.file.seek(pos + 8)  # Skip the shape's 8 byte header
            shape = self._shape(shape_len_B=shape_len_B, oid=i, bbox=bbox)
            # # pos = self.file.tell()
            # pos += num_bytes
            if shape is not None or outside_bbox_as_None:
                yield shape

        n = i + 1  # num shapes yielded, having iterated over entire shp file.
        assert n == len(self.headers_cache), f"{n=}, {len(self.headers_cache)=}"


class _NoShpSentinel:
    """For use as a default value for shp to preserve the
    behaviour (from when all keyword args were gathered
    in the **kwargs dict) in case someone explictly
    called Reader(shp=None) to load self.shx.
    """


_NO_SHP_SENTINEL = _NoShpSentinel()


class Reader(_HasExitStack):
    """Reads the three files of a shapefile as a unit or
    separately.  If one of the three files (.shp, .shx,
    .dbf) is missing no exception is thrown until you try
    to call a method that depends on that particular file.
    The .shx index file is used if available for efficiency
    but is not required to read the geometry from the .shp
    file. If present, the "shapefile_path" argument in the
    constructor must be a string, path or otherwise satisfy
    os.PathLike.  It is the name of the file you want to open,
    and can be the path to a shapefile on a local filesystem,
    inside a zipfile, or a url.

    You can instantiate a Reader without specifying a shapefile
    and then specify one later with the load() method.

    Only the shapefile headers are read upon loading. Content
    within each file is only accessed when required and as
    efficiently as possible. Shapefiles are usually not large
    but they can be.
    """

    FileProto = ReadSeekableBinStream
    new_file_obj_mode = "rb"
    ext = ".shp"
    ExceptionClass = ShapefileException

    def __init__(
        self,
        shapefile_path: str | PathLike[Any] = "",
        /,
        *,
        encoding: str = "utf-8",
        encodingErrors: str = "strict",
        shp: _NoShpSentinel | BinaryFileT | None = _NO_SHP_SENTINEL,
        shx: BinaryFileT | None = None,
        dbf: BinaryFileT | None = None,
        # Keep kwargs even though unused, to preserve PyShp 2.4 API
        **kwargs: Any,
    ):
        super().__init__()
        # Store encoding info to use if lazy loading DbfReader later.
        self.encoding = encoding
        self.encodingErrors = encodingErrors
        self._shp = None
        self._shx = None
        self._dbf = None
        self.shapeName = "Not specified"
        self.numShapes: int = 0
        self.path: str | os.PathLike[Any] | None = None
        # See if a shapefile name was passed as the first argument
        if shapefile_path:
            if not isinstance(shapefile_path, (str, os.PathLike)):
                raise TypeError(
                    f"Unsupported shapefile path argument type: {type(shapefile_path)}. "
                    "The first arg of Reader must be a str or pathlib.Path"
                    " (or satisfy os.PathLike). "
                )
            discarded_kwargs = {}
            if shp not in (None, _NO_SHP_SENTINEL):
                discarded_kwargs["shp"] = shp
            if shx is not None:
                discarded_kwargs["shx"] = shx
            if dbf is not None:
                discarded_kwargs["dbf"] = dbf
            if discarded_kwargs:
                raise TypeError(
                    "Please be specific about the shapefile you want to load. "
                    f"Got: {shapefile_path}, plus the following unusable "
                    " kwargs: {discarded_kwargs} which previous versions of PyShp ignored. \n"
                    "Only either: i) exactly one positional arg \n"
                    "         or: ii) one or both of shp and dbf, optionally plus shx kwargs\n"
                    "is currently supported.  All other kwargs may be set (or not). "
                )
            self.path = shapefile_path

            if isinstance(self.path, str):
                # Try to parse to a supported URL first, as
                # because pathlib.Path parses URLs like relative file paths
                # (Path.resolve even returns an absolute one from one, which
                # could even exist on a Posix file system if the user has a dir
                # called "https:").
                url_info = urlsplit(self.path)
                if (
                    url_info.netloc
                    and url_info.scheme
                    and (
                        not IS_WINDOWS or not Path(f"{url_info.scheme}:").is_dir()
                    )  # scheme != drive letter
                    and url_info.scheme.lower().startswith(SUPPORTED_URL_SCHEMES)
                ):
                    # i) ".zip" in the domain name no longer implies it's a url
                    # to a .zip file (e.g. www.zipfiles.com/unzipped_shapefile.shp).
                    # ii) Paths to specific shapefiles within zip files from URLs not supported.
                    if Path(url_info.path).suffix.lower() == ".zip":
                        zipfileobj = self._download_binary_file_from_url(
                            url_info,
                            ".zip",
                            suppress_http_errors=False,
                        )
                        if zipfileobj is None:
                            raise ShapefileException("Error downloading: {self.path}")
                        self._load_from_zipfileobj(zipfileobj)
                    else:
                        self._load_from_url(url_info)
                        # Raises ShapefileException if not self._shp or self._dbf
                    return

            path = Path(self.path).resolve()
            paths = [path]
            paths.extend(path.parents)
            # Checking path.anchor != "" (e.g. "/" or r"c:\") because Path("https://...").parents[-1] == Path(".")
            # Only test paths[-1].is_dir() because later path dirs could be inside a zip file.
            if path.anchor and paths[-1].is_dir():
                zippath = next(
                    (
                        p
                        for p in reversed(paths)
                        if p.suffix.lower() == ".zip" and p.is_file()
                    ),
                    None,
                )
                if zippath is not None:
                    self._load_from_local_zip_file(path, zippath)
                    # Raises ShapefileException if not self._shp or self._dbf
                    return

            self.load(path)
            # Raises ShapefileException if not self._shp or self._dbf
            #
            return

        if shp is not _NO_SHP_SENTINEL:
            shp = cast(Union[BinaryFileT, None], shp)
            self._shp = self._seek_0_on_file_obj_wrap_or_open_from_name(".shp", shp)
            self._shx = self._seek_0_on_file_obj_wrap_or_open_from_name(".shx", shx)

        self._dbf = self._seek_0_on_file_obj_wrap_or_open_from_name(".dbf", dbf)

        # Load the files
        if self._shp:
            self._get_shp_reader()
        if self._dbf:
            self._get_dbf_reader()
        if self._shx:
            self._get_shx_reader()

    @functools.cache
    def _get_shp_reader(self) -> ShpReader:
        if self._shp is None:
            raise ShapefileException(
                "ShpReader requires a .shp file or file-like object."
            )
        shp_reader = ShpReader(
            shp=self._shp,
        )
        return shp_reader

    @functools.cache
    def _get_shx_reader(self) -> ShxReader:
        if self._shx is None:
            raise ShapefileException(
                "ShxReader requires a .shx file or file-like object."
            )
        shx_reader = ShxReader(
            shx=self._shx,
        )
        self.numShapes = shx_reader.numShapes
        return shx_reader

    @functools.cache
    def _get_dbf_reader(self) -> DbfReader:
        if self._dbf is None:
            raise ShapefileException(
                "DbfReader requires a .dbf file or file-like object."
            )
        return DbfReader(
            dbf=self._dbf,
            encoding=self.encoding,
            encodingErrors=self.encodingErrors,
        )

    @property
    def shp_reader(self) -> ShpReader:
        return self._get_shp_reader()

    @property
    def shx_reader(self) -> ShxReader:
        return self._get_shx_reader()

    @property
    def dbf_reader(self) -> DbfReader:
        return self._get_dbf_reader()

    # Simple references to the 3 constituent file objects for backwards compatibility.
    @property
    def shp(self) -> ReadSeekableBinStream:
        return self.shp_reader.file

    @property
    def shx(self) -> ReadSeekableBinStream:
        return self.shx_reader.file

    @property
    def dbf(self) -> ReadSeekableBinStream:
        return self.dbf_reader.file

    @property
    def _offsets(self) -> list[int]:
        if self._shx:
            return self.shx_reader.offsets
        return self.shp_reader.offsets

    @property
    def shapeTypeName(self) -> str:
        return self.shp_reader.shapeTypeName

    @property
    def shapeType(self) -> int:
        return self.shp_reader.shapeType

    @property
    def bbox(self) -> BBox:
        return self.shp_reader.bbox

    @property
    def mbox(self) -> MBox:
        return self.shp_reader.mbox

    @property
    def zbox(self) -> ZBox:
        return self.shp_reader.zbox

    @property
    def numRecords(self) -> int | None:
        if self._dbf is None:
            return None
        return self.dbf_reader.numRecords

    @property
    def fields(self) -> list[Field]:
        return self.dbf_reader.fields

    def record(self, i: int = 0, fields: list[str] | None = None) -> _Record | None:
        return self.dbf_reader.record(i, fields)

    def records(
        self,
        fields: list[str] | None = None,
        start: int = 0,
        stop: int | None = None,
        deleted_as_None: bool = False,
    ) -> list[_Record | None]:
        return self.dbf_reader.records(fields, start, stop, deleted_as_None)

    def iterRecords(
        self,
        fields: list[str] | None = None,
        start: int = 0,
        stop: int | None = None,
        deleted_as_None: bool = False,
    ) -> Iterator[_Record | None]:
        return self.dbf_reader.iterRecords(fields, start, stop, deleted_as_None)

    def _seek_0_on_file_obj_wrap_or_open_from_name(
        self,
        ext: Literal[".shp", ".shx", ".dbf"],
        file: BinaryFileT | None,
    ) -> None | IO[bytes]:
        if file is None:
            return None

        if isinstance(file, (str, PathLike)):
            file_obj = _try_get_open_constituent_file(Path(file), ext)
            if file_obj is not None:
                self.exit_stack.enter_context(file_obj)
            return file_obj

        if hasattr(file, "read"):
            # Copy if required
            try:
                file.seek(0)
                return file
            except (NameError, io.UnsupportedOperation):
                # Read the whole file into a seekable wrapper.
                return io.BytesIO(file.read())

        raise ShapefileException(
            f"Could not load shapefile constituent file from: {file}"
        )

    def _download_binary_file_from_url(
        self,
        urlinfo: SplitResult,
        ext: Literal[".shp", ".shx", ".dbf", ".zip"],
        suppress_http_errors: bool = True,
    ) -> tempfile._TemporaryFileWrapper[bytes] | None:
        sniffed_bytes, resp = _try_to_download_binary_file(
            urlinfo=urlinfo,
            ext=ext,
            suppress_http_errors=suppress_http_errors,
        )
        if resp is None:
            return None
        # Use tempfile as source for url data.
        fileobj = _save_to_named_tmp_file(resp, initial_bytes=sniffed_bytes)
        return fileobj

    def _load_from_url(self, urlinfo: SplitResult) -> None:
        # Shapefile is from a url
        # Download each file to temporary path and treat as normal shapefile path
        self._shp = self._download_binary_file_from_url(urlinfo, ".shp")
        self._shx = self._download_binary_file_from_url(urlinfo, ".shx")
        self._dbf = self._download_binary_file_from_url(urlinfo, ".dbf")

        shp_or_dbf_loaded = False
        if self._shx is not None:
            self.exit_stack.enter_context(self._shx)
        if self._shp is not None:
            self.exit_stack.enter_context(self._shp)
            shp_or_dbf_loaded = True
        if self._dbf is not None:
            self.exit_stack.enter_context(self._dbf)
            shp_or_dbf_loaded = True

        if not shp_or_dbf_loaded:
            raise ShapefileException(
                f"Failed to download .shp or .dbf from: {urlunsplit(urlinfo)}"
            )

    def _load_file_from_zip_to_tmp_file(
        self,
        archive: zipfile.ZipFile,
        file: Path,
        ext: Literal[".shp", ".shx", ".dbf"],
    ) -> tempfile._TemporaryFileWrapper[bytes] | None:
        for cased_ext in {ext.lower(), ext.upper(), ext}:
            try:
                member = archive.open(file.with_suffix(cased_ext).as_posix())
            except (OSError, KeyError):
                continue
            # Use read+write tempfile as source for member data.
            fileobj = _save_to_named_tmp_file(member)
            self.exit_stack.enter_context(fileobj)
            return fileobj
        return None

    def _load_from_local_zip_file(
        self,
        path: Path,
        zippath: Path,
    ) -> None:

        shapefile: Path | None

        if path != zippath:
            more_zipfile_parents = [
                parent
                for parent in path.relative_to(zippath).parents
                if parent.suffix.lower() == ".zip"
            ]
            if more_zipfile_parents:
                warnings.warn(
                    f"Reading from multiple nested zipfiles is not supported. "
                    "Multiple path segments requested within zip file, that "
                    f"also look like zip files: {more_zipfile_parents}. "
                    "Trying to open Shapefile at: {path} anyway "
                )
            shapefile = path.relative_to(zippath)
        else:
            shapefile = None

        with open(zippath, mode="rb") as zipfileobj:
            self._load_from_zipfileobj(zipfileobj, shapefile)

    def _load_from_zipfileobj(
        self,
        zipfileobj: tempfile._TemporaryFileWrapper[bytes] | io.BufferedReader,
        shapefile: Path | None = None,
    ) -> None:
        # Open the zipfile archive
        with zipfile.ZipFile(zipfileobj, "r") as archive:
            if shapefile is None:
                # Only the zipfile path is given
                # Inspect zipfile contents to find the full shapefile path
                constituent_files = (
                    Path(name)
                    for name in archive.namelist()
                    if name.lower().endswith((".shp", ".dbf", ".shx"))
                )

                def without_ext(path: Path) -> Path:
                    return path.with_suffix("")

                shapefiles = list(itertools.groupby(constituent_files, without_ext))
                # The zipfile must contain exactly one shapefile
                if not shapefiles:
                    raise ShapefileException("Zipfile does not contain any shapefiles")
                if len(shapefiles) >= 2:
                    raise ShapefileException(
                        f"Zipfile contains more than one shapefile: {shapefiles}. "
                        "Please ensure the zip file is on the file system "
                        "(download it if necessary) "
                        "and specify the full path to the shapefile in it "
                        "that you would like to open, "
                        "e.g. 'my_zip_file.zip/this_particular_shape_file.shp'. "
                    )
                shapefile, _files = shapefiles[0]
            # Try to extract file-like objects from zipfile
            self._shp = self._load_file_from_zip_to_tmp_file(archive, shapefile, ".shp")
            self._shx = self._load_file_from_zip_to_tmp_file(archive, shapefile, ".shx")
            self._dbf = self._load_file_from_zip_to_tmp_file(archive, shapefile, ".dbf")

    def load(self, file: str | os.PathLike[Any]) -> None:
        """Opens a shapefile from a filename or file-like
        object. Normally this method would be called by the
        constructor with the file name as an argument."""
        if not file:
            raise ShapefileException(f"No Shapefile to load.  Got: {file=}")
        self.path = file
        file = Path(file)
        self.shapeName = file.stem
        self.load_shp(file)
        self.load_shx(file)
        self.load_dbf(file)
        if not (self._shp or self._dbf):
            raise ShapefileException(
                f"Neither {self.shapeName}.dbf nor {self.shapeName}.shp could be opened "
            )

    def load_shp(self, file: Path) -> None:
        """
        Attempts to load file with .shp extension as both lower and upper case
        """
        self._shp = _try_get_open_constituent_file(file, ".shp")
        if self._shp:
            self.exit_stack.enter_context(self._shp)
            self._get_shp_reader()

    def load_shx(self, file: Path) -> None:
        """
        Attempts to load file with .shx extension as both lower and upper case
        """
        self._shx = _try_get_open_constituent_file(file, ".shx")
        if self._shx:
            self.exit_stack.enter_context(self._shx)
            self._get_shx_reader()

    def load_dbf(self, file: Path) -> None:
        """
        Attempts to load file with .dbf extension as both lower and upper case
        """
        self._dbf = _try_get_open_constituent_file(file, ".dbf")
        if self._dbf:
            self.exit_stack.enter_context(self._dbf)
            self._get_dbf_reader()

    def __len__(self) -> int:
        """Returns the number of shapes/records in the shapefile."""
        if self._dbf:
            # Preferably use dbf record count
            return len(self.dbf_reader)

        if self._shp:
            # Otherwise use shape count
            if self._shx:
                return self.shx_reader.numShapes

            # Index file not available, iterate all shapes to get total count
            elif self.numShapes == 0:
                # Determine length of shp file from
                # shp_reader offsets (and set these too)
                self.numShapes = len(self._offsets)

        return self.numShapes

    def __iter__(self) -> Iterator[ShapeRecord]:
        """Iterates through the shapes/records in the shapefile."""
        yield from self.iterShapeRecords()

    @property
    def __geo_interface__(self) -> GeoJSONFeatureCollectionWithBBox:
        return GeoJSONFeatureCollectionWithBBox(
            bbox=list(self.bbox),
            **self.shapeRecords().__geo_interface__,
        )

    def __del__(self) -> None:
        self.close()

    def __str__(self) -> str:
        """
        Use some general info on the shapefile as __str__
        """
        info = ["shapefile Reader"]
        if self._shp:
            info.append(
                f"    {self.numShapes} shapes (type '{SHAPETYPE_LOOKUP[self.shapeType]}')"
            )
        if self._dbf:
            info.append(f"    {self.numRecords} records ({len(self.fields)} fields)")
        return "\n".join(info)

    def shape(self, i: int = 0, bbox: BBox | None = None) -> Shape | None:
        """Returns a shape object for a shape in the geometry
        record file.
        If the 'bbox' arg is given (list or tuple of xmin,ymin,xmax,ymax),
        returns None if the shape is not within that region.
        """
        N = len(self)
        if N == 0:
            raise ShapefileException("No shapes loaded.")
        i = ensure_within_bounds(i, N)
        if self._shx:
            offset, shape_len_B = (
                self.shx_reader.offsets[i],
                self.shx_reader.shape_lengths_B[i],
            )
        else:
            offset, shape_len_B = None, None
        return self.shp_reader.shape(i, offset, shape_len_B, bbox)

    def shapes(self, bbox: BBox | None = None) -> Shapes:
        """Returns all shapes in a shapefile.
        To only read shapes within a given spatial region, specify the 'bbox'
        arg as a list or tuple of xmin,ymin,xmax,ymax.
        """
        shapes = Shapes(self.iterShapes(bbox=bbox))
        return shapes

    def iterShapes(self, bbox: BBox | None = None) -> Iterator[Shape | None]:
        """Returns a generator of shapes in a shapefile. Useful
        for handling large shapefiles.
        To only read shapes within a given spatial region, specify the 'bbox'
        arg as a list or tuple of xmin,ymin,xmax,ymax.
        """
        shape_lengths_B = self.shx_reader.shape_lengths_B if self._shx else None
        bbox = BBox(*bbox) if bbox is not None else None
        yield from self.shp_reader.iterShapes(
            shape_lengths_B=shape_lengths_B, bbox=bbox
        )
        self.numShapes = len(self.shp_reader.headers_cache)

    def shapeRecord(
        self,
        i: int = 0,
        fields: list[str] | None = None,
        bbox: BBox | None = None,
    ) -> ShapeRecord | None:
        """Returns a combination geometry and attribute record for the
        supplied record index.
        To only read some of the fields, specify the 'fields' arg as a
        list of one or more fieldnames.
        If the 'bbox' arg is given (list or tuple of xmin,ymin,xmax,ymax),
        returns None if the shape is not within that region.
        """
        if self.numRecords is None:
            raise ShapefileException(
                "A .dbf file is required to read Records, for ShapeRecords"
            )
        i = ensure_within_bounds(i, self.numRecords)
        shape = self.shape(i, bbox=bbox)
        if shape:
            record = self.dbf_reader.record(i, fields=fields)
            return ShapeRecord(shape=shape, record=record)
        return None

    def shapeRecords(
        self,
        fields: list[str] | None = None,
        bbox: BBox | None = None,
    ) -> ShapeRecords:
        """Returns a list of combination geometry/attribute records for
        all records in a shapefile.
        To only read some of the fields, specify the 'fields' arg as a
        list of one or more fieldnames.
        To only read entries within a given spatial region, specify the 'bbox'
        arg as a list or tuple of xmin,ymin,xmax,ymax.
        """
        return ShapeRecords(self.iterShapeRecords(fields=fields, bbox=bbox))

    def iterShapeRecords(
        self,
        fields: list[str] | None = None,
        bbox: BBox | None = None,
    ) -> Iterator[ShapeRecord]:
        """Returns a generator of combination geometry/attribute records for
        all records in a shapefile.
        To only read some of the fields, specify the 'fields' arg as a
        list of one or more fieldnames.
        To only read entries within a given spatial region, specify the 'bbox'
        arg as a list or tuple of xmin,ymin,xmax,ymax.
        """
        if bbox is None:
            # iterate through all shapes and records
            for shape, record in zip(
                self.iterShapes(), self.dbf_reader.iterRecords(fields=fields)
            ):
                yield ShapeRecord(shape=shape, record=record)
        else:
            # Only yield ShapeRecords whose shape.bbox overlaps with bbox.
            # TODO: internal _record method should be faster but would have to
            # make sure to seek to correct file location...

            # fieldTuples,recLookup,recStruct = self._record_fields(fields)
            for shape in self.iterShapes(bbox=bbox):
                if shape:
                    # record = self._record(oid=i, fieldTuples=fieldTuples, recLookup=recLookup, recStruct=recStruct)
                    record = self.dbf_reader.record(i=shape.oid, fields=fields)
                    yield ShapeRecord(shape=shape, record=record)


def _is_file_obj_open(f: WriteSeekableBinStream | str | None) -> bool:
    if not f:
        return False
    # If it doesn't declare itself closed, assume it's open.
    return not getattr(f, "closed", False)


def _try_to_flush_file_obj(f: WriteSeekableBinStream | str | None) -> None:
    if not f or not hasattr(f, "flush"):
        return
    if getattr(f, "closed", False):
        return
    try:
        f.flush()
    except OSError:
        pass


class _HasCheckedWriteableFile(_FileObjChecker[WriteSeekableBinStream]):
    FileProto = WriteSeekableBinStream
    new_file_obj_mode = "w+b"

    def __init__(self, file: str | PathLike[Any] | WriteSeekableBinStream):
        super().__init__(file)

    @functools.cached_property
    def file(self) -> WriteSeekableBinStream:
        return self._ensure_file_obj()

    def is_open(self) -> bool:
        return bool(self.file and _is_file_obj_open(self.file))

    def _header(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        self._header()
        if self.is_open():
            _try_to_flush_file_obj(self.file)
        super().close()


class DbfWriter(_HasCheckedWriteableFile):
    """Writes .dbf files (dBASE database files), in particular those of Shapefiles."""

    ext = ".dbf"
    ExceptionClass = dbfFileException

    def __init__(
        self,
        dbf: str | PathLike[Any] | WriteSeekableBinStream,
        *,
        encoding: str = "utf-8",
        encodingErrors: str = "strict",
        max_num_fields: int = 2046,
        # Keep kwargs even though unused, to preserve PyShp 2.4 API
        **kwargs: Any,
    ):
        super().__init__(file=dbf)

        self.encoding = encoding
        self.encodingErrors = encodingErrors

        self.fields: list[Field] = []
        self.max_num_fields = max_num_fields
        self.recNum = 0

    def field(
        # Types of args should match *Field
        self,
        name: str,
        field_type: FieldTypeT = "C",
        size: int = 50,
        decimal: int = 0,
    ) -> None:
        """Adds a dbf field descriptor to the shapefile."""
        if len(self.fields) >= self.max_num_fields:
            raise dbfFileException(
                f".dbf Shapefile Writer reached maximum number of fields: {self.max_num_fields}."
            )
        field_ = Field.from_unchecked(name, field_type, size, decimal)
        self.fields.append(field_)

    def _header(self) -> None:
        """Writes the dbf header and field descriptors."""
        f = self.file
        f.seek(0)
        version = 3
        year, month, day = time.localtime()[:3]
        year -= 1900
        # Get all fields, ignoring DeletionFlag if specified
        fields = [field for field in self.fields if field[0] != "DeletionFlag"]
        # Ensure has at least one field
        if not fields:
            raise ShapefileException(
                "Shapefile dbf file must contain at least one field."
            )
        numRecs = self.recNum
        numFields = len(fields)
        headerLength = numFields * 32 + 33
        if headerLength >= 65535:
            raise ShapefileException(
                "Shapefile dbf header length exceeds maximum length."
            )
        recordLength = sum(field.size for field in fields) + 1
        header = pack(
            "<BBBBLHH20x",
            version,
            year,
            month,
            day,
            numRecs,
            headerLength,
            recordLength,
        )
        f.write(header)
        # Field descriptors
        for field in fields:
            encoded_name = field.name.encode(self.encoding, self.encodingErrors)
            encoded_name = encoded_name.replace(b" ", b"_")
            encoded_name = encoded_name[:10].ljust(11).replace(b" ", b"\x00")
            encodedFieldType = field.field_type.encode("ascii")
            fld = pack(
                "<11sc4xBB14x",
                encoded_name,
                encodedFieldType,
                field.size,
                field.decimal,
            )
            f.write(fld)
        # Terminator
        f.write(b"\r")

    def record(
        self,
        *recordList: RecordValue,
        **recordDict: RecordValue,
    ) -> None:
        """Creates a dbf attribute record. You can submit either a sequence of
        field values or keyword arguments of field names and values. Before
        adding records you must add fields for the record values using the
        field() method. If the record values exceed the number of fields the
        extra ones won't be added. In the case of using keyword arguments to specify
        field/value pairs only fields matching the already registered fields
        will be added."""
        record: list[RecordValue]
        fieldCount = sum(1 for field in self.fields if field[0] != "DeletionFlag")
        if recordList:
            record = list(recordList)
            while len(record) < fieldCount:
                record.append("")
        elif recordDict:
            record = []
            for field in self.fields:
                if field[0] == "DeletionFlag":
                    continue  # ignore deletionflag field in case it was specified
                if field[0] in recordDict:
                    val = recordDict[field[0]]
                    if val is None:
                        record.append("")
                    else:
                        record.append(val)
                else:
                    record.append("")  # need empty value for missing dict entries
        else:
            # Blank fields for empty record
            record = ["" for _ in range(fieldCount)]
        self.__dbfRecord(record)

    def __dbfRecord(self, record: list[RecordValue]) -> None:
        """Writes the dbf records."""
        f = self.file
        if self.recNum == 0:
            # first records, so all fields should be set
            # allowing us to write the dbf header
            # cannot change the fields after this point
            self._header()
        # first byte of the record is deletion flag, always disabled
        f.write(b" ")
        # begin
        self.recNum += 1
        fields = (
            field for field in self.fields if field[0] != "DeletionFlag"
        )  # ignore deletionflag field in case it was specified
        for (fieldName, fieldType, size, deci), value in zip(fields, record):
            # write
            # fieldName, fieldType, size and deci were already checked
            # when their Field instance was created and added to self.fields
            str_val: str | None = None

            if fieldType in ("N", "F"):
                # numeric or float: number stored as a string, right justified, and padded with blanks to the width of the field.
                if value in MISSING:
                    str_val = "*" * size  # QGIS NULL
                elif not deci:
                    # force to int
                    try:
                        # first try to force directly to int.
                        # forcing a large int to float and back to int
                        # will lose information and result in wrong nr.
                        num_val = int(cast(int, value))
                    except ValueError:
                        # forcing directly to int failed, so was probably a float.
                        num_val = int(float(cast(float, value)))
                    str_val = format(num_val, "d")[:size].rjust(
                        size
                    )  # caps the size if exceeds the field size
                else:
                    f_val = float(cast(float, value))
                    str_val = format(f_val, f".{deci}f")[:size].rjust(
                        size
                    )  # caps the size if exceeds the field size
            elif fieldType == "D":
                # date: 8 bytes - date stored as a string in the format YYYYMMDD.
                if isinstance(value, date):
                    str_val = f"{value.year:04d}{value.month:02d}{value.day:02d}"
                elif isinstance(value, list) and len(value) == 3:
                    str_val = f"{value[0]:04d}{value[1]:02d}{value[2]:02d}"
                elif value in MISSING:
                    str_val = "0" * 8  # QGIS NULL for date type
                elif isinstance(value, str) and len(value) == 8:
                    pass  # value is already a date string
                else:
                    raise ShapefileException(
                        "Date values must be either a datetime.date object, a list, a YYYYMMDD string, or a missing value."
                    )
            elif fieldType == "L":
                # logical: 1 byte - initialized to 0x20 (space) otherwise T or F.
                if value in MISSING:
                    str_val = " "  # missing is set to space
                elif value in [True, 1]:
                    str_val = "T"
                elif value in [False, 0]:
                    str_val = "F"
                else:
                    str_val = " "  # unknown is set to space

            if str_val is None:
                # Types C and M, and anything else, value is forced to string,
                # encoded by the codec specified to the Writer (utf-8 by default),
                # then the resulting bytes are padded and truncated to the length
                # of the field
                encoded = (
                    str(value)
                    .encode(self.encoding, self.encodingErrors)[:size]
                    .ljust(size)
                )
            else:
                # str_val was given a not-None string value
                # under the checks for fieldTypes "N", "F", "D", or "L" above
                # Numeric, logical, and date numeric types are ascii already, but
                # for Shapefile or dbf spec reasons
                # "should be default ascii encoding"
                encoded = str_val.encode("ascii", self.encodingErrors)

            if len(encoded) != size:
                raise ShapefileException(
                    f"Shapefile Writer unable to pack incorrect sized {value=}"
                    f" (encoded as {len(encoded)}B) into field '{fieldName}' ({size}B)."
                )
            f.write(encoded)


class _ShpShxHeaderWriter(_HasCheckedWriteableFile):
    def __init__(self, file: str | PathLike[Any] | WriteSeekableBinStream):
        super().__init__(file=file)
        # Initiate with empty headers, to be finalized upon closing
        self.file.seek(0)
        self.file.write(b"9" * 100)

    def _write_file_length(self) -> None:
        raise NotImplementedError

    def _shp_or_shx_header(self, shp_info: _ShpWriterInfo) -> None:
        """Writes the specified header type to the specified file-like object.
        Several of the shapefile formats are so similar that a single generic
        method to read or write them is warranted."""
        f = self.file
        f.seek(0)
        # File code, Unused bytes
        f.write(pack(">6i", 9994, 0, 0, 0, 0, 0))

        # File length (Bytes / 2 = 16-bit words).
        # Hook for shx and shp specific subclasses to implement.
        self._write_file_length()

        f.write(pack("<2i", 1000, shp_info.shapeType or NULL))

        # BBox, the shapefile's bounding box (lower left, upper right)
        # In such cases of empty shapefiles, ESRI spec says the bbox values are 'unspecified'.
        # Not sure what that means, so for now just setting to 0s, which is the same behavior as in previous versions.
        # This would also make sense since the Z and M bounds are similarly set to 0 for non-Z/M type shapefiles.
        # bbox: BBox = (0, 0, 0, 0)
        bbox = shp_info._bbox or (0, 0, 0, 0)
        try:
            f.write(pack("<4d", *bbox))
        except StructError:
            raise ShapefileException(
                "Failed to write shapefile bounding box. Floats required."
            )

        # Elevation
        # As per the ESRI shapefile spec, the zbox for non-Z type shapefiles are set to 0s
        # zbox : ZBox = (0, 0).  We also do this for empty shapefiles and null-shapes only files.
        zbox = shp_info._zbox or (0, 0)

        # Ms
        # As per the ESRI shapefile spec, the mbox for non-M type shapefiles are set to 0s
        # mbox: Mbox = (0, 0).  We also do this for empty shapefiles and null-shapes only files.
        mbox = shp_info._mbox or (0, 0)

        # Try writing
        try:
            f.write(pack("<4d", *zbox, *replace_None_with_NODATA(mbox)))
        except StructError:
            raise ShapefileException(
                "Failed to write shapefile elevation and measure values. Floats required."
            )


class _ShpWriterInfo(_ShpShxHeaderWriter):
    def __init__(
        self,
        shp: str | PathLike[Any] | WriteSeekableBinStream,
        shapeType: int | None = None,
    ):
        super().__init__(file=shp)
        self.shapeType: int | None = shapeType
        # Geometry record offsets and lengths for writing shx file.
        self.shpNum: int = 0
        self._bbox: BBox | None = None
        self._zbox: ZBox | None = None
        self._mbox: MBox | None = None

    def bbox(self) -> BBox | None:
        """Returns the current bounding box for the shapefile which is
        the lower-left and upper-right corners. It does not contain the
        elevation or measure extremes."""
        return self._bbox

    def zbox(self) -> ZBox | None:
        """Returns the current z extremes for the shapefile."""
        return self._zbox

    def mbox(self) -> MBox | None:
        """Returns the current m extremes for the shapefile."""
        return self._mbox


class ShpWriter(_ShpWriterInfo):
    ext = ".shp"

    def _header(self) -> None:
        super()._shp_or_shx_header(shp_info=self)

    def _write_file_length(self) -> None:
        # self.file required to be at correct position, e.g.
        # if called by self._header
        self.file.write(pack(">i", self._shp_file_length_B()))

    def _shp_file_length_B(self) -> int:
        """Calculates the file length of the shp file."""
        # Remember starting position
        start_B = self.file.tell()

        # Calculate size of all shapes
        self.file.seek(0, 2)
        size_16b_words = self.file.tell()
        # Calculate size as 16-bit words
        size_B = size_16b_words // 2
        # Return to start
        self.file.seek(start_B)
        return size_B

    def _update_file_bbox(self, s: Shape) -> None:
        if s.shapeType == NULL:
            shape_bbox = None
        elif s.shapeType in _CanHaveBBox_shapeTypes:
            shape_bbox = s.bbox
        else:
            x, y = s.points[0][:2]
            shape_bbox = BBox(xmin=x, ymin=y, xmax=x, ymax=y)

        if shape_bbox is None:
            return None

        if self._bbox:
            # compare with existing
            self._bbox = BBox(
                xmin=min(shape_bbox.xmin, self._bbox.xmin),
                ymin=min(shape_bbox.ymin, self._bbox.ymin),
                xmax=max(shape_bbox.xmax, self._bbox.xmax),
                ymax=max(shape_bbox.ymax, self._bbox.ymax),
            )
        else:
            # first time bbox is being set
            self._bbox = shape_bbox
        return None

    def _update_file_zbox(self, s: _HasZ | PointZ) -> None:
        if self._zbox:
            # compare with existing
            self._zbox = ZBox(
                zmin=min(s.zbox.zmin, self._zbox.zmin),
                zmax=max(s.zbox.zmax, self._zbox.zmax),
            )
        else:
            # first time zbox is being set
            self._zbox = s.zbox

    def _update_file_mbox(self, s: _HasM | PointM) -> None:
        mbox = s.mbox
        if self._mbox:
            # compare with existing
            self._mbox = self._mbox.expand(mbox)
        else:
            # first time mbox is being set
            self._mbox = mbox

    def shape(
        self,
        s: Shape | HasGeoInterface | GeoJSONHomogeneousGeometryObject,
    ) -> tuple[int, int]:
        # Check is shape or import from geojson
        if not isinstance(s, Shape):
            if hasattr(s, "__geo_interface__"):
                s = cast(HasGeoInterface, s)
                shape_dict = s.__geo_interface__
            elif isinstance(s, dict):  # TypedDict is a dict at runtime
                shape_dict = s
            else:
                raise TypeError(
                    "Can only write Shape objects, GeoJSON dictionaries, "
                    "or objects with the __geo_interface__, "
                    f"not: {s}"
                )
            s = Shape._from_geojson(shape_dict)
        # Write to file
        return self._shp_record(s)

    def _shp_record(self, s: Shape) -> tuple[int, int]:
        offset = self.file.tell()
        self.shpNum += 1

        # Shape Type
        if self.shapeType is None and s.shapeType != NULL:
            self.shapeType = s.shapeType
        if s.shapeType not in (NULL, self.shapeType):
            raise ShapefileException(
                f"The shape's type ({s.shapeType}) must match "
                f"the type of the shapefile ({self.shapeType})."
            )

        # For both single point and multiple-points non-null shapes,
        # update bbox, mbox and zbox of the whole shapefile
        if s.shapeType != NULL:
            self._update_file_bbox(s)

        if s.shapeType in PointM_shapeTypes | _HasM_shapeTypes:
            self._update_file_mbox(cast(Union[_HasM, PointM], s))

        if s.shapeType in PointZ_shapeTypes | _HasZ_shapeTypes:
            self._update_file_zbox(cast(Union[_HasZ, PointZ], s))

        # Create an in-memory binary buffer to avoid
        # unnecessary seeks to files on disk
        # (other ops are already buffered until .seek
        # or .flush is called if not using RawIOBase).
        # https://docs.python.org/3/library/io.html#id2
        # https://docs.python.org/3/library/io.html#io.BufferedWriter
        b_io: ReadWriteSeekableBinStream = io.BytesIO()

        # Record number, Content length place holder
        b_io.write(pack(">2i", self.shpNum, -1))

        # Track number of content bytes written, excluding
        # self.shpNum and length (t.b.c.)
        n = 0

        n += b_io.write(pack("<i", s.shapeType))

        ShapeClass = SHAPE_CLASS_FROM_SHAPETYPE[s.shapeType]
        n += ShapeClass.write_to_byte_stream(
            b_io=b_io,
            s=s,
            i=self.shpNum,
        )

        # Finalize record length as 16-bit words
        length_16bw = n // 2

        # 4 bytes in is the content length field
        # (where we wrote the -1 placeholder above)
        b_io.seek(4)
        b_io.write(pack(">i", length_16bw))

        # Flush to file.
        b_io.seek(0)
        self.file.write(b_io.read())
        return offset, length_16bw


class ShxWriter(_ShpShxHeaderWriter):
    ext = ".shx"

    def __init__(
        self,
        shx: str | PathLike[Any] | WriteSeekableBinStream,
        shp_writer: _ShpWriterInfo,
    ):
        super().__init__(file=shx)
        self.shp_writer = shp_writer

    def _shx_record(self, offset_B: int, length_16bw: int) -> None:
        """Writes the shx records."""

        f = self.file
        max_value_B = (1 << 32) - 2  # 4294967294 Bytes
        if offset_B > max_value_B:
            raise ShapefileException(
                f".shp file position offset too big. Max_value: {max_value_B=}.  Got: {offset_B}. \n"
                "It's over 4GB, perhaps split the .shp or the Shapefile into smaller ones? "
            )

        offset_16bw = offset_B // 2
        f.write(pack(">2i", offset_16bw, length_16bw))

    def _header(self) -> None:
        super()._shp_or_shx_header(shp_info=self.shp_writer)

    def _write_file_length(self) -> None:
        # self.file required to be at correct position, e.g.
        # if called by self._header
        self.file.write(pack(">i", ((100 + (self.shp_writer.shpNum * 8)) // 2)))


class Writer(_HasExitStack):
    """Provides write support for ESRI Shapefiles."""

    # W = TypeVar("W", bound=WriteSeekableBinStream)

    FileProto = WriteSeekableBinStream
    new_file_obj_mode = "w+b"
    ext = None
    ExceptionClass = ShapefileException

    def __init__(
        self,
        target: str | PathLike[Any] | None = None,
        shapeType: int | None = None,
        autoBalance: bool = False,
        *,
        encoding: str = "utf-8",
        encodingErrors: str = "strict",
        shp: WriteSeekableBinStream | None = None,
        shx: WriteSeekableBinStream | None = None,
        dbf: WriteSeekableBinStream | None = None,
        # Keep kwargs even though unused, to preserve PyShp 2.4 API
        **kwargs: Any,
    ) -> None:
        # Don't call super().__init
        if target is not None:
            try:
                target = Path(target)
            except (ValueError, TypeError):
                raise TypeError(
                    f"The target filepath {target!r} must be a str, Path, or os.PathLike, not {type(target)}."
                )
        self.target: Path | None = target

        # User settable - see ### Geometry and Record Balancing in README.md
        self.autoBalance = autoBalance

        self._shp: Path | WriteSeekableBinStream | None = shp
        self._shx: Path | WriteSeekableBinStream | None = shx
        self._dbf: Path | WriteSeekableBinStream | None = dbf
        self._shp_writer: ShpWriter | None = None
        self._shx_writer: ShxWriter | None = None
        self._dbf_writer: DbfWriter | None = None
        self.exit_stack = ExitStack()
        if target is not None:
            if shp or shx or dbf:
                raise TypeError(
                    "Unused kwargs were silently ignored by previous versions of PyShp. "
                    "Either specify target (first positional only arg), "
                    "or shp and/or dbf, possible plus shx"
                )
            self._shp = target.with_suffix(".shp")
            self._shx = target.with_suffix(".shx")
            self._dbf = target.with_suffix(".dbf")
        elif not (shp or shx or dbf):
            raise TypeError(
                "Either the target filepath, or any of shp, shx, or dbf must be set to create a shapefile."
            )
        if self._shp:
            self._shp_writer = ShpWriter(shp=self._shp, shapeType=shapeType)
            self.exit_stack.enter_context(self._shp_writer)
        if self._shx:
            if self._shp_writer is None:
                raise ShapefileException(
                    "a .shp file object is required to for a .shx file object "
                    ", to have shapes to actually create indices for. "
                )
            self._shx_writer = ShxWriter(shx=self._shx, shp_writer=self._shp_writer)
            self.exit_stack.enter_context(self._shx_writer)
        if self._dbf:
            self._dbf_writer = DbfWriter(
                dbf=self._dbf,
                encoding=encoding,
                encodingErrors=encodingErrors,
            )
            self.exit_stack.enter_context(self._dbf_writer)

    @property
    def shp_writer(self) -> ShpWriter:
        if self._shp_writer is None:
            raise ShapefileException(
                f"No shp file.  Got target: {self.target} & shp: {self._shp}"
            )
        return self._shp_writer

    @property
    def shx_writer(self) -> ShxWriter:
        if self._shx_writer is None:
            raise ShapefileException(
                f"No shx file.  Got target: {self.target} & shx: {self._shx}"
            )
        return self._shx_writer

    @property
    def dbf_writer(self) -> DbfWriter:
        if self._dbf_writer is None:
            raise dbfFileException(
                f"No dbf file.  Got target: {self.target} & dbf: {self._dbf}"
            )
        return self._dbf_writer

    @property
    def shp(self) -> WriteSeekableBinStream:
        return self.shp_writer.file

    @property
    def shx(self) -> WriteSeekableBinStream:
        return self.shx_writer.file

    @property
    def dbf(self) -> WriteSeekableBinStream:
        return self.dbf_writer.file

    @property
    def fields(self) -> list[Field]:
        return self.dbf_writer.fields

    @fields.setter
    def fields(self, value: list[Field]) -> None:
        self.dbf_writer.fields = value

    @property
    def recNum(self) -> int:
        if not self._dbf_writer:
            return 0
        return self.dbf_writer.recNum

    def balance(self) -> None:
        """Adds corresponding empty attributes or null geometry records depending
        on which type of record was created to make sure all three files
        are in synch."""
        while self.dbf_writer.recNum > self.shp_writer.shpNum:
            self.null()
        while self.dbf_writer.recNum < self.shp_writer.shpNum:
            self.record()

    def shape(
        self,
        s: Shape | HasGeoInterface | GeoJSONHomogeneousGeometryObject,
    ) -> None:
        # Balance if already not balanced
        if self.autoBalance and self.dbf_writer.recNum < self.shp_writer.shpNum:
            self.balance()
        offset_B, length_16bw = self.shp_writer.shape(s)
        if self._shx:
            self.shx_writer._shx_record(offset_B, length_16bw)

    def record(
        self,
        *recordList: RecordValue,
        **recordDict: RecordValue,
    ) -> None:
        # Balance if already not balanced
        if self.autoBalance and self.dbf_writer.recNum > self.shp_writer.shpNum:
            self.balance()
        self.dbf_writer.record(*recordList, **recordDict)

    def __len__(self) -> int:
        """Returns the current number of features written to the shapefile.
        If shapes and records are unbalanced, the length is considered the highest
        of the two."""

        if self._dbf_writer and self._shp_writer:
            return max(self.dbf_writer.recNum, self.shp_writer.shpNum)
        if self._shp_writer:
            return self.shp_writer.shpNum
        if self._dbf_writer:
            return self.dbf_writer.recNum
        return 0

    def __del__(self) -> None:
        self.close()

    def close(self) -> None:
        """
        Write final shp, shx, and dbf headers, close opened files.
        """

        # Check if user supplied shp or dbf file objects have
        # already been closed by the user for some reason.
        #
        # TODO: Do we really need to support this?
        #       Isn't "for some reason" an edge case by definition?
        # A user who supplies custom file objects for shp and
        # dbf, opens a Writer
        # to partially write the Shapefile, manually closes the .shp object
        # but uses the context manager or calls .close expecting
        # Writer to create the dbf's header?
        shp_open = False if self._shp_writer is None else self.shp_writer.is_open()
        dbf_open = False if self._dbf_writer is None else self.dbf_writer.is_open()
        # dbf_open = (
        #     False
        #     if self._dbf_writer is None
        #     else _is_file_obj_open(self.dbf_writer.file)
        # )

        # Balance if already not balanced
        if shp_open and dbf_open:
            if self.autoBalance:
                self.balance()
            if self.dbf_writer.recNum != self.shp_writer.shpNum:
                raise ShapefileException(
                    "When saving both the dbf and shp file, "
                    f"the number of records ({self.dbf_writer.recNum}) must correspond "
                    f"with the number of shapes ({self.shp_writer.shpNum})"
                )

        # self.exit_stack contains any self.{shp,shx,dbf}_writer instances.
        # Those created are triggered to write their headers here.
        # The point of using the exit stack is
        # i) that the above are guaranteed to be pushed on to
        #    it to dynamically if accessed via their properties.
        # ii) but in particular it should not contain
        #  user-supplied, already opened file objects that
        #  might be closed by an outer context manager).
        #
        # Idempotent.
        super().close()

    @property
    def shapeType(self) -> int | None:
        return self.shp_writer.shapeType

    @shapeType.setter
    def shapeType(self, val: int | None) -> None:
        # User settable - see #### Setting the Shape Type in README.md
        self.shp_writer.shapeType = val

    @property
    def shapeTypeName(self) -> str:
        return SHAPETYPE_LOOKUP[self.shapeType or 0]

    @property
    def shpNum(self) -> int:
        return self.shp_writer.shpNum

    @functools.wraps(_ShpWriterInfo.bbox)
    def bbox(self) -> BBox | None:
        return self.shp_writer._bbox

    @functools.wraps(_ShpWriterInfo.zbox)
    def zbox(self) -> ZBox | None:
        return self.shp_writer._zbox

    @functools.wraps(_ShpWriterInfo.mbox)
    def mbox(self) -> MBox | None:
        return self.shp_writer._mbox

    @functools.wraps(DbfWriter.field)
    def field(
        # Types of args should match *Field
        self,
        name: str,
        field_type: FieldTypeT = "C",
        size: int = 50,
        decimal: int = 0,
    ) -> None:
        self.dbf_writer.field(name, field_type, size, decimal)

    def null(self) -> None:
        """Creates a null shape."""
        self.shape(NullShape())

    def point(self, x: float, y: float) -> None:
        """Creates a POINT shape."""
        pointShape = Point(x, y)
        self.shape(pointShape)

    def pointm(self, x: float, y: float, m: float | None = None) -> None:
        """Creates a POINTM shape.
        If the m (measure) value is not set, it defaults to NoData."""
        pointShape = PointM(x, y, m)
        self.shape(pointShape)

    def pointz(
        self, x: float, y: float, z: float = 0.0, m: float | None = None
    ) -> None:
        """Creates a POINTZ shape.
        If the z (elevation) value is not set, it defaults to 0.
        If the m (measure) value is not set, it defaults to NoData."""
        pointShape = PointZ(x, y, z, m)
        self.shape(pointShape)

    def multipoint(self, points: PointsT) -> None:
        """Creates a MULTIPOINT shape.
        Points is a list of xy values."""
        # nest the points inside a list to be compatible with the generic shapeparts method
        shape = MultiPoint(points=points)
        self.shape(shape)

    def multipointm(self, points: PointsT) -> None:
        """Creates a MULTIPOINTM shape.
        Points is a list of xym values.
        If the m (measure) value is not included, it defaults to None (NoData)."""
        # nest the points inside a list to be compatible with the generic shapeparts method
        shape = MultiPointM(points=points)
        self.shape(shape)

    def multipointz(self, points: PointsT) -> None:
        """Creates a MULTIPOINTZ shape.
        Points is a list of xyzm values.
        If the z (elevation) value is not included, it defaults to 0.
        If the m (measure) value is not included, it defaults to None (NoData)."""
        # nest the points inside a list to be compatible with the generic shapeparts method
        shape = MultiPointZ(points=points)
        self.shape(shape)

    def line(self, lines: list[PointsT]) -> None:
        """Creates a POLYLINE shape.
        Lines is a collection of lines, each made up of a list of xy values."""
        shape = Polyline(lines=lines)
        self.shape(shape)

    def linem(self, lines: list[PointsT]) -> None:
        """Creates a POLYLINEM shape.
        Lines is a collection of lines, each made up of a list of xym values.
        If the m (measure) value is not included, it defaults to None (NoData)."""
        shape = PolylineM(lines=lines)
        self.shape(shape)

    def linez(self, lines: list[PointsT]) -> None:
        """Creates a POLYLINEZ shape.
        Lines is a collection of lines, each made up of a list of xyzm values.
        If the z (elevation) value is not included, it defaults to 0.
        If the m (measure) value is not included, it defaults to None (NoData)."""
        shape = PolylineZ(lines=lines)
        self.shape(shape)

    def poly(self, polys: list[PointsT]) -> None:
        """Creates a POLYGON shape.
        Polys is a collection of polygons, each made up of a list of xy values.
        Note that for ordinary polygons the coordinates must run in a clockwise direction.
        If some of the polygons are holes, these must run in a counterclockwise direction."""
        shape = Polygon(lines=polys)
        self.shape(shape)

    def polym(self, polys: list[PointsT]) -> None:
        """Creates a POLYGONM shape.
        Polys is a collection of polygons, each made up of a list of xym values.
        Note that for ordinary polygons the coordinates must run in a clockwise direction.
        If some of the polygons are holes, these must run in a counterclockwise direction.
        If the m (measure) value is not included, it defaults to None (NoData)."""
        shape = PolygonM(lines=polys)
        self.shape(shape)

    def polyz(self, polys: list[PointsT]) -> None:
        """Creates a POLYGONZ shape.
        Polys is a collection of polygons, each made up of a list of xyzm values.
        Note that for ordinary polygons the coordinates must run in a clockwise direction.
        If some of the polygons are holes, these must run in a counterclockwise direction.
        If the z (elevation) value is not included, it defaults to 0.
        If the m (measure) value is not included, it defaults to None (NoData)."""
        shape = PolygonZ(lines=polys)
        self.shape(shape)

    def multipatch(self, parts: list[PointsT], partTypes: list[int]) -> None:
        """Creates a MULTIPATCH shape.
        Parts is a collection of 3D surface patches, each made up of a list of xyzm values.
        PartTypes is a list of types that define each of the surface patches.
        The types can be any of the following module constants: TRIANGLE_STRIP,
        TRIANGLE_FAN, OUTER_RING, INNER_RING, FIRST_RING, or RING.
        If the z (elevation) value is not included, it defaults to 0.
        If the m (measure) value is not included, it defaults to None (NoData)."""
        shape = MultiPatch(lines=parts, partTypes=partTypes)
        self.shape(shape)


# Begin Testing
def _get_doctests() -> doctest.DocTest:
    # run tests
    with open("README.md", "rb") as fobj:
        tests = doctest.DocTestParser().get_doctest(
            string=fobj.read().decode("utf8").replace("\r\n", "\n"),
            globs={},
            name="README",
            filename="README.md",
            lineno=0,
        )

    return tests


def _filter_network_doctests(
    examples: Iterable[doctest.Example],
    include_network: bool = False,
    include_non_network: bool = True,
) -> Iterator[doctest.Example]:
    globals_from_network_doctests = set()

    if not (include_network or include_non_network):
        return

    examples_it = iter(examples)

    yield next(examples_it)

    for example in examples_it:
        # Track variables in doctest shell sessions defined from commands
        # that poll remote URLs, to skip subsequent commands until all
        # such dependent variables are reassigned.

        if 'sf = shapefile.Reader("https://' in example.source:
            globals_from_network_doctests.add("sf")
            if include_network:
                yield example
            continue

        lhs = example.source.partition("=")[0]

        for target in lhs.split(","):
            target = target.strip()
            if target in globals_from_network_doctests:
                globals_from_network_doctests.remove(target)

        # Non-network tests dependent on the network tests.
        if globals_from_network_doctests:
            if include_network:
                yield example
            continue

        if not include_non_network:
            continue

        yield example


def _replace_remote_url_with_localhost(old_url: str) -> str:

    old_split = urlsplit(old_url)

    # Strip subpaths, so an artefacts
    # repo or file tree can be simpler and flat
    path = old_split.path.rpartition("/")[2]

    new_split = old_split._replace(
        scheme="http",
        netloc="localhost:8000",  # Default port of Python http.server
        path=path,
        query="",
        fragment="",
    )

    return str(urlunsplit(new_split))


_URL_STR_LITERAL_PATTERN = r'"(https?://.*)"'


def _change_remote_url_match_to_localhost(
    match: re.Match[Any],  # A Match from _URL_STR_LITERAL_PATTERN above
) -> str:

    old_url = match.group(1)
    new_url = _replace_remote_url_with_localhost(old_url)
    return f'"{new_url}"'


def _test(
    temp_dir: str | None = None,
    args: list[str] = sys.argv[1:],
    verbosity: bool = False,
) -> int:

    if verbosity == 0:
        print("Getting doctests...")

    tests = _get_doctests()

    if len(args) >= 2 and args[0] == "-m":
        if verbosity == 0:
            print("Filtering doctests...")
        tests.examples = list(
            _filter_network_doctests(
                tests.examples,
                include_network=args[1] == "network",
                include_non_network=args[1] == "not network",
            )
        )

    if REPLACE_REMOTE_URLS_WITH_LOCALHOST:
        if verbosity == 0:
            print("Replacing remote urls with http://localhost in doctests...")

        for example in tests.examples:
            example.source = re.sub(
                pattern=_URL_STR_LITERAL_PATTERN,
                repl=_change_remote_url_match_to_localhost,
                string=example.source,
            )

    if temp_dir is not None:
        for example in tests.examples:
            example.source = example.source.replace("shapefiles/test/", f"{temp_dir}/")

    runner = doctest.DocTestRunner(verbose=verbosity, optionflags=doctest.FAIL_FAST)

    if verbosity == 0:
        print(f"Running {len(tests.examples)} doctests...")
    # Deleting a temp dir will error if it contains shapefiles to which
    # unclosed Readers still file objects open,
    # regardless of using clear_globs=True or calling gc.collect afterwards.
    failure_count, __test_count = runner.run(tests)

    # print results
    if verbosity:
        runner.summarize(True)
    else:
        if failure_count == 0:
            print("All test passed successfully")
        elif failure_count > 0:
            runner.summarize(verbosity)

    return failure_count


def main() -> None:
    """
    Doctests are contained in the file 'README.md', and are tested using the built-in
    testing libraries.
    """
    with tempfile.TemporaryDirectory() as td:
        failure_count = _test(Path(td).as_posix())
    sys.exit(failure_count)


if __name__ == "__main__":
    main()
