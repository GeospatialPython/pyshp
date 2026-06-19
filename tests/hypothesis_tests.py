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
    sampled_from,
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
    assert actual.points_2D == expected.points_2D

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
    assert actual.points_2D == expected.points_2D

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
    assert actual.points_3D == expected.points_3D

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
    assert actual.points_2D == expected.points_2D

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
    assert actual.points_2D == expected.points_2D

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
    assert actual.points_3D == expected.points_3D

    assert actual.m == expected.m, f"{type(actual.m)=}, {type(expected.m)=}"
    assert actual.z == expected.z,  f"{type(actual.z)=}, {type(expected.z)=}"
    assert actual.oid == expected.oid

polyline = builds(shp.Polyline, lines=lists(lists(tuples(xs, ys), min_size=1), min_size=1), oid=oid)
polylinem = builds(shp.PolylineM, lines=lists(lists(tuples(xs, ys, ms), min_size=1), min_size=1), oid=oid)
polylinez = builds(shp.PolylineZ, lines=lists(lists(tuples(xs, ys, zs, ms), min_size=1), min_size=1), oid=oid)

@pytest.mark.hypothesis
@given(expected=polyline, i=integers(min_value=1))
def test_Polyline_roundtrips(
    expected: shp.Polyline,
    i: int,
) -> None:
    stream = io.BytesIO()
    n = shp.Polyline.write_to_byte_stream(b_io=stream, s=expected, i=i)
    assert n == stream.tell()
    stream.seek(0)
    actual = shp.Polyline.from_byte_stream(
        shapeType=shp.POLYLINE,
        b_io=stream,
        next_shape_pos=n,
        oid=expected.oid,
        bbox=None,
    )
    assert isinstance(actual, shp.Polyline)
    assert actual.points_2D == expected.points_2D

    assert actual.parts == expected.parts, f"{type(actual.parts)=}, {type(expected.parts)=}"
    assert actual.oid == expected.oid

@pytest.mark.hypothesis
@settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(expected=polylinem, i=integers(min_value=1))
def test_PolylineM_roundtrips(
    expected: shp.PolylineM,
    i: int,
) -> None:
    stream = io.BytesIO()
    n = shp.PolylineM.write_to_byte_stream(b_io=stream, s=expected, i=i)
    assert n == stream.tell()
    stream.seek(0)
    actual = shp.PolylineM.from_byte_stream(
        shapeType=shp.POLYLINEM,
        b_io=stream,
        next_shape_pos=n,
        oid=expected.oid,
        bbox=None,
    )
    assert isinstance(actual, shp.PolylineM)
    assert actual.points_2D == expected.points_2D

    assert actual.parts == expected.parts, f"{type(actual.parts)=}, {type(expected.parts)=}"
    assert actual.m == expected.m, f"{type(actual.m)=}, {type(expected.m)=}"
    assert actual.oid == expected.oid

@pytest.mark.hypothesis
@settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(expected=polylinez, i=integers(min_value=1))
def test_PolylineZ_roundtrips(
    expected: shp.PolylineZ,
    i: int,
) -> None:
    stream = io.BytesIO()
    n = shp.PolylineZ.write_to_byte_stream(b_io=stream, s=expected, i=i)
    assert n == stream.tell()
    stream.seek(0)
    actual = shp.PolylineZ.from_byte_stream(
        shapeType=shp.POLYLINEZ,
        b_io=stream,
        next_shape_pos=n,
        oid=expected.oid,
        bbox=None,
    )
    assert isinstance(actual, shp.PolylineZ)
    assert actual.points_3D == expected.points_3D

    assert actual.parts == expected.parts, f"{type(actual.parts)=}, {type(expected.parts)=}"
    assert actual.m == expected.m, f"{type(actual.m)=}, {type(expected.m)=}"
    assert actual.z == expected.z,  f"{type(actual.z)=}, {type(expected.z)=}"
    assert actual.oid == expected.oid

# Relies on Shape._ensure_polygon_rings_closed to close the Polygons
polygon = builds(shp.Polygon, lines=lists(lists(tuples(xs, ys), min_size=1), min_size=1), oid=oid)
polygonm = builds(shp.PolygonM, lines=lists(lists(tuples(xs, ys, ms), min_size=1), min_size=1), oid=oid)
polygonz = builds(shp.PolygonZ, lines=lists(lists(tuples(xs, ys, zs, ms), min_size=1), min_size=1), oid=oid)

