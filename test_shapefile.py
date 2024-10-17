"""
This module tests the functionality of shapefile.py.
"""

import datetime
import json
import os.path

try:
    from pathlib import Path
except ImportError:
    # pathlib2 is a dependency of pytest >= 3.7
    from pathlib2 import Path

# third party imports
import pytest

# our imports
import shapefile

# define various test shape tuples of (type, points, parts indexes, and expected geo interface output)
geo_interface_tests = [
    (
        shapefile.POINT,  # point
        [(1, 1)],
        [],
        {"type": "Point", "coordinates": (1, 1)},
    ),
    (
        shapefile.MULTIPOINT,  # multipoint
        [(1, 1), (2, 1), (2, 2)],
        [],
        {"type": "MultiPoint", "coordinates": [(1, 1), (2, 1), (2, 2)]},
    ),
    (
        shapefile.POLYLINE,  # single linestring
        [(1, 1), (2, 1)],
        [0],
        {"type": "LineString", "coordinates": [(1, 1), (2, 1)]},
    ),
    (
        shapefile.POLYLINE,  # multi linestring
        [
            (1, 1),
            (2, 1),  # line 1
            (10, 10),
            (20, 10),
        ],  # line 2
        [0, 2],
        {
            "type": "MultiLineString",
            "coordinates": [
                [(1, 1), (2, 1)],  # line 1
                [(10, 10), (20, 10)],  # line 2
            ],
        },
    ),
    (
        shapefile.POLYGON,  # single polygon, no holes
        [
            (1, 1),
            (1, 9),
            (9, 9),
            (9, 1),
            (1, 1),  # exterior
        ],
        [0],
        {
            "type": "Polygon",
            "coordinates": [
                [(1, 1), (1, 9), (9, 9), (9, 1), (1, 1)],
            ],
        },
    ),
    (
        shapefile.POLYGON,  # single polygon, holes (ordered)
        [
            (1, 1),
            (1, 9),
            (9, 9),
            (9, 1),
            (1, 1),  # exterior
            (2, 2),
            (4, 2),
            (4, 4),
            (2, 4),
            (2, 2),  # hole 1
            (5, 5),
            (7, 5),
            (7, 7),
            (5, 7),
            (5, 5),  # hole 2
        ],
        [0, 5, 5 + 5],
        {
            "type": "Polygon",
            "coordinates": [
                [(1, 1), (1, 9), (9, 9), (9, 1), (1, 1)],  # exterior
                [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)],  # hole 1
                [(5, 5), (7, 5), (7, 7), (5, 7), (5, 5)],  # hole 2
            ],
        },
    ),
    (
        shapefile.POLYGON,  # single polygon, holes (unordered)
        [
            (2, 2),
            (4, 2),
            (4, 4),
            (2, 4),
            (2, 2),  # hole 1
            (1, 1),
            (1, 9),
            (9, 9),
            (9, 1),
            (1, 1),  # exterior
            (5, 5),
            (7, 5),
            (7, 7),
            (5, 7),
            (5, 5),  # hole 2
        ],
        [0, 5, 5 + 5],
        {
            "type": "Polygon",
            "coordinates": [
                [(1, 1), (1, 9), (9, 9), (9, 1), (1, 1)],  # exterior
                [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)],  # hole 1
                [(5, 5), (7, 5), (7, 7), (5, 7), (5, 5)],  # hole 2
            ],
        },
    ),
    (
        shapefile.POLYGON,  # multi polygon, no holes
        [
            (1, 1),
            (1, 9),
            (9, 9),
            (9, 1),
            (1, 1),  # exterior
            (11, 11),
            (11, 19),
            (19, 19),
            (19, 11),
            (11, 11),  # exterior
        ],
        [0, 5],
        {
            "type": "MultiPolygon",
            "coordinates": [
                [  # poly 1
                    [(1, 1), (1, 9), (9, 9), (9, 1), (1, 1)],
                ],
                [  # poly 2
                    [(11, 11), (11, 19), (19, 19), (19, 11), (11, 11)],
                ],
            ],
        },
    ),
    (
        shapefile.POLYGON,  # multi polygon, holes (unordered)
        [
            (1, 1),
            (1, 9),
            (9, 9),
            (9, 1),
            (1, 1),  # exterior 1
            (11, 11),
            (11, 19),
            (19, 19),
            (19, 11),
            (11, 11),  # exterior 2
            (12, 12),
            (14, 12),
            (14, 14),
            (12, 14),
            (12, 12),  # hole 2.1
            (15, 15),
            (17, 15),
            (17, 17),
            (15, 17),
            (15, 15),  # hole 2.2
            (2, 2),
            (4, 2),
            (4, 4),
            (2, 4),
            (2, 2),  # hole 1.1
            (5, 5),
            (7, 5),
            (7, 7),
            (5, 7),
            (5, 5),  # hole 1.2
        ],
        [0, 5, 10, 15, 20, 25],
        {
            "type": "MultiPolygon",
            "coordinates": [
                [  # poly 1
                    [(1, 1), (1, 9), (9, 9), (9, 1), (1, 1)],  # exterior
                    [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)],  # hole 1
                    [(5, 5), (7, 5), (7, 7), (5, 7), (5, 5)],  # hole 2
                ],
                [  # poly 2
                    [(11, 11), (11, 19), (19, 19), (19, 11), (11, 11)],  # exterior
                    [(12, 12), (14, 12), (14, 14), (12, 14), (12, 12)],  # hole 1
                    [(15, 15), (17, 15), (17, 17), (15, 17), (15, 15)],  # hole 2
                ],
            ],
        },
    ),
    (
        shapefile.POLYGON,  # multi polygon, nested exteriors with holes (unordered)
        [
            (1, 1),
            (1, 9),
            (9, 9),
            (9, 1),
            (1, 1),  # exterior 1
            (3, 3),
            (3, 7),
            (7, 7),
            (7, 3),
            (3, 3),  # exterior 2
            (4.5, 4.5),
            (4.5, 5.5),
            (5.5, 5.5),
            (5.5, 4.5),
            (4.5, 4.5),  # exterior 3
            (4, 4),
            (6, 4),
            (6, 6),
            (4, 6),
            (4, 4),  # hole 2.1
            (2, 2),
            (8, 2),
            (8, 8),
            (2, 8),
            (2, 2),  # hole 1.1
        ],
        [0, 5, 10, 15, 20],
        {
            "type": "MultiPolygon",
            "coordinates": [
                [  # poly 1
                    [(1, 1), (1, 9), (9, 9), (9, 1), (1, 1)],  # exterior 1
                    [(2, 2), (8, 2), (8, 8), (2, 8), (2, 2)],  # hole 1.1
                ],
                [  # poly 2
                    [(3, 3), (3, 7), (7, 7), (7, 3), (3, 3)],  # exterior 2
                    [(4, 4), (6, 4), (6, 6), (4, 6), (4, 4)],  # hole 2.1
                ],
                [  # poly 3
                    [
                        (4.5, 4.5),
                        (4.5, 5.5),
                        (5.5, 5.5),
                        (5.5, 4.5),
                        (4.5, 4.5),
                    ],  # exterior 3
                ],
            ],
        },
    ),
    (
        shapefile.POLYGON,  # multi polygon, nested exteriors with holes (unordered and tricky holes designed to throw off ring_sample() test)
        [
            (1, 1),
            (1, 9),
            (9, 9),
            (9, 1),
            (1, 1),  # exterior 1
            (3, 3),
            (3, 7),
            (7, 7),
            (7, 3),
            (3, 3),  # exterior 2
            (4.5, 4.5),
            (4.5, 5.5),
            (5.5, 5.5),
            (5.5, 4.5),
            (4.5, 4.5),  # exterior 3
            (4, 4),
            (4, 4),
            (6, 4),
            (6, 4),
            (6, 4),
            (6, 6),
            (4, 6),
            (4, 4),  # hole 2.1 (hole has duplicate coords)
            (2, 2),
            (3, 3),
            (4, 2),
            (8, 2),
            (8, 8),
            (4, 8),
            (2, 8),
            (2, 4),
            (
                2,
                2,
            ),  # hole 1.1 (hole coords form straight line and starts in concave orientation)
        ],
        [0, 5, 10, 15, 20 + 3],
        {
            "type": "MultiPolygon",
            "coordinates": [
                [  # poly 1
                    [(1, 1), (1, 9), (9, 9), (9, 1), (1, 1)],  # exterior 1
                    [
                        (2, 2),
                        (3, 3),
                        (4, 2),
                        (8, 2),
                        (8, 8),
                        (4, 8),
                        (2, 8),
                        (2, 4),
                        (2, 2),
                    ],  # hole 1.1
                ],
                [  # poly 2
                    [(3, 3), (3, 7), (7, 7), (7, 3), (3, 3)],  # exterior 2
                    [
                        (4, 4),
                        (4, 4),
                        (6, 4),
                        (6, 4),
                        (6, 4),
                        (6, 6),
                        (4, 6),
                        (4, 4),
                    ],  # hole 2.1
                ],
                [  # poly 3
                    [
                        (4.5, 4.5),
                        (4.5, 5.5),
                        (5.5, 5.5),
                        (5.5, 4.5),
                        (4.5, 4.5),
                    ],  # exterior 3
                ],
            ],
        },
    ),
    (
        shapefile.POLYGON,  # multi polygon, holes incl orphaned holes (unordered), should raise warning
        [
            (1, 1),
            (1, 9),
            (9, 9),
            (9, 1),
            (1, 1),  # exterior 1
            (11, 11),
            (11, 19),
            (19, 19),
            (19, 11),
            (11, 11),  # exterior 2
            (12, 12),
            (14, 12),
            (14, 14),
            (12, 14),
            (12, 12),  # hole 2.1
            (15, 15),
            (17, 15),
            (17, 17),
            (15, 17),
            (15, 15),  # hole 2.2
            (95, 95),
            (97, 95),
            (97, 97),
            (95, 97),
            (95, 95),  # hole x.1 (orphaned hole, should be interpreted as exterior)
            (2, 2),
            (4, 2),
            (4, 4),
            (2, 4),
            (2, 2),  # hole 1.1
            (5, 5),
            (7, 5),
            (7, 7),
            (5, 7),
            (5, 5),  # hole 1.2
        ],
        [0, 5, 10, 15, 20, 25, 30],
        {
            "type": "MultiPolygon",
            "coordinates": [
                [  # poly 1
                    [(1, 1), (1, 9), (9, 9), (9, 1), (1, 1)],  # exterior
                    [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)],  # hole 1
                    [(5, 5), (7, 5), (7, 7), (5, 7), (5, 5)],  # hole 2
                ],
                [  # poly 2
                    [(11, 11), (11, 19), (19, 19), (19, 11), (11, 11)],  # exterior
                    [(12, 12), (14, 12), (14, 14), (12, 14), (12, 12)],  # hole 1
                    [(15, 15), (17, 15), (17, 17), (15, 17), (15, 15)],  # hole 2
                ],
                [  # poly 3 (orphaned hole)
                    [(95, 95), (97, 95), (97, 97), (95, 97), (95, 95)],  # exterior
                ],
            ],
        },
    ),
    (
        shapefile.POLYGON,  # multi polygon, exteriors with wrong orientation (be nice and interpret as such), should raise warning
        [
            (1, 1),
            (9, 1),
            (9, 9),
            (1, 9),
            (1, 1),  # exterior with hole-orientation
            (11, 11),
            (19, 11),
            (19, 19),
            (11, 19),
            (11, 11),  # exterior with hole-orientation
        ],
        [0, 5],
        {
            "type": "MultiPolygon",
            "coordinates": [
                [  # poly 1
                    [(1, 1), (9, 1), (9, 9), (1, 9), (1, 1)],
                ],
                [  # poly 2
                    [(11, 11), (19, 11), (19, 19), (11, 19), (11, 11)],
                ],
            ],
        },
    ),
]


