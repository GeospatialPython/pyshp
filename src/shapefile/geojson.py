from __future__ import annotations

import logging
from typing import (Any, TypedDict, Union, Protocol, Literal, cast, Self)

from .constants import (
    NULL,
    POINT,
    POINTM,
    POINTZ,
    MULTIPOINT,
    MULTIPOINTM,
    MULTIPOINTZ,
    POLYLINE,
    POLYLINEM,
    POLYLINEZ,
    POLYGON,
    POLYGONM,
    POLYGONZ,
    SHAPETYPE_LOOKUP,
    VERBOSE
)
from .exceptions import GeoJSON_Error
from .geometric_calculations import is_cw, rewind, organize_polygon_rings
from .types import PointT, PointsT


logger = logging.getLogger(__name__)
    
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

class GeoJSONSerisalizableShape:
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

    @classmethod
    def _from_geojson(cls, geoj: GeoJSONHomogeneousGeometryObject) -> Self:
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
        return cls(shapeType=shapeType, points=points, parts=parts)