@pytest.mark.hypothesis
@given(expected=polygon, i=integers(min_value=1))
def test_Polygon_roundtrips(
    expected: shp.Polygon,
    i: int,
) -> None:
    stream = io.BytesIO()
    n = shp.Polygon.write_to_byte_stream(b_io=stream, s=expected, i=i)
    assert n == stream.tell()
    stream.seek(0)
    actual = shp.Polygon.from_byte_stream(
        shapeType=shp.POLYGON,
        b_io=stream,
        next_shape_pos=n,
        oid=expected.oid,
        bbox=None,
    )
    assert isinstance(actual, shp.Polygon)
    assert actual.points_2D == expected.points_2D

    assert actual.parts == expected.parts, f"{type(actual.parts)=}, {type(expected.parts)=}"
    assert actual.oid == expected.oid

@pytest.mark.hypothesis
@settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(expected=polygonm, i=integers(min_value=1))
def test_PolygonM_roundtrips(
    expected: shp.PolygonM,
    i: int,
) -> None:
    stream = io.BytesIO()
    n = shp.PolygonM.write_to_byte_stream(b_io=stream, s=expected, i=i)
    assert n == stream.tell()
    stream.seek(0)
    actual = shp.PolygonM.from_byte_stream(
        shapeType=shp.POLYGONM,
        b_io=stream,
        next_shape_pos=n,
        oid=expected.oid,
        bbox=None,
    )
    assert isinstance(actual, shp.PolygonM)
    assert actual.points_2D == expected.points_2D

    assert actual.parts == expected.parts, f"{type(actual.parts)=}, {type(expected.parts)=}"
    assert actual.m == expected.m, f"{type(actual.m)=}, {type(expected.m)=}"
    assert actual.oid == expected.oid

@pytest.mark.hypothesis
@settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(expected=polygonz, i=integers(min_value=1))
def test_PolygonZ_roundtrips(
    expected: shp.PolygonZ,
    i: int,
) -> None:
    stream = io.BytesIO()
    n = shp.PolygonZ.write_to_byte_stream(b_io=stream, s=expected, i=i)
    assert n == stream.tell()
    stream.seek(0)
    actual = shp.PolygonZ.from_byte_stream(
        shapeType=shp.POLYGONZ,
        b_io=stream,
        next_shape_pos=n,
        oid=expected.oid,
        bbox=None,
    )
    assert isinstance(actual, shp.PolygonZ)
    assert actual.points_3D == expected.points_3D

    assert actual.parts == expected.parts, f"{type(actual.parts)=}, {type(expected.parts)=}"
    assert actual.m == expected.m, f"{type(actual.m)=}, {type(expected.m)=}"
    assert actual.z == expected.z,  f"{type(actual.z)=}, {type(expected.z)=}"
    assert actual.oid == expected.oid

part_types = sampled_from(range(6)) # 0: Triangle Strip, ..., 5: Ring
@composite
def multipatches(draw):
    N = draw(PointsLengths)
    p_types = draw(lists(part_types, min_size=N, max_size=N))
    patches = draw(lists(lists(tuples(xs, ys, zs, ms), min_size=1), min_size=N, max_size=N))
    return shp.MultiPatch(lines = patches, partTypes = p_types, oid=oid)




@pytest.mark.hypothesis
@settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(expected=multipatches(), i=integers(min_value=1))
def test_MultiPatch_roundtrips(
    expected: shp.MultiPatch,
    i: int,
) -> None:
    stream = io.BytesIO()
    n = shp.MultiPatch.write_to_byte_stream(b_io=stream, s=expected, i=i)
    assert n == stream.tell()
    stream.seek(0)
    actual = shp.MultiPatch.from_byte_stream(
        shapeType=shp.MULTIPATCH,
        b_io=stream,
        next_shape_pos=n,
        oid=expected.oid,
        bbox=None,
    )
    assert isinstance(actual, shp.MultiPatch)
    assert actual.points_3D == expected.points_3D

    assert actual.parts == expected.parts, f"{type(actual.parts)=}, {type(expected.parts)=}"
    assert actual.m == expected.m, f"{type(actual.m)=}, {type(expected.m)=}"
    assert actual.z == expected.z,  f"{type(actual.z)=}, {type(expected.z)=}"
    assert actual.oid == expected.oid
    assert actual.partTypes == expected.partTypes, f"{type(actual.partTypes)=}, {type(expected.partTypes)=}"