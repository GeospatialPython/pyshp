from __future__ import annotations

import os

# Module settings
VERBOSE = True

# Test config (for the Doctest runner and test_shapefile.py)
REPLACE_REMOTE_URLS_WITH_LOCALHOST = (
    os.getenv("REPLACE_REMOTE_URLS_WITH_LOCALHOST", "").lower() == "yes"
)

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


MISSING = (None, "")  # Don't make a set, as user input may not be Hashable
NODATA = -10e38  # as per the ESRI shapefile spec, only used for m-values.
