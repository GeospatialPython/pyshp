from __future__ import annotations

import io

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import (
    builds,
    composite,
    floats,
    integers,
    just,
    lists,
    none,
    one_of,
    tuples,
)

import shapefile as shp

float_nums = floats(allow_nan=False, allow_infinity=False)
xs = float_nums
ys = float_nums
ms = one_of(none(), float_nums)
zs = one_of(just(0.0), float_nums)
PointsLengths = integers(min_value=1, max_value=8000)  # length of points
oid = one_of(none(), integers(min_value=0))
point_2D = builds(shp.Point, x=xs, y=ys, oid=oid)
pointM = builds(
    shp.PointM,
    x=xs,
    y=ys,
    m=ms,
    oid=oid,
)
pointZ = builds(
    shp.PointZ,
    x=xs,
    y=ys,
    z=zs,
    m=ms,
    oid=oid,
)


def coords_2D_list(
    min_size: int = 1,
    max_size: int | None = None,
):
    return lists(
        tuples(xs, ys),
        min_size=min_size,
        max_size=max_size,
    )


@pytest.mark.hypothesis
@given(expected=point_2D, i=integers(min_value=1))
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
@given(expected=pointM, i=integers(min_value=1))
def test_PointM_roundtrips(
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


@pytest.mark.hypothesis
@given(expected=pointZ, i=integers(min_value=1))
def test_PointZ_roundtrips(
    expected: shp.Point,
    i: int,
) -> None:
    stream = io.BytesIO()
    n = shp.PointZ.write_to_byte_stream(b_io=stream, s=expected, i=i)
    assert n == stream.tell()
    stream.seek(0)
    actual = shp.PointZ.from_byte_stream(
        shapeType=shp.POINTZ,
        b_io=stream,
        next_shape_pos=n,
        oid=expected.oid,
        bbox=None,
    )
    assert isinstance(actual, shp.PointM)
    assert actual.points == expected.points
    assert actual.z == expected.z
    assert actual.m == expected.m
    assert actual.oid == expected.oid


multipoint = builds(shp.MultiPoint, points=coords_2D_list())


@pytest.mark.hypothesis
@given(expected=multipoint, i=integers(min_value=1))
def test_MultiPoint_roundtrips(
    expected: shp.MultiPoint,
    i: int,
) -> None:
    stream = io.BytesIO()
    n = shp.MultiPoint.write_to_byte_stream(b_io=stream, s=expected, i=i)
    assert n == stream.tell()
    stream.seek(0)
    actual = shp.MultiPoint.from_byte_stream(
        shapeType=shp.MULTIPOINT,
        b_io=stream,
        next_shape_pos=n,
        oid=expected.oid,
        bbox=None,
    )
    assert isinstance(actual, shp.MultiPoint)
    assert actual.points == expected.points
    assert actual.oid == expected.oid


@composite
def multipointM(draw):
    N = draw(PointsLengths)
    return shp.MultiPointM(
        points=draw(coords_2D_list(min_size=N, max_size=N)),
        m=draw(lists(ms, min_size=N, max_size=N)),
        oid=oid,
    )


@pytest.mark.hypothesis
@settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(expected=multipointM(), i=integers(min_value=1))
def test_MultiPointM_roundtrips(
    expected: shp.MultiPointM,
    i: int,
) -> None:
    stream = io.BytesIO()
    n = shp.MultiPointM.write_to_byte_stream(b_io=stream, s=expected, i=i)
    assert n == stream.tell()
    stream.seek(0)
    actual = shp.MultiPointM.from_byte_stream(
        shapeType=shp.MULTIPOINTM,
        b_io=stream,
        next_shape_pos=n,
        oid=expected.oid,
        bbox=None,
    )
    assert isinstance(actual, shp.MultiPointM)
    assert actual.points == expected.points
    assert actual.m == expected.m
    assert actual.oid == expected.oid


@composite
def multipointZ(draw):
    N = draw(PointsLengths)
    return shp.MultiPointZ(
        points=draw(coords_2D_list(min_size=N, max_size=N)),
        z=draw(lists(zs, min_size=N, max_size=N)),
        m=draw(lists(ms, min_size=N, max_size=N)),
        oid=oid,
    )


@pytest.mark.hypothesis
@settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(expected=multipointZ(), i=integers(min_value=1))
def test_MultiPointZ_roundtrips(
    expected: shp.MultiPointZ,
    i: int,
) -> None:
    stream = io.BytesIO()
    n = shp.MultiPointZ.write_to_byte_stream(b_io=stream, s=expected, i=i)
    assert n == stream.tell()
    stream.seek(0)
    actual = shp.MultiPointZ.from_byte_stream(
        shapeType=shp.MULTIPOINTZ,
        b_io=stream,
        next_shape_pos=n,
        oid=expected.oid,
        bbox=None,
    )
    assert isinstance(actual, shp.MultiPointZ)
    assert actual.points == expected.points
    assert actual.m == expected.m, f"{type(actual.m)=}, {type(expected.m)=}"
    assert actual.z == expected.z,  f"{type(actual.z)=}, {type(expected.z)=}"
    assert actual.oid == expected.oid