def test_empty_shape_geo_interface():
    """
    Assert that calling __geo_interface__
    on a Shape with no points or parts
    raises an Exception.
    """
    shape = shapefile.Shape()
    with pytest.raises(Exception):
        getattr(shape, "__geo_interface__")


@pytest.mark.parametrize("typ,points,parts,expected", geo_interface_tests)
def test_expected_shape_geo_interface(typ, points, parts, expected):
    """
    Assert that calling __geo_interface__
    on arbitrary input Shape works as expected.
    """
    shape = shapefile.Shape(typ, points, parts)
    geoj = shape.__geo_interface__
    assert geoj == expected


def test_reader_geo_interface():
    with shapefile.Reader("shapefiles/blockgroups") as r:
        geoj = r.__geo_interface__
        assert geoj["type"] == "FeatureCollection"
        assert "bbox" in geoj
        assert json.dumps(geoj)


def test_shapes_geo_interface():
    with shapefile.Reader("shapefiles/blockgroups") as r:
        geoj = r.shapes().__geo_interface__
        assert geoj["type"] == "GeometryCollection"
        assert json.dumps(geoj)


def test_shaperecords_geo_interface():
    with shapefile.Reader("shapefiles/blockgroups") as r:
        geoj = r.shapeRecords().__geo_interface__
        assert geoj["type"] == "FeatureCollection"
        assert json.dumps(geoj)


def test_shaperecord_geo_interface():
    with shapefile.Reader("shapefiles/blockgroups") as r:
        for shaperec in r:
            assert json.dumps(shaperec.__geo_interface__)


