"""
This module tests the functionality of shapefile.py.
"""
# std lib imports

# third party imports
import pytest

# our imports
import shapefile


def test_empty_shape_geo_interface():
    """
    Assert that calling __geo_interface__
    on a Shape with no points or parts
    raises an Exception.
    """
    shape = shapefile.Shape()
    with pytest.raises(Exception):
        shape.__geo_interface__


def test_reader_context_manager():
    """
    Assert that the Reader context manager
    closes the shp, shx, and dbf files
    on exit.
    """
    # note uses an actual shapefile from
    # the projects "shapefiles" directory
    with shapefile.Reader("shapefiles/blockgroups") as shp:
        pass

    assert shp.shp.closed is True
    assert shp.dbf.closed is True
    assert shp.shx.closed is True


def test_reader_shapefile_type():
    """
    Assert that the type of the shapefile
    is returned correctly.
    """
    with shapefile.Reader("shapefiles/blockgroups") as shp:
        assert shp.shapeType is 5   # 5 means Polygon
        assert shp.shapeType is shapefile.POLYGON
        assert shp.shapeTypeName is "POLYGON"


def test_reader_shapefile_length():
    """
    Assert that the length the reader gives us
    matches up with the number of records
    in the file.
    """
    with shapefile.Reader("shapefiles/blockgroups") as shp:
        assert len(shp) == len(shp.shapes())
