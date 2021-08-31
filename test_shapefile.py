"""
This module tests the functionality of shapefile.py.
"""
# std lib imports
import os.path

# third party imports
import pytest
import json
import datetime

# our imports
import shapefile

# define various test shape tuples of (type, points, parts indexes, and expected geo interface output)
geo_interface_tests = [ (shapefile.POINT, # point
                            [(1,1)],
                            [],
                            {'type':'Point','coordinates':(1,1)}
                        ),
                       (shapefile.MULTIPOINT, # multipoint
                            [(1,1),(2,1),(2,2)],
                            [],
                            {'type':'MultiPoint','coordinates':[(1,1),(2,1),(2,2)]}
                        ),
                       (shapefile.POLYLINE, # single linestring
                            [(1,1),(2,1)],
                            [0],
                            {'type':'LineString','coordinates':[(1,1),(2,1)]}
                        ),
                       (shapefile.POLYLINE, # multi linestring
                            [(1,1),(2,1), # line 1
                             (10,10),(20,10)], # line 2
                            [0,2],
                            {'type':'MultiLineString','coordinates':[
                                [(1,1),(2,1)], # line 1
                                [(10,10),(20,10)] # line 2
                                ]}
                        ),
                       (shapefile.POLYGON, # single polygon, no holes
                            [(1,1),(1,9),(9,9),(9,1),(1,1), # exterior
                             ],
                            [0],
                            {'type':'Polygon','coordinates':[
                                [(1,1),(1,9),(9,9),(9,1),(1,1)],
                                ]}
                        ),
                       (shapefile.POLYGON, # single polygon, holes (ordered)
                            [(1,1),(1,9),(9,9),(9,1),(1,1), # exterior
                             (2,2),(4,2),(4,4),(2,4),(2,2), # hole 1
                             (5,5),(7,5),(7,7),(5,7),(5,5), # hole 2
                             ],
                            [0,5,5+5],
                            {'type':'Polygon','coordinates':[
                                [(1,1),(1,9),(9,9),(9,1),(1,1)], # exterior
                                [(2,2),(4,2),(4,4),(2,4),(2,2)], # hole 1
                                [(5,5),(7,5),(7,7),(5,7),(5,5)], # hole 2
                                ]}
                        ),
                       (shapefile.POLYGON, # single polygon, holes (unordered)
                            [
                             (2,2),(4,2),(4,4),(2,4),(2,2), # hole 1
                             (1,1),(1,9),(9,9),(9,1),(1,1), # exterior
                             (5,5),(7,5),(7,7),(5,7),(5,5), # hole 2
                             ],
                            [0,5,5+5],
                            {'type':'Polygon','coordinates':[
                                [(1,1),(1,9),(9,9),(9,1),(1,1)], # exterior
                                [(2,2),(4,2),(4,4),(2,4),(2,2)], # hole 1
                                [(5,5),(7,5),(7,7),(5,7),(5,5)], # hole 2
                                ]}
                        ),
                       (shapefile.POLYGON, # multi polygon, no holes
                            [(1,1),(1,9),(9,9),(9,1),(1,1), # exterior
                             (11,11),(11,19),(19,19),(19,11),(11,11), # exterior
                             ],
                            [0,5],
                            {'type':'MultiPolygon','coordinates':[
                                [ # poly 1
                                    [(1,1),(1,9),(9,9),(9,1),(1,1)],
                                ],
                                [ # poly 2
                                    [(11,11),(11,19),(19,19),(19,11),(11,11)],
                                ],
                                ]}
                        ),
                       (shapefile.POLYGON, # multi polygon, holes (unordered)
                            [(1,1),(1,9),(9,9),(9,1),(1,1), # exterior 1
                             (11,11),(11,19),(19,19),(19,11),(11,11), # exterior 2
                             (12,12),(14,12),(14,14),(12,14),(12,12), # hole 2.1
                             (15,15),(17,15),(17,17),(15,17),(15,15), # hole 2.2
                             (2,2),(4,2),(4,4),(2,4),(2,2), # hole 1.1
                             (5,5),(7,5),(7,7),(5,7),(5,5), # hole 1.2
                             ],
                            [0,5,10,15,20,25],
                            {'type':'MultiPolygon','coordinates':[
                                [ # poly 1
                                    [(1,1),(1,9),(9,9),(9,1),(1,1)], # exterior
                                    [(2,2),(4,2),(4,4),(2,4),(2,2)], # hole 1
                                    [(5,5),(7,5),(7,7),(5,7),(5,5)], # hole 2
                                ],
                                [ # poly 2
                                    [(11,11),(11,19),(19,19),(19,11),(11,11)], # exterior
                                    [(12,12),(14,12),(14,14),(12,14),(12,12)], # hole 1
                                    [(15,15),(17,15),(17,17),(15,17),(15,15)], # hole 2
                                ],
                                ]}
                        ),
                       (shapefile.POLYGON, # multi polygon, nested exteriors with holes (unordered)
                            [(1,1),(1,9),(9,9),(9,1),(1,1), # exterior 1
                             (3,3),(3,7),(7,7),(7,3),(3,3), # exterior 2
                             (4.5,4.5),(4.5,5.5),(5.5,5.5),(5.5,4.5),(4.5,4.5), # exterior 3
                             (4,4),(6,4),(6,6),(4,6),(4,4), # hole 2.1
                             (2,2),(8,2),(8,8),(2,8),(2,2), # hole 1.1
                             ],
                            [0,5,10,15,20],
                            {'type':'MultiPolygon','coordinates':[
                                [ # poly 1
                                    [(1,1),(1,9),(9,9),(9,1),(1,1)], # exterior 1
                                    [(2,2),(8,2),(8,8),(2,8),(2,2)], # hole 1.1
                                ],
                                [ # poly 2
                                    [(3,3),(3,7),(7,7),(7,3),(3,3)], # exterior 2
                                    [(4,4),(6,4),(6,6),(4,6),(4,4)], # hole 2.1
                                ],
                                [ # poly 3
                                    [(4.5,4.5),(4.5,5.5),(5.5,5.5),(5.5,4.5),(4.5,4.5)], # exterior 3
                                ],
                                ]}
                        ),
                       (shapefile.POLYGON, # multi polygon, nested exteriors with holes (unordered and tricky holes designed to throw off ring_sample() test)
                            [(1,1),(1,9),(9,9),(9,1),(1,1), # exterior 1
                             (3,3),(3,7),(7,7),(7,3),(3,3), # exterior 2
                             (4.5,4.5),(4.5,5.5),(5.5,5.5),(5.5,4.5),(4.5,4.5), # exterior 3
                             (4,4),(4,4),(6,4),(6,4),(6,4),(6,6),(4,6),(4,4), # hole 2.1 (hole has duplicate coords)
                             (2,2),(3,3),(4,2),(8,2),(8,8),(4,8),(2,8),(2,4),(2,2), # hole 1.1 (hole coords form straight line and starts in concave orientation)
                             ],
                            [0,5,10,15,20+3],
                            {'type':'MultiPolygon','coordinates':[
                                [ # poly 1
                                    [(1,1),(1,9),(9,9),(9,1),(1,1)], # exterior 1
                                    [(2,2),(3,3),(4,2),(8,2),(8,8),(4,8),(2,8),(2,4),(2,2)], # hole 1.1
                                ],
                                [ # poly 2
                                    [(3,3),(3,7),(7,7),(7,3),(3,3)], # exterior 2
                                    [(4,4),(4,4),(6,4),(6,4),(6,4),(6,6),(4,6),(4,4)], # hole 2.1
                                ],
                                [ # poly 3
                                    [(4.5,4.5),(4.5,5.5),(5.5,5.5),(5.5,4.5),(4.5,4.5)], # exterior 3
                                ],
                                ]}
                        ),
                       (shapefile.POLYGON, # multi polygon, holes incl orphaned holes (unordered), should raise warning
                            [(1,1),(1,9),(9,9),(9,1),(1,1), # exterior 1
                             (11,11),(11,19),(19,19),(19,11),(11,11), # exterior 2
                             (12,12),(14,12),(14,14),(12,14),(12,12), # hole 2.1
                             (15,15),(17,15),(17,17),(15,17),(15,15), # hole 2.2
                             (95,95),(97,95),(97,97),(95,97),(95,95), # hole x.1 (orphaned hole, should be interpreted as exterior)
                             (2,2),(4,2),(4,4),(2,4),(2,2), # hole 1.1
                             (5,5),(7,5),(7,7),(5,7),(5,5), # hole 1.2
                             ],
                            [0,5,10,15,20,25,30],
                            {'type':'MultiPolygon','coordinates':[
                                [ # poly 1
                                    [(1,1),(1,9),(9,9),(9,1),(1,1)], # exterior
                                    [(2,2),(4,2),(4,4),(2,4),(2,2)], # hole 1
                                    [(5,5),(7,5),(7,7),(5,7),(5,5)], # hole 2
                                ],
                                [ # poly 2
                                    [(11,11),(11,19),(19,19),(19,11),(11,11)], # exterior
                                    [(12,12),(14,12),(14,14),(12,14),(12,12)], # hole 1
                                    [(15,15),(17,15),(17,17),(15,17),(15,15)], # hole 2
                                ],
                                [ # poly 3 (orphaned hole)
                                    [(95,95),(97,95),(97,97),(95,97),(95,95)], # exterior
                                ],
                                ]}
                        ),
                       (shapefile.POLYGON, # multi polygon, exteriors with wrong orientation (be nice and interpret as such), should raise warning
                            [(1,1),(9,1),(9,9),(1,9),(1,1), # exterior with hole-orientation
                             (11,11),(19,11),(19,19),(11,19),(11,11), # exterior with hole-orientation
                             ],
                            [0,5],
                            {'type':'MultiPolygon','coordinates':[
                                [ # poly 1
                                    [(1,1),(9,1),(9,9),(1,9),(1,1)],
                                ],
                                [ # poly 2
                                    [(11,11),(19,11),(19,19),(11,19),(11,11)],
                                ],
                                ]}
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
        shape.__geo_interface__

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
        assert geoj['type'] == 'FeatureCollection'
        assert 'bbox' in geoj
        assert json.dumps(geoj)


def test_shapes_geo_interface():
    with shapefile.Reader("shapefiles/blockgroups") as r:
        geoj = r.shapes().__geo_interface__
        assert geoj['type'] == 'GeometryCollection'
        assert json.dumps(geoj)


def test_shaperecords_geo_interface():
    with shapefile.Reader("shapefiles/blockgroups") as r:
        geoj = r.shapeRecords().__geo_interface__
        assert geoj['type'] == 'FeatureCollection'
        assert json.dumps(geoj)


def test_shaperecord_geo_interface():
    with shapefile.Reader("shapefiles/blockgroups") as r:
        for shaperec in r:
            assert json.dumps(shaperec.__geo_interface__)


def test_reader_context_manager():
    """
    Assert that the Reader context manager
    closes the shp, shx, and dbf files
    on exit.
    """
    # note uses an actual shapefile from
    # the projects "shapefiles" directory
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        pass

    assert sf.shp.closed is True
    assert sf.dbf.closed is True
    assert sf.shx.closed is True


def test_reader_close():
    """
    Assert that manually callcin Reader.close()
    closes the shp, shx, and dbf files
    on exit.
    """
    # note uses an actual shapefile from
    # the projects "shapefiles" directory
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        pass

    assert sf.shp.closed is True
    assert sf.dbf.closed is True
    assert sf.shx.closed is True


def test_reader_shapefile_type():
    """
    Assert that the type of the shapefile
    is returned correctly.
    """
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        assert sf.shapeType is 5   # 5 means Polygon
        assert sf.shapeType is shapefile.POLYGON
        assert sf.shapeTypeName is "POLYGON"


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
        assert shape.shapeType is 5 # Polygon
        assert shape.shapeType is shapefile.POLYGON
        assert sf.shapeTypeName is "POLYGON"


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
        assert isinstance(field[0], str)    # field name
        assert field[1] in ["C", "N", "F", "L", "D", "M"]   # field type
        assert isinstance(field[2], int)    # field length
        assert isinstance(field[3], int)    # decimal length


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


def test_reader_filelike_dbf_only():
    """
    Assert that specifying just the
    dbf argument to the shapefile reader
    reads just the dbf file.
    """
    with shapefile.Reader(dbf=open("shapefiles/blockgroups.dbf", "rb")) as sf:
        assert len(sf) == 663
        record = sf.record(3)
        assert record[1:3] == ['060750601001', 4715]


def test_reader_filelike_shp_shx_only():
    """
    Assert that specifying just the
    shp and shx argument to the shapefile reader
    reads just the shp and shx file.
    """
    with shapefile.Reader(shp=open("shapefiles/blockgroups.shp", "rb"), shx=open("shapefiles/blockgroups.shx", "rb")) as sf:
        assert len(sf) == 663
        shape = sf.shape(3)
        assert len(shape.points) is 173


def test_reader_filelike_shx_optional():
    """
    Assert that specifying just the
    shp argument to the shapefile reader
    reads just the shp file (shx optional).
    """
    with shapefile.Reader(shp=open("shapefiles/blockgroups.shp", "rb")) as sf:
        assert len(sf) == 663
        shape = sf.shape(3)
        assert len(shape.points) is 173


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


def test_record_attributes():
    """
    Assert that record values can be accessed as
    attributes and dictionary items.
    """
    # note
    # second element in fields matches first element
    # in record because records dont have DeletionFlag
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        field_name = sf.fields[1][0]
        record = sf.record(0)
        assert record[0] == record[field_name] == getattr(record, field_name)


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

        for i,record in enumerate(sf.records()):
            assert record.oid == i

        for i,record in enumerate(sf.iterRecords()):
            assert record.oid == i

        for i,shaperec in enumerate(sf.iterShapeRecords()):
            assert shaperec.record.oid == i


def test_shape_oid():
    """
    Assert that the shape's oid attribute returns
    its index in the shapefile.
    """
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        for i in range(len(sf)):
            shape = sf.shape(i)
            assert shape.oid == i

        for i,shape in enumerate(sf.shapes()):
            assert shape.oid == i

        for i,shape in enumerate(sf.iterShapes()):
            assert shape.oid == i

        for i,shaperec in enumerate(sf.iterShapeRecords()):
            assert shaperec.shape.oid == i


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
        assert len(point) is 2


def test_shaperecord_record():
    """
    Assert that a ShapeRecord object has a record
    attribute that contains record data.
    """
    with shapefile.Reader("shapefiles/blockgroups") as sf:
        shaperec = sf.shapeRecord(3)
        record = shaperec.record

        assert record[1:3] == ['060750601001', 4715]


def test_write_field_name_limit(tmpdir):
    """
    Abc...
    """
    filename = tmpdir.join("test.shp").strpath
    with shapefile.Writer(filename) as writer:
        writer.field('a'*5, 'C') # many under length limit
        writer.field('a'*9, 'C') # 1 under length limit
        writer.field('a'*10, 'C') # at length limit
        writer.field('a'*11, 'C') # 1 over length limit
        writer.field('a'*20, 'C') # many over limit

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
    filename = tmpdir.join("test.shp").strpath
    with shapefile.Writer(shp=filename) as writer:
        pass

    # assert test.shp exists
    assert os.path.exists(filename)

    # assert test.shx does not exist
    assert not os.path.exists(tmpdir.join("test.shx").strpath)

    # assert test.dbf does not exist
    assert not os.path.exists(tmpdir.join("test.dbf").strpath)


def test_write_shx_only(tmpdir):
    """
    Assert that specifying just the
    shx argument to the shapefile writer
    creates just a shx file.
    """
    filename = tmpdir.join("test.shx").strpath
    with shapefile.Writer(shx=filename) as writer:
        pass

    # assert test.shx exists
    assert os.path.exists(filename)

    # assert test.shp does not exist
    assert not os.path.exists(tmpdir.join("test.shp").strpath)

    # assert test.dbf does not exist
    assert not os.path.exists(tmpdir.join("test.dbf").strpath)


def test_write_dbf_only(tmpdir):
    """
    Assert that specifying just the
    dbf argument to the shapefile writer
    creates just a dbf file.
    """
    filename = tmpdir.join("test.dbf").strpath
    with shapefile.Writer(dbf=filename) as writer:
        writer.field('field1', 'C') # required to create a valid dbf file

    # assert test.dbf exists
    assert os.path.exists(filename)

    # assert test.shp does not exist
    assert not os.path.exists(tmpdir.join("test.shp").strpath)

    # assert test.shx does not exist
    assert not os.path.exists(tmpdir.join("test.shx").strpath)


def test_write_default_shp_shx_dbf(tmpdir):
    """
    Assert that creating the shapefile writer without
    specifying the shp, shx, or dbf arguments
    creates a set of shp, shx, and dbf files.
    """
    filename = tmpdir.join("test").strpath
    with shapefile.Writer(filename) as writer:
        writer.field('field1', 'C') # required to create a valid dbf file

    # assert shp, shx, dbf files exist
    assert os.path.exists(filename + ".shp")
    assert os.path.exists(filename + ".shx")
    assert os.path.exists(filename + ".dbf")


def test_write_shapefile_extension_ignored(tmpdir):
    """
    Assert that the filename's extension is
    ignored when creating a shapefile.
    """
    base = "test"
    ext = ".abc"
    filename = tmpdir.join(base + ext).strpath
    with shapefile.Writer(filename) as writer:
        writer.field('field1', 'C') # required to create a valid dbf file

    # assert shp, shx, dbf files exist
    basepath = tmpdir.join(base).strpath
    assert os.path.exists(basepath + ".shp")
    assert os.path.exists(basepath + ".shx")
    assert os.path.exists(basepath + ".dbf")

    # assert test.abc does not exist
    assert not os.path.exists(basepath + ext)


def test_write_geojson(tmpdir):
    """
    Assert that the output of geo interface can be written to json.
    """
    filename = tmpdir.join("test").strpath
    with shapefile.Writer(filename) as w:
        w.field('TEXT', 'C')
        w.field('NUMBER', 'N')
        w.field('DATE', 'D')
        w.record('text', 123, datetime.date(1898,1,30))
        w.record('text', 123, [1998,1,30])
        w.record('text', 123, '19980130')
        w.record('text', 123, '-9999999') # faulty date
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

shape_types = [k for k in shapefile.SHAPETYPE_LOOKUP.keys() if k != 31] # exclude multipatch

@pytest.mark.parametrize("shape_type", shape_types)
def test_write_empty_shapefile(tmpdir, shape_type):
    """
    Assert that can write an empty shapefile, for all different shape types. 
    """
    filename = tmpdir.join("test").strpath
    with shapefile.Writer(filename, shapeType=shape_type) as w:
        w.field('field1', 'C') # required to create a valid dbf file

    with shapefile.Reader(filename) as r:
        assert r.shapeType == shape_type