@pytest.mark.network
def test_reader_url():
    """
    Assert that Reader can open shapefiles from a url.
    """
    # test with extension
    url = "https://github.com/nvkelso/natural-earth-vector/blob/master/110m_cultural/ne_110m_admin_0_tiny_countries.shp?raw=true"
    with shapefile.Reader(url) as sf:
        for __recShape in sf.iterShapeRecords():
            pass
    assert sf.shp.closed is sf.shx.closed is sf.dbf.closed is True

    # test without extension
    url = "https://github.com/nvkelso/natural-earth-vector/blob/master/110m_cultural/ne_110m_admin_0_tiny_countries?raw=true"
    with shapefile.Reader(url) as sf:
        for __recShape in sf.iterShapeRecords():
            pass
        assert len(sf) > 0
    assert sf.shp.closed is sf.shx.closed is sf.dbf.closed is True

    # test no files found
    url = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/README.md"
    with pytest.raises(shapefile.ShapefileException):
        with shapefile.Reader(url) as sf:
            pass

    # test reading zipfile from url
    url = "https://github.com/JamesParrott/PyShp_test_shapefile/raw/main/gis_osm_natural_a_free_1.zip"
    with shapefile.Reader(url) as sf:
        for __recShape in sf.iterShapeRecords():
            pass
        assert len(sf) > 0
    assert sf.shp.closed is sf.shx.closed is sf.dbf.closed is True


def test_reader_zip():
    """
    Assert that Reader can open shapefiles inside a zipfile.
    """
    # test reading zipfile only
    with shapefile.Reader("shapefiles/blockgroups.zip") as sf:
        for __recShape in sf.iterShapeRecords():
            pass
        assert len(sf) > 0
    assert sf.shp.closed is sf.shx.closed is sf.dbf.closed is True

    # test require specific path when reading multi-shapefile zipfile
    with pytest.raises(shapefile.ShapefileException):
        with shapefile.Reader("shapefiles/blockgroups_multishapefile.zip") as sf:
            pass

    # test specifying the path when reading multi-shapefile zipfile (with extension)
    with shapefile.Reader(
        "shapefiles/blockgroups_multishapefile.zip/blockgroups2.shp"
    ) as sf:
        for __recShape in sf.iterShapeRecords():
            pass
        assert len(sf) > 0
    assert sf.shp.closed is sf.shx.closed is sf.dbf.closed is True

    # test specifying the path when reading multi-shapefile zipfile (without extension)
    with shapefile.Reader(
        "shapefiles/blockgroups_multishapefile.zip/blockgroups2"
    ) as sf:
        for __recShape in sf.iterShapeRecords():
            pass
        assert len(sf) > 0
    assert sf.shp.closed is sf.shx.closed is sf.dbf.closed is True

    # test raising error when can't find shapefile inside zipfile
    with pytest.raises(shapefile.ShapefileException):
        with shapefile.Reader("shapefiles/empty_zipfile.zip") as sf:
            pass


def test_reader_close_path():
    """
    Assert that manually calling Reader.close()
    closes the shp, shx, and dbf files
    on exit, if given paths.
    """
    # note uses an actual shapefile from
    # the projects "shapefiles" directory
    sf = shapefile.Reader("shapefiles/blockgroups.shp")
    sf.close()

    assert sf.shp.closed is True
    assert sf.dbf.closed is True
    assert sf.shx.closed is True

    # check that can read again
    sf = shapefile.Reader("shapefiles/blockgroups.shp")
    sf.close()


def test_reader_close_filelike():
    """
    Assert that manually calling Reader.close()
    leaves the shp, shx, and dbf files open
    on exit, if given filelike objects.
    """
    # note uses an actual shapefile from
    # the projects "shapefiles" directory
    shp = open("shapefiles/blockgroups.shp", mode="rb")
    shx = open("shapefiles/blockgroups.shx", mode="rb")
    dbf = open("shapefiles/blockgroups.dbf", mode="rb")
    sf = shapefile.Reader(shp=shp, shx=shx, dbf=dbf)
    sf.close()

    assert sf.shp.closed is False
    assert sf.dbf.closed is False
    assert sf.shx.closed is False

    # check that can read again
    sf = shapefile.Reader(shp=shp, shx=shx, dbf=dbf)
    sf.close()


def test_reader_context_path():
    """
    Assert that using the context manager
    closes the shp, shx, and dbf files
    on exit, if given paths.
    """
    # note uses an actual shapefile from
    # the projects "shapefiles" directory
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        pass

    assert sf.shp.closed is True
    assert sf.dbf.closed is True
    assert sf.shx.closed is True

    # check that can read again
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        pass


def test_reader_context_filelike():
    """
    Assert that using the context manager
    leaves the shp, shx, and dbf files open
    on exit, if given filelike objects.
    """
    # note uses an actual shapefile from
    # the projects "shapefiles" directory
    shp = open("shapefiles/blockgroups.shp", mode="rb")
    shx = open("shapefiles/blockgroups.shx", mode="rb")
    dbf = open("shapefiles/blockgroups.dbf", mode="rb")
    with shapefile.Reader(shp=shp, shx=shx, dbf=dbf) as sf:
        pass

    assert sf.shp.closed is False
    assert sf.dbf.closed is False
    assert sf.shx.closed is False

    # check that can read again
    with shapefile.Reader(shp=shp, shx=shx, dbf=dbf) as sf:
        pass


def test_reader_shapefile_type():
    """
    Assert that the type of the shapefile
    is returned correctly.
    """
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        assert sf.shapeType == 5  # 5 means Polygon
        assert sf.shapeType == shapefile.POLYGON
        assert sf.shapeTypeName == "POLYGON"


def test_reader_shapefile_length():
    """
    Assert that the length the reader gives us
    matches up with the number of records
    in the file.
    """
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        assert len(sf) == len(sf.shapes())


def test_shape_metadata():
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        shape = sf.shape(0)
        assert shape.shapeType == 5  # Polygon
        assert shape.shapeType == shapefile.POLYGON
        assert sf.shapeTypeName == "POLYGON"


def test_reader_fields():
    """
    Assert that the reader's fields attribute
    gives the shapefile's fields as a list.
    Assert that each field has a name,
    type, field length, and decimal length.
    """
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        fields = sf.fields
        assert isinstance(fields, list)

        field = fields[0]
        assert isinstance(field[0], str)  # field name
        assert field[1] in ["C", "N", "F", "L", "D", "M"]  # field type
        assert isinstance(field[2], int)  # field length
        assert isinstance(field[3], int)  # decimal length


def test_reader_shapefile_extension_ignored():
    """
    Assert that the filename's extension is
    ignored when reading a shapefile.
    """
    base = "shapefiles/blockgroups"
    ext = ".abc"
    filename = base + ext
    with shapefile.Reader(filename) as sf:
        assert len(sf) == 663

    # assert test.abc does not exist
    assert not os.path.exists(filename)


def test_reader_pathlike():
    """
    Assert that path-like objects can be read.
    """
    base = Path("shapefiles")
    with shapefile.Reader(base / "blockgroups") as sf:
        assert len(sf) == 663


