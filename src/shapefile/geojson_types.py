from __future__ import annotations

from typing import Any, Literal, Protocol, TypedDict, Union

from .constants import (
    MULTIPOINT,
    NULL,
    POINT,
    POLYGON,
    POLYLINE,
)
from .types import PointsT, PointT


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
