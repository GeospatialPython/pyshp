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