def test_reader_dbf_only():
    """
    Assert that specifying just the
    dbf argument to the shapefile reader
    reads just the dbf file.
    """
    with shapefile.Reader(dbf="shapefiles/blockgroups.dbf") as sf:
        assert len(sf) == 663
        record = sf.record(3)
        assert record[1:3] == ["060750601001", 4715]


def test_reader_shp_shx_only():
    """
    Assert that specifying just the
    shp and shx argument to the shapefile reader
    reads just the shp and shx file.
    """
    with shapefile.Reader(
        shp="shapefiles/blockgroups.shp", shx="shapefiles/blockgroups.shx"
    ) as sf:
        assert len(sf) == 663
        shape = sf.shape(3)
        assert len(shape.points) == 173


def test_reader_shp_dbf_only():
    """
    Assert that specifying just the
    shp and shx argument to the shapefile reader
    reads just the shp and dbf file.
    """
    with shapefile.Reader(
        shp="shapefiles/blockgroups.shp", dbf="shapefiles/blockgroups.dbf"
    ) as sf:
        assert len(sf) == 663
        shape = sf.shape(3)
        assert len(shape.points) == 173
        record = sf.record(3)
        assert record[1:3] == ["060750601001", 4715]


def test_reader_shp_only():
    """
    Assert that specifying just the
    shp argument to the shapefile reader
    reads just the shp file (shx optional).
    """
    with shapefile.Reader(shp="shapefiles/blockgroups.shp") as sf:
        assert len(sf) == 663
        shape = sf.shape(3)
        assert len(shape.points) == 173


def test_reader_filelike_dbf_only():
    """
    Assert that specifying just the
    dbf argument to the shapefile reader
    reads just the dbf file.
    """
    with shapefile.Reader(dbf=open("shapefiles/blockgroups.dbf", "rb")) as sf:
        assert len(sf) == 663
        record = sf.record(3)
        assert record[1:3] == ["060750601001", 4715]


def test_reader_filelike_shp_shx_only():
    """
    Assert that specifying just the
    shp and shx argument to the shapefile reader
    reads just the shp and shx file.
    """
    with shapefile.Reader(
        shp=open("shapefiles/blockgroups.shp", "rb"),
        shx=open("shapefiles/blockgroups.shx", "rb"),
    ) as sf:
        assert len(sf) == 663
        shape = sf.shape(3)
        assert len(shape.points) == 173


def test_reader_filelike_shp_dbf_only():
    """
    Assert that specifying just the
    shp and shx argument to the shapefile reader
    reads just the shp and dbf file.
    """
    with shapefile.Reader(
        shp=open("shapefiles/blockgroups.shp", "rb"),
        dbf=open("shapefiles/blockgroups.dbf", "rb"),
    ) as sf:
        assert len(sf) == 663
        shape = sf.shape(3)
        assert len(shape.points) == 173
        record = sf.record(3)
        assert record[1:3] == ["060750601001", 4715]


def test_reader_filelike_shp_only():
    """
    Assert that specifying just the
    shp argument to the shapefile reader
    reads just the shp file (shx optional).
    """
    with shapefile.Reader(shp=open("shapefiles/blockgroups.shp", "rb")) as sf:
        assert len(sf) == 663
        shape = sf.shape(3)
        assert len(shape.points) == 173


def test_reader_shapefile_delayed_load():
    """
    Assert that the filename's extension is
    ignored when reading a shapefile.
    """
    with shapefile.Reader() as sf:
        # assert that data request raises exception, since no file has been provided yet
        with pytest.raises(shapefile.ShapefileException):
            sf.shape(0)
        # assert that works after loading file manually
        sf.load("shapefiles/blockgroups")
        assert len(sf) == 663


def test_records_match_shapes():
    """
    Assert that the number of records matches
    the number of shapes in the shapefile.
    """
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        records = sf.records()
        shapes = sf.shapes()
        assert len(records) == len(shapes)


def test_record_attributes(fields=None):
    """
    Assert that record retrieves all relevant values and can
    be accessed as attributes and dictionary items.
    """
    # note
    # second element in fields matches first element
    # in record because records dont have DeletionFlag
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        for i in range(len(sf)):
            # full record
            full_record = sf.record(i)
            # user-fetched record
            if fields is not None:
                # only a subset of fields
                record = sf.record(i, fields=fields)
            else:
                # default all fields
                record = full_record
                fields = [
                    field[0] for field in sf.fields[1:]
                ]  # fieldnames, sans del flag
            # check correct length
            assert len(record) == len(set(fields))
            # check record values (should be in same order as shapefile fields)
            i = 0
            for field in sf.fields:
                field_name = field[0]
                if field_name in fields:
                    assert (
                        record[i] == record[field_name] == getattr(record, field_name)
                    )
                    i += 1


def test_record_subfields():
    """
    Assert that reader correctly retrieves only a subset
    of fields when specified.
    """
    fields = ["AREA", "POP1990", "MALES", "FEMALES", "MOBILEHOME"]
    test_record_attributes(fields=fields)


def test_record_subfields_unordered():
    """
    Assert that reader correctly retrieves only a subset
    of fields when specified, given in random order but
    retrieved in the order of the shapefile fields.
    """
    fields = sorted(["AREA", "POP1990", "MALES", "FEMALES", "MOBILEHOME"])
    test_record_attributes(fields=fields)


def test_record_subfields_delflag_notvalid():
    """
    Assert that reader does not consider DeletionFlag as a valid field name.
    """
    fields = ["DeletionFlag", "AREA", "POP1990", "MALES", "FEMALES", "MOBILEHOME"]
    with pytest.raises(ValueError):
        test_record_attributes(fields=fields)


def test_record_subfields_duplicates():
    """
    Assert that reader correctly retrieves only a subset
    of fields when specified, handling duplicate input fields.
    """
    fields = ["AREA", "AREA", "AREA", "MALES", "MALES", "MOBILEHOME"]
    test_record_attributes(fields=fields)
    # check that only 3 values
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        rec = sf.record(0, fields=fields)
        assert len(rec) == len(set(fields))


def test_record_subfields_empty():
    """
    Assert that reader does not retrieve any fields when given
    an empty list.
    """
    fields = []
    test_record_attributes(fields=fields)
    # check that only 0 values
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        rec = sf.record(0, fields=fields)
        assert len(rec) == 0


def test_record_as_dict():
    """
    Assert that a record object can be converted
    into a dictionary and data remains correct.
    """
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        record = sf.record(0)
        as_dict = record.as_dict()

        assert len(record) == len(as_dict)
        for key, value in as_dict.items():
            assert record[key] == value


def test_record_oid():
    """
    Assert that the record's oid attribute returns
    its index in the shapefile.
    """
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        for i in range(len(sf)):
            record = sf.record(i)
            assert record.oid == i

        for i, record in enumerate(sf.records()):
            assert record.oid == i

        for i, record in enumerate(sf.iterRecords()):
            assert record.oid == i

        for i, shaperec in enumerate(sf.iterShapeRecords()):
            assert shaperec.record.oid == i


def test_iterRecords_start_stop():
    """
    Assert that Reader.iterRecords(start, stop)
    returns the correct records, as if searched for
    by index with Reader.record
    """

    with shapefile.Reader("shapefiles/blockgroups") as sf:
        N = len(sf)

        # Arbitrary selection of record indices
        # (there are 663 records in blockgroups.dbf).
        for i in [
            0,
            1,
            2,
            3,
            5,
            11,
            17,
            33,
            51,
            103,
            170,
            234,
            435,
            543,
            N - 3,
            N - 2,
            N - 1,
        ]:
            for record in sf.iterRecords(start=i):
                assert record == sf.record(record.oid)

            for record in sf.iterRecords(stop=i):
                assert record == sf.record(record.oid)

            for stop in range(i, len(sf)):
                # test negative indexing from end, as well as
                # positive values of stop, and its default
                for stop_arg in (stop, stop - len(sf)):
                    for record in sf.iterRecords(start=i, stop=stop_arg):
                        assert record == sf.record(record.oid)


def test_shape_oid():
    """
    Assert that the shape's oid attribute returns
    its index in the shapefile.
    """
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        for i in range(len(sf)):
            shape = sf.shape(i)
            assert shape.oid == i

        for i, shape in enumerate(sf.shapes()):
            assert shape.oid == i

        for i, shape in enumerate(sf.iterShapes()):
            assert shape.oid == i

        for i, shaperec in enumerate(sf.iterShapeRecords()):
            assert shaperec.shape.oid == i


def test_shape_oid_no_shx():
    """
    Assert that the shape's oid attribute returns
    its index in the shapefile, when shx file is missing.
    """
    basename = "shapefiles/blockgroups"
    shp = open(basename + ".shp", "rb")
    dbf = open(basename + ".dbf", "rb")
    with shapefile.Reader(shp=shp, dbf=dbf) as sf:
        with shapefile.Reader(basename) as sf_expected:
            for i in range(len(sf)):
                shape = sf.shape(i)
                assert shape.oid == i
                shape_expected = sf_expected.shape(i)
                assert shape.__geo_interface__ == shape_expected.__geo_interface__

            for i, shape in enumerate(sf.shapes()):
                assert shape.oid == i
                shape_expected = sf_expected.shape(i)
                assert shape.__geo_interface__ == shape_expected.__geo_interface__

            for i, shape in enumerate(sf.iterShapes()):
                assert shape.oid == i
                shape_expected = sf_expected.shape(i)
                assert shape.__geo_interface__ == shape_expected.__geo_interface__

            for i, shaperec in enumerate(sf.iterShapeRecords()):
                assert shaperec.shape.oid == i
                shape_expected = sf_expected.shape(i)
                assert (
                    shaperec.shape.__geo_interface__ == shape_expected.__geo_interface__
                )


def test_reader_offsets():
    """
    Assert that reader will not read the shx offsets unless necessary,
    i.e. requesting a shape index.
    """
    basename = "shapefiles/blockgroups"
    with shapefile.Reader(basename) as sf:
        # shx offsets should not be read during loading
        assert not sf._offsets
        # reading a shape index should trigger reading offsets from shx file
        sf.shape(3)
        assert len(sf._offsets) == len(sf.shapes())


def test_reader_offsets_no_shx():
    """
    Assert that reading a shapefile without a shx file will not build
    the offsets unless necessary, i.e. reading all the shapes.
    """
    basename = "shapefiles/blockgroups"
    shp = open(basename + ".shp", "rb")
    dbf = open(basename + ".dbf", "rb")
    with shapefile.Reader(shp=shp, dbf=dbf) as sf:
        # offsets should not be built during loading
        assert not sf._offsets
        # reading a shape index should iterate to the shape
        # but the list of offsets should remain empty
        sf.shape(3)
        assert not sf._offsets
        # reading all the shapes should build the list of offsets
        shapes = sf.shapes()
        assert len(sf._offsets) == len(shapes)


def test_reader_numshapes():
    """
    Assert that reader reads the numShapes attribute from the
    shx file header during loading.
    """
    basename = "shapefiles/blockgroups"
    with shapefile.Reader(basename) as sf:
        # numShapes should be set during loading
        assert sf.numShapes is not None
        # numShapes should equal the number of shapes
        assert sf.numShapes == len(sf.shapes())


def test_reader_numshapes_no_shx():
    """
    Assert that reading a shapefile without a shx file will have
    an unknown value for the numShapes attribute (None), and that
    reading all the shapes will set the numShapes attribute.
    """
    basename = "shapefiles/blockgroups"
    shp = open(basename + ".shp", "rb")
    dbf = open(basename + ".dbf", "rb")
    with shapefile.Reader(shp=shp, dbf=dbf) as sf:
        # numShapes should be unknown due to missing shx file
        assert sf.numShapes is None
        # numShapes should be set after reading all the shapes
        shapes = sf.shapes()
        assert sf.numShapes == len(shapes)


def test_reader_len():
    """
    Assert that calling len() on reader is equal to length of
    all shapes and records.
    """
    basename = "shapefiles/blockgroups"
    with shapefile.Reader(basename) as sf:
        assert len(sf) == len(sf.records()) == len(sf.shapes())


def test_reader_len_not_loaded():
    """
    Assert that calling len() on reader that hasn't loaded a shapefile
    yet is equal to 0.
    """
    with shapefile.Reader() as sf:
        assert len(sf) == 0


def test_reader_len_dbf_only():
    """
    Assert that calling len() on reader when reading a dbf file only,
    is equal to length of all records.
    """
    basename = "shapefiles/blockgroups"
    dbf = open(basename + ".dbf", "rb")
    with shapefile.Reader(dbf=dbf) as sf:
        assert len(sf) == len(sf.records())


def test_reader_len_no_dbf():
    """
    Assert that calling len() on reader when dbf file is missing,
    is equal to length of all shapes.
    """
    basename = "shapefiles/blockgroups"
    shp = open(basename + ".shp", "rb")
    shx = open(basename + ".shx", "rb")
    with shapefile.Reader(shp=shp, shx=shx) as sf:
        assert len(sf) == len(sf.shapes())


def test_reader_len_no_dbf_shx():
    """
    Assert that calling len() on reader when dbf and shx file is missing,
    is equal to length of all shapes.
    """
    basename = "shapefiles/blockgroups"
    shp = open(basename + ".shp", "rb")
    with shapefile.Reader(shp=shp) as sf:
        assert len(sf) == len(sf.shapes())


