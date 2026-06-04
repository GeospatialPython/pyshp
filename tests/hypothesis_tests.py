import io

import pytest
from hypothesis import given
from hypothesis.strategies import (
    builds,
    floats,
    integers,
    none,
    one_of,
)

import shapefile as shp

float_nums = floats(allow_nan=False, allow_infinity=False)

points_2D = builds(shp.Point, float_nums, float_nums, one_of(none(), integers()))
pointMs = builds(
    shp.PointM,
    float_nums,
    float_nums,
    one_of(none(), float_nums),
    one_of(none(), integers()),
)


@pytest.mark.hypothesis
@given(expected=points_2D, i=integers(min_value=1))
def test_Point_2D_roundtrips(
    expected: shp.Point,
    i: int,
) -> None:
    stream = io.BytesIO()
    n = shp.Point.write_to_byte_stream(b_io=stream, s=expected, i=i)
    assert n == stream.tell()
    stream.seek(0)
    actual = shp.Point.from_byte_stream(
        shapeType=shp.POINT,
        b_io=stream,
        next_shape_pos=n,
        oid=expected.oid,
        bbox=None,
    )
    assert isinstance(actual, shp.Point)
    assert actual.points == expected.points
    assert actual.oid == expected.oid


@pytest.mark.hypothesis
@given(expected=pointMs, i=integers(min_value=1))
def test_Point_M_roundtrips(
    expected: shp.Point,
    i: int,
) -> None:
    stream = io.BytesIO()
    n = shp.PointM.write_to_byte_stream(b_io=stream, s=expected, i=i)
    assert n == stream.tell()
    stream.seek(0)
    actual = shp.PointM.from_byte_stream(
        shapeType=shp.POINTM,
        b_io=stream,
        next_shape_pos=n,
        oid=expected.oid,
        bbox=None,
    )
    assert isinstance(actual, shp.PointM)
    assert actual.points == expected.points
    assert actual.m == expected.m
    assert actual.oid == expected.oid
