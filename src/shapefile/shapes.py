from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from struct import error, pack, unpack
from typing import Final, TypedDict, Union, cast

from .classes import _Array
from .constants import (
    MULTIPATCH,
    MULTIPOINT,
    MULTIPOINTM,
    MULTIPOINTZ,
    NODATA,
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
    SHAPETYPE_LOOKUP,
    SHAPETYPENUM_LOOKUP,
)
from .exceptions import ShapefileException
from .geojson import GeoJSONSerisalizableShape
from .geometric_calculations import bbox_overlap
from .types import (
    BBox,
    MBox,
    Point2D,
    PointMT,
    PointsT,
    PointT,
    PointZT,
    ReadableBinStream,
    ReadSeekableBinStream,
    WriteableBinStream,
    ZBox,
)


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


class Shape(GeoJSONSerisalizableShape):
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

        return min(xs), min(ys), max(xs), max(ys)

    def _mbox_from_ms(self) -> MBox:
        ms: list[float] = [m for m in self.m if m is not None]

        if not ms:
            # only if none of the shapes had m values, should mbox be set to missing m values
            ms.append(NODATA)

        return min(ms), max(ms)

    def _zbox_from_zs(self) -> ZBox:
        return min(self.z), max(self.z)

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
        next_shape: int,
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
        return unpack("<4d", b_io.read(32))

    @staticmethod
    def _write_bbox_to_byte_stream(
        b_io: WriteableBinStream, i: int, bbox: BBox | None
    ) -> int:
        if not bbox or len(bbox) != 4:
            raise ShapefileException(f"Four numbers required for bbox. Got: {bbox}")
        try:
            return b_io.write(pack("<4d", *bbox))
        except error:
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
        except error:
            raise ShapefileException(
                f"Failed to write points for record {i}. Expected floats."
            )

    @classmethod
    def from_byte_stream(
        cls,
        shapeType: int,
        b_io: ReadSeekableBinStream,
        next_shape: int,
        oid: int | None = None,
        bbox: BBox | None = None,
    ) -> Shape | None:
        ShapeClass = cast(type[_CanHaveBBox], SHAPE_CLASS_FROM_SHAPETYPE[shapeType])

        kwargs: CanHaveBboxNoLinesKwargs = {"oid": oid}  # "shapeType": shapeType}
        kwargs["bbox"] = shape_bbox = cls._read_bbox_from_byte_stream(b_io)

        # if bbox specified and no overlap, skip this shape
        if bbox is not None and not bbox_overlap(bbox, shape_bbox):
            # because we stop parsing this shape, caller must skip to beginning of
            # next shape after we return (as done in f.seek(next_shape))
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
                    b_io, nPoints, next_shape
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
        except error:
            raise ShapefileException(
                f"Failed to write point for record {i}. Expected floats."
            )

    @classmethod
    def from_byte_stream(
        cls,
        shapeType: int,
        b_io: ReadSeekableBinStream,
        next_shape: int,
        oid: int | None = None,
        bbox: BBox | None = None,
    ) -> Shape | None:
        x, y = cls._x_y_from_byte_stream(b_io)

        if bbox is not None:
            # create bounding box for Point by duplicating coordinates
            # skip shape if no overlap with bounding box
            if not bbox_overlap(bbox, (x, y, x, y)):
                return None
        elif shapeType == POINT:
            return Point(x=x, y=y, oid=oid)

        if shapeType == POINTZ:
            z = PointZ._read_single_point_zs_from_byte_stream(b_io)[0]

        m = PointM._read_single_point_ms_from_byte_stream(b_io, next_shape)[0]

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


class _HasM(_CanHaveBBox):
    m: Sequence[float | None]

    @staticmethod
    def _read_ms_from_byte_stream(
        b_io: ReadSeekableBinStream, nPoints: int, next_shape: int
    ) -> tuple[MBox, list[float | None]]:
        if next_shape - b_io.tell() >= 16:
            mbox = unpack("<2d", b_io.read(16))
        # Measure values less than -10e38 are nodata values according to the spec
        if next_shape - b_io.tell() >= nPoints * 8:
            ms = []
            for m in unpack(f"<{nPoints}d", b_io.read(nPoints * 8)):
                if m > NODATA:
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
            num_bytes_written = b_io.write(pack("<2d", *mbox))
        except error:
            raise ShapefileException(
                f"Failed to write measure extremes for record {i}. Expected floats"
            )
        try:
            ms = cast(_HasM, s).m

            ms_to_encode = [m if m is not None else NODATA for m in ms]

            num_bytes_written += b_io.write(pack(f"<{len(ms)}d", *ms_to_encode))
        except error:
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
        zbox = unpack("<2d", b_io.read(16))
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
        except error:
            raise ShapefileException(
                f"Failed to write elevation extremes for record {i}. Expected floats."
            )
        try:
            zs = cast(_HasZ, s).z
            num_bytes_written += b_io.write(pack(f"<{len(zs)}d", *zs))
        except error:
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
        # same default as in Writer.__shpRecord (if s.shapeType in (11, 21):)
        # PyShp encodes None m values as NODATA
        m: float | None = None,
        oid: int | None = None,
    ):
        Shape.__init__(self, points=[(x, y)], m=(m,), oid=oid)

    @staticmethod
    def _read_single_point_ms_from_byte_stream(
        b_io: ReadSeekableBinStream, next_shape: int
    ) -> tuple[float | None]:
        if next_shape - b_io.tell() >= 8:
            (m,) = unpack("<d", b_io.read(8))
        else:
            m = NODATA
        # Measure values less than -10e38 are nodata values according to the spec
        if m > NODATA:
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
        except error:
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

    # same default as in Writer.__shpRecord (if s.shapeType == 11:)
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
        except error:
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