def test_reader_corrupt_files():
    """
    Assert that reader is able to handle corrupt files by
    strictly going off the header information.
    """
    basename = "shapefiles/test/corrupt_too_long"

    # write a shapefile with junk byte data at end of files
    with shapefile.Writer(basename) as w:
        w.field("test", "C", 50)
        # add 10 line geoms
        for _ in range(10):
            w.record("value")
            w.line([[(1, 1), (1, 2), (2, 2)]])
        # add junk byte data to end of dbf and shp files
        w.dbf.write(b"12345")
        w.shp.write(b"12345")

    # read the corrupt shapefile and assert that it reads correctly
    with shapefile.Reader(basename) as sf:
        # assert correct shapefile length metadata
        assert len(sf) == sf.numRecords == sf.numShapes == 10
        # assert that records are read without error
        assert len(sf.records()) == 10
        # assert that didn't read the extra junk data
        stopped = sf.dbf.tell()
        sf.dbf.seek(0, 2)
        end = sf.dbf.tell()
        assert (end - stopped) == 5
        # assert that shapes are read without error
        assert len(sf.shapes()) == 10
        # assert that didn't read the extra junk data
        stopped = sf.shp.tell()
        sf.shp.seek(0, 2)
        end = sf.shp.tell()
        assert (end - stopped) == 5


def test_bboxfilter_shape():
    """
    Assert that applying the bbox filter to shape() correctly ignores the shape
    if it falls outside, and returns it if inside.
    """
    inside = [-122.4, 37.8, -122.35, 37.82]
    outside = list(inside)
    outside[0] *= 10
    outside[2] *= 10
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        assert sf.shape(0, bbox=inside) is not None
        assert sf.shape(0, bbox=outside) is None


def test_bboxfilter_shapes():
    """
    Assert that applying the bbox filter to shapes() correctly ignores shapes
    that fall outside, and returns those that fall inside.
    """
    bbox = [-122.4, 37.8, -122.35, 37.82]
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        # apply bbox filter
        shapes = sf.shapes(bbox=bbox)
        # manually check bboxes
        manual = shapefile.Shapes()
        for shape in sf.iterShapes():
            if shapefile.bbox_overlap(shape.bbox, bbox):
                manual.append(shape)
        # compare
        assert len(shapes) == len(manual)
        # check that they line up
        for shape, man in zip(shapes, manual):
            assert shape.oid == man.oid
            assert shape.__geo_interface__ == man.__geo_interface__


def test_bboxfilter_shapes_outside():
    """
    Assert that applying the bbox filter to shapes() correctly returns
    no shapes when the bbox is outside the entire shapefile.
    """
    bbox = [-180, 89, -179, 90]
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        shapes = sf.shapes(bbox=bbox)
        assert len(shapes) == 0


def test_bboxfilter_itershapes():
    """
    Assert that applying the bbox filter to iterShapes() correctly ignores shapes
    that fall outside, and returns those that fall inside.
    """
    bbox = [-122.4, 37.8, -122.35, 37.82]
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        # apply bbox filter
        shapes = list(sf.iterShapes(bbox=bbox))
        # manually check bboxes
        manual = shapefile.Shapes()
        for shape in sf.iterShapes():
            if shapefile.bbox_overlap(shape.bbox, bbox):
                manual.append(shape)
        # compare
        assert len(shapes) == len(manual)
        # check that they line up
        for shape, man in zip(shapes, manual):
            assert shape.oid == man.oid
            assert shape.__geo_interface__ == man.__geo_interface__


def test_bboxfilter_shaperecord():
    """
    Assert that applying the bbox filter to shapeRecord() correctly ignores the shape
    if it falls outside, and returns it if inside.
    """
    inside = [-122.4, 37.8, -122.35, 37.82]
    outside = list(inside)
    outside[0] *= 10
    outside[2] *= 10
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        # inside
        shaperec = sf.shapeRecord(0, bbox=inside)
        assert shaperec is not None
        assert shaperec.shape.oid == shaperec.record.oid
        # outside
        assert sf.shapeRecord(0, bbox=outside) is None


def test_bboxfilter_shaperecords():
    """
    Assert that applying the bbox filter to shapeRecords() correctly ignores shapes
    that fall outside, and returns those that fall inside.
    """
    bbox = [-122.4, 37.8, -122.35, 37.82]
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        # apply bbox filter
        shaperecs = sf.shapeRecords(bbox=bbox)
        # manually check bboxes
        manual = shapefile.ShapeRecords()
        for shaperec in sf.iterShapeRecords():
            if shapefile.bbox_overlap(shaperec.shape.bbox, bbox):
                manual.append(shaperec)
        # compare
        assert len(shaperecs) == len(manual)
        # check that they line up
        for shaperec, man in zip(shaperecs, manual):
            # oids
            assert shaperec.shape.oid == shaperec.record.oid
            # same shape as manual
            assert shaperec.shape.oid == man.shape.oid
            assert shaperec.shape.__geo_interface__ == man.shape.__geo_interface__
            # same record as manual
            assert shaperec.record.oid == man.record.oid
            assert shaperec.record == man.record


def test_bboxfilter_itershaperecords():
    """
    Assert that applying the bbox filter to iterShapeRecords() correctly ignores shapes
    that fall outside, and returns those that fall inside.
    """
    bbox = [-122.4, 37.8, -122.35, 37.82]
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        # apply bbox filter
        shaperecs = list(sf.iterShapeRecords(bbox=bbox))
        # manually check bboxes
        manual = shapefile.ShapeRecords()
        for shaperec in sf.iterShapeRecords():
            if shapefile.bbox_overlap(shaperec.shape.bbox, bbox):
                manual.append(shaperec)
        # compare
        assert len(shaperecs) == len(manual)
        # check that they line up
        for shaperec, man in zip(shaperecs, manual):
            # oids
            assert shaperec.shape.oid == shaperec.record.oid
            # same shape as manual
            assert shaperec.shape.oid == man.shape.oid
            assert shaperec.shape.__geo_interface__ == man.shape.__geo_interface__
            # same record as manual
            assert shaperec.record.oid == man.record.oid
            assert shaperec.record == man.record


def test_shaperecords_shaperecord():
    """
    Assert that shapeRecords returns a list of
    ShapeRecord objects.
    Assert that shapeRecord returns a single
    ShapeRecord at the given index.
    """
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        shaperecs = sf.shapeRecords()
        shaperec = sf.shapeRecord(0)
        should_match = shaperecs[0]

        # assert record is equal
        assert shaperec.record == should_match.record

        # assert shape is equal
        shaperec_json = shaperec.shape.__geo_interface__
        should_match_json = should_match.shape.__geo_interface__
        assert shaperec_json == should_match_json


def test_shaperecord_shape():
    """
    Assert that a ShapeRecord object has a shape
    attribute that contains shape data.
    """
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        shaperec = sf.shapeRecord(3)
        shape = shaperec.shape
        point = shape.points[0]
        assert len(point) == 2


def test_shaperecord_record():
    """
    Assert that a ShapeRecord object has a record
    attribute that contains record data.
    """
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        shaperec = sf.shapeRecord(3)
        record = shaperec.record

        assert record[1:3] == ["060750601001", 4715]


def test_write_field_name_limit(tmpdir):
    """
    Abc...
    """
    filename = tmpdir.join("test.shp").strpath
    with shapefile.Writer(filename) as writer:
        writer.field("a" * 5, "C")  # many under length limit
        writer.field("a" * 9, "C")  # 1 under length limit
        writer.field("a" * 10, "C")  # at length limit
        writer.field("a" * 11, "C")  # 1 over length limit
        writer.field("a" * 20, "C")  # many over limit

    with shapefile.Reader(filename) as reader:
        fields = reader.fields[1:]
        assert len(fields[0][0]) == 5
        assert len(fields[1][0]) == 9
        assert len(fields[2][0]) == 10
        assert len(fields[3][0]) == 10
        assert len(fields[4][0]) == 10


def test_write_shp_only(tmpdir):
    """
    Assert that specifying just the
    shp argument to the shapefile writer
    creates just a shp file.
    """
    filename = tmpdir.join("test").strpath
    with shapefile.Writer(shp=filename + ".shp") as writer:
        writer.point(1, 1)
    assert writer.shp and not writer.shx and not writer.dbf
    assert writer.shpNum == 1
    assert len(writer) == 1
    assert writer.shp.closed is True

    # assert test.shp exists
    assert os.path.exists(filename + ".shp")

    # test that can read shapes
    with shapefile.Reader(shp=filename + ".shp") as reader:
        assert reader.shp and not reader.shx and not reader.dbf
        assert (reader.numRecords, reader.numShapes) == (
            None,
            None,
        )  # numShapes is unknown in the absence of shx file
        assert len(reader.shapes()) == 1

    # assert test.shx does not exist
    assert not os.path.exists(filename + ".shx")

    # assert test.dbf does not exist
    assert not os.path.exists(filename + ".dbf")


def test_write_shp_shx_only(tmpdir):
    """
    Assert that specifying just the shp and
    shx argument to the shapefile writer
    creates just a shp and shx file.
    """
    filename = tmpdir.join("test").strpath
    with shapefile.Writer(shp=filename + ".shp", shx=filename + ".shx") as writer:
        writer.point(1, 1)
    assert writer.shp and writer.shx and not writer.dbf
    assert writer.shpNum == 1
    assert len(writer) == 1
    assert writer.shp.closed is writer.shx.closed is True

    # assert test.shp exists
    assert os.path.exists(filename + ".shp")

    # assert test.shx exists
    assert os.path.exists(filename + ".shx")

    # test that can read shapes and offsets
    with shapefile.Reader(shp=filename + ".shp", shx=filename + ".shx") as reader:
        assert reader.shp and reader.shx and not reader.dbf
        assert (reader.numRecords, reader.numShapes) == (None, 1)
        reader.shape(0)  # trigger reading of shx offsets
        assert len(reader._offsets) == 1
        assert len(reader.shapes()) == 1

    # assert test.dbf does not exist
    assert not os.path.exists(filename + ".dbf")


def test_write_shp_dbf_only(tmpdir):
    """
    Assert that specifying just the
    shp and dbf argument to the shapefile writer
    creates just a shp and dbf file.
    """
    filename = tmpdir.join("test").strpath
    with shapefile.Writer(shp=filename + ".shp", dbf=filename + ".dbf") as writer:
        writer.field("field1", "C")  # required to create a valid dbf file
        writer.record("value")
        writer.point(1, 1)
    assert writer.shp and not writer.shx and writer.dbf
    assert writer.shpNum == writer.recNum == 1
    assert len(writer) == 1
    assert writer.shp.closed is writer.dbf.closed is True

    # assert test.shp exists
    assert os.path.exists(filename + ".shp")

    # assert test.dbf exists
    assert os.path.exists(filename + ".dbf")

    # test that can read records and shapes
    with shapefile.Reader(shp=filename + ".shp", dbf=filename + ".dbf") as reader:
        assert reader.shp and not reader.shx and reader.dbf
        assert (reader.numRecords, reader.numShapes) == (
            1,
            None,
        )  # numShapes is unknown in the absence of shx file
        assert len(reader.records()) == 1
        assert len(reader.shapes()) == 1

    # assert test.shx does not exist
    assert not os.path.exists(filename + ".shx")


def test_write_dbf_only(tmpdir):
    """
    Assert that specifying just the
    dbf argument to the shapefile writer
    creates just a dbf file.
    """
    filename = tmpdir.join("test").strpath
    with shapefile.Writer(dbf=filename + ".dbf") as writer:
        writer.field("field1", "C")  # required to create a valid dbf file
        writer.record("value")
    assert not writer.shp and not writer.shx and writer.dbf
    assert writer.recNum == 1
    assert len(writer) == 1
    assert writer.dbf.closed is True

    # assert test.dbf exists
    assert os.path.exists(filename + ".dbf")

    # test that can read records
    with shapefile.Reader(dbf=filename + ".dbf") as reader:
        assert not writer.shp and not writer.shx and writer.dbf
        assert (reader.numRecords, reader.numShapes) == (1, None)
        assert len(reader.records()) == 1

    # assert test.shp does not exist
    assert not os.path.exists(filename + ".shp")

    # assert test.shx does not exist
    assert not os.path.exists(filename + ".shx")


def test_write_default_shp_shx_dbf(tmpdir):
    """
    Assert that creating the shapefile writer without
    specifying the shp, shx, or dbf arguments
    creates a set of shp, shx, and dbf files.
    """
    filename = tmpdir.join("test").strpath
    with shapefile.Writer(filename) as writer:
        writer.field("field1", "C")  # required to create a valid dbf file
        writer.record("value")
        writer.null()

    # assert shp, shx, dbf files exist
    assert os.path.exists(filename + ".shp")
    assert os.path.exists(filename + ".shx")
    assert os.path.exists(filename + ".dbf")


def test_write_pathlike(tmpdir):
    """
    Assert that path-like objects can be written.
    Similar to test_write_default_shp_shx_dbf.
    """
    filename = tmpdir.join("test")
    assert not isinstance(filename, str)
    with shapefile.Writer(filename) as writer:
        writer.field("field1", "C")
        writer.record("value")
        writer.null()
    assert (filename + ".shp").ensure()
    assert (filename + ".shx").ensure()
    assert (filename + ".dbf").ensure()


def test_write_filelike(tmpdir):
    """
    Assert that file-like objects are written correctly.
    """
    shp = open(tmpdir.join("test.shp").strpath, mode="wb+")
    shx = open(tmpdir.join("test.shx").strpath, mode="wb+")
    dbf = open(tmpdir.join("test.dbf").strpath, mode="wb+")
    with shapefile.Writer(shx=shx, dbf=dbf, shp=shp) as writer:
        writer.field("field1", "C")  # required to create a valid dbf file
        writer.record("value")
        writer.null()

    # test that filelike objects were written correctly
    with shapefile.Reader(shp=shp, shx=shx, dbf=dbf) as reader:
        assert len(reader) == 1
        assert reader.shape(0).shapeType == shapefile.NULL


def test_write_close_path(tmpdir):
    """
    Assert that the Writer close() method
    closes the shp, shx, and dbf files
    on exit, if given paths.
    """
    sf = shapefile.Writer(tmpdir.join("test"))
    sf.field("field1", "C")  # required to create a valid dbf file
    sf.record("value")
    sf.null()
    sf.close()

    assert sf.shp.closed is True
    assert sf.dbf.closed is True
    assert sf.shx.closed is True

    # test that opens and reads correctly after
    with shapefile.Reader(tmpdir.join("test")) as reader:
        assert len(reader) == 1
        assert reader.shape(0).shapeType == shapefile.NULL


def test_write_close_filelike(tmpdir):
    """
    Assert that the Writer close() method
    leaves the shp, shx, and dbf files open
    on exit, if given filelike objects.
    """
    shp = open(tmpdir.join("test.shp").strpath, mode="wb+")
    shx = open(tmpdir.join("test.shx").strpath, mode="wb+")
    dbf = open(tmpdir.join("test.dbf").strpath, mode="wb+")
    sf = shapefile.Writer(shx=shx, dbf=dbf, shp=shp)
    sf.field("field1", "C")  # required to create a valid dbf file
    sf.record("value")
    sf.null()
    sf.close()

    assert sf.shp.closed is False
    assert sf.dbf.closed is False
    assert sf.shx.closed is False

    # test that opens and reads correctly after
    with shapefile.Reader(shx=shx, dbf=dbf, shp=shp) as reader:
        assert len(reader) == 1
        assert reader.shape(0).shapeType == shapefile.NULL


def test_write_context_path(tmpdir):
    """
    Assert that the Writer context manager
    closes the shp, shx, and dbf files
    on exit, if given paths.
    """
    with shapefile.Writer(tmpdir.join("test")) as sf:
        sf.field("field1", "C")  # required to create a valid dbf file
        sf.record("value")
        sf.null()

    assert sf.shp.closed is True
    assert sf.dbf.closed is True
    assert sf.shx.closed is True

    # test that opens and reads correctly after
    with shapefile.Reader(tmpdir.join("test")) as reader:
        assert len(reader) == 1
        assert reader.shape(0).shapeType == shapefile.NULL


def test_write_context_filelike(tmpdir):
    """
    Assert that the Writer context manager
    leaves the shp, shx, and dbf files open
    on exit, if given filelike objects.
    """
    shp = open(tmpdir.join("test.shp").strpath, mode="wb+")
    shx = open(tmpdir.join("test.shx").strpath, mode="wb+")
    dbf = open(tmpdir.join("test.dbf").strpath, mode="wb+")
    with shapefile.Writer(shx=shx, dbf=dbf, shp=shp) as sf:
        sf.field("field1", "C")  # required to create a valid dbf file
        sf.record("value")
        sf.null()

    assert sf.shp.closed is False
    assert sf.dbf.closed is False
    assert sf.shx.closed is False

    # test that opens and reads correctly after
    with shapefile.Reader(shx=shx, dbf=dbf, shp=shp) as reader:
        assert len(reader) == 1
        assert reader.shape(0).shapeType == shapefile.NULL


def test_write_shapefile_extension_ignored(tmpdir):
    """
    Assert that the filename's extension is
    ignored when creating a shapefile.
    """
    base = "test"
    ext = ".abc"
    filename = tmpdir.join(base + ext).strpath
    with shapefile.Writer(filename) as writer:
        writer.field("field1", "C")  # required to create a valid dbf file

    # assert shp, shx, dbf files exist
    basepath = tmpdir.join(base).strpath
    assert os.path.exists(basepath + ".shp")
    assert os.path.exists(basepath + ".shx")
    assert os.path.exists(basepath + ".dbf")

    # assert test.abc does not exist
    assert not os.path.exists(basepath + ext)


def test_write_record(tmpdir):
    """
    Test that .record() correctly writes a record using either a list of *args
    or a dict of **kwargs.
    """
    filename = tmpdir.join("test.shp").strpath
    with shapefile.Writer(filename) as writer:
        writer.autoBalance = True

        writer.field("one", "C")
        writer.field("two", "C")
        writer.field("three", "C")
        writer.field("four", "C")

        values = ["one", "two", "three", "four"]
        writer.record(*values)
        writer.record(*values)

        valuedict = dict(zip(values, values))
        writer.record(**valuedict)
        writer.record(**valuedict)

    with shapefile.Reader(filename) as reader:
        for record in reader.iterRecords():
            assert record == values


def test_write_partial_record(tmpdir):
    """
    Test that .record() correctly writes a partial record (given only some of the values)
    using either a list of *args or a dict of **kwargs. Should fill in the gaps.
    """
    filename = tmpdir.join("test.shp").strpath
    with shapefile.Writer(filename) as writer:
        writer.autoBalance = True

        writer.field("one", "C")
        writer.field("two", "C")
        writer.field("three", "C")
        writer.field("four", "C")

        values = ["one", "two"]
        writer.record(*values)
        writer.record(*values)

        valuedict = dict(zip(values, values))
        writer.record(**valuedict)
        writer.record(**valuedict)

    with shapefile.Reader(filename) as reader:
        expected = list(values)
        expected.extend(["", ""])
        for record in reader.iterRecords():
            assert record == expected

        assert len(reader.records()) == 4


def test_write_geojson(tmpdir):
    """
    Assert that the output of geo interface can be written to json.
    """
    filename = tmpdir.join("test").strpath
    with shapefile.Writer(filename) as w:
        w.field("TEXT", "C")
        w.field("NUMBER", "N")
        w.field("DATE", "D")
        w.record("text", 123, datetime.date(1898, 1, 30))
        w.record("text", 123, [1998, 1, 30])
        w.record("text", 123, "19980130")
        w.record("text", 123, "-9999999")  # faulty date
        w.record(None, None, None)
        w.null()
        w.null()
        w.null()
        w.null()
        w.null()

    with shapefile.Reader(filename) as r:
        for feat in r:
            assert json.dumps(feat.__geo_interface__)
        assert json.dumps(r.shapeRecords().__geo_interface__)
        assert json.dumps(r.__geo_interface__)


shape_types = [
    k for k in shapefile.SHAPETYPE_LOOKUP.keys() if k != 31
]  # exclude multipatch


@pytest.mark.parametrize("shape_type", shape_types)
def test_write_empty_shapefile(tmpdir, shape_type):
    """
    Assert that can write an empty shapefile, for all different shape types.
    """
    filename = tmpdir.join("test").strpath
    with shapefile.Writer(filename, shapeType=shape_type) as w:
        w.field("field1", "C")  # required to create a valid dbf file

    with shapefile.Reader(filename) as r:
        # test correct shape type
        assert r.shapeType == shape_type
        # test length 0
        assert len(r) == r.numRecords == r.numShapes == 0
        # test records are empty
        assert len(r.records()) == 0
        # test shapes are empty
        assert len(r.shapes()) == 0
