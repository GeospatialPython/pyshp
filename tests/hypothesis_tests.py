from __future__ import annotations

import datetime
import io
import itertools
import string

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import (
    builds,
    composite, # Preferably avoid.  Shrinking composite strategies is slow.
    floats,
    integers,
    just,
    lists,
    none,
    one_of,
    tuples,
    sampled_from,
    text,
    characters,
    dates,
)

import shapefile as shp

float_nums = floats(allow_nan=False, allow_infinity=False)
xs = float_nums
ys = float_nums
ms = one_of(none(), float_nums)
zs = one_of(just(0.0), float_nums)
PointsLengths = integers(min_value=1, max_value=8000)  # length of points
oid = one_of(none(), integers(min_value=0))
null_shapes = builds(shp.NullShape, oid=oid)
point_2D = builds(shp.Point, x=xs, y=ys, oid=oid)
pointm = builds(
    shp.PointM,
    x=xs,
    y=ys,
    m=ms,
    oid=oid,
)
pointz = builds(
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
@given(expected=pointm, i=integers(min_value=1))
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
@given(expected=pointz, i=integers(min_value=1))
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



def multipointM_from_xyms(point_ms: tuple[float, float, float | None], oid_: int) -> shp.MultiPointM:
    x_vals, y_vals, m_vals = zip(*point_ms)
    xy_vals = zip(x_vals, y_vals)
    return shp.MultiPointM(points=list(xy_vals), m=list(m_vals), oid=oid_)

multipointm = builds(multipointM_from_xyms, lists(tuples(xs, ys, ms), min_size=1), oid)

@pytest.mark.hypothesis
@given(expected=multipointm, i=integers(min_value=1))
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


def multipointZ_from_xyzms(pointz_ms: tuple[float, float, float, float | None], oid_: int) -> shp.MultiPointZ:
    x_vals, y_vals, z_vals, m_vals = zip(*pointz_ms)
    xy_vals = zip(x_vals, y_vals)
    return shp.MultiPointZ(points=list(xy_vals), z=list(z_vals), m=list(m_vals), oid=oid_)

multipointz = builds(multipointZ_from_xyzms, lists(tuples(xs, ys, zs, ms), min_size=1), oid)


@pytest.mark.hypothesis
@given(expected=multipointz, i=integers(min_value=1))
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

def multipatch_from_xyzms_and_types(
    xyzms_and_types: list[tuple[list[tuple[float, float, float, float | None]], int]],
    oid: int,
    ) -> shp.MultiPatch:
    xyzm_vals, p_types = zip(*xyzms_and_types)
    return shp.MultiPatch(lines = xyzm_vals, partTypes = p_types, oid=oid)

multipatch = builds(
    multipatch_from_xyzms_and_types,
    lists(tuples(lists(tuples(xs, ys, zs, ms), min_size=1), part_types), min_size=1), oid)


@pytest.mark.hypothesis
@given(expected=multipatch, i=integers(min_value=1))
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

MAX_FILE_SIZE_16bw = (1 << 31) - 1 # This bound comes from encoding the
                                   # actual file size (in 16 bit words)
                                   # as a 4 byte signed integer.
MAX_NUM_SHAPES = (MAX_FILE_SIZE_16bw - 50) // 6 # Minus 100B header, 12 bytes
                                                # per record (the minimum for
                                                # a Null shape).

shape_codes_names_and_strategies = [
(0, "Null Shape", null_shapes),
(1, "Point", point_2D),
(3, "PolyLine", polyline),
(5, "Polygon", polygon),
(8, "MultiPoint", multipoint),
(11, "PointZ", pointz),
(13, "PolyLineZ", polylinez),
(15, "PolygonZ", polygonz),
(18, "MultiPointZ", multipointz),
(21, "PointM", pointm),
(23, "PolyLineM", polylinem),
(25, "PolygonM", polygonm),
(28, "MultiPointM", multipointm),
(31, "MultiPatch", multipatch),
]

def code_and_shape_strat_from_triple(t):
    x, _name, shapes  = t
    return tuples(
        just(x),
        lists(
            one_of(shapes, null_shapes),
            min_size = 0, # Empty shp files are in the ESRI spec.
            max_size=MAX_NUM_SHAPES,
        ),
    )
codes_and_shapes_strats = [
    code_and_shape_strat_from_triple(t)
    for t in shape_codes_names_and_strategies
]

codes_and_shapes = one_of(codes_and_shapes_strats)

@pytest.mark.hypothesis
@given(codes_and_shapes=codes_and_shapes)
def test_shp_reader_writer_roundtrip(codes_and_shapes)-> None:
    code_ex, expected_shapes = codes_and_shapes
    stream = io.BytesIO()
    with shp.ShpWriter(shp=stream, shapeType=code_ex) as w:
        for shape in expected_shapes:
            w.shape(shape)
    stream.seek(0)
    with shp.ShpReader(shp=stream) as r:
        assert r.shapeType == code_ex

        for actual, expected in itertools.zip_longest(r.shapes(), expected_shapes):

            assert isinstance(actual, (shp.SHAPE_CLASS_FROM_SHAPETYPE[code_ex], shp.NullShape))
            assert actual.points_3D == expected.points_3D
            # Don't assert actual.oid == expected.oid it's defined by
            # actual.oid indicates the order actual was written in, expected.oid
            # is not currently encoded (as we'd have to resort the entire Shapefile after each shape)
            assert actual.parts == expected.parts, f"{type(actual.parts)=}, {type(expected.parts)=}"

            if (m := getattr(actual, "m", None)):
                assert m == expected.m, f"{type(m)=}, {type(expected.m)=}"
            else:
                assert not hasattr(expected, "m")

            if (z := getattr(actual, "z", None)):
                assert z == expected.z, f"{type(z)=}, {type(expected.z)=}"
            else:
                assert not hasattr(expected, "z")

            if (partTypes := getattr(actual, "partTypes", None)):
                assert actual.partTypes == expected.partTypes, f"{type(actual.partTypes)=}, {type(expected.partTypes)=}"
            else:
                assert not hasattr(expected, "partTypes")




@pytest.mark.hypothesis
@given(codes_and_shapes=codes_and_shapes)
def test_shx_reader_writer_roundtrip(codes_and_shapes)-> None:
    code_ex, expected_shapes = codes_and_shapes

    sizes_B = []
    offsets_B = []
    offset_B = 100 # "Thus, the offset for the first record in the
                   #  main file is 50 (16bw), given the 100-byte header. "
    shp_stream = io.BytesIO()
    shx_stream = io.BytesIO()
    with shp.ShpWriter(shp=shp_stream, shapeType=code_ex) as shp_w:
        with shp.ShxWriter(shx=shx_stream, shp_writer = shp_w) as shx_w:
            for shape in expected_shapes:
                offset_B, size_B = shp_w.shape(shape)
                sizes_B.append(size_B)
                offsets_B.append(offset_B)
                shx_w._shx_record(offset_B, size_B)

    shx_stream.seek(0)

    with shp.ShxReader(shx=shx_stream) as r:
        assert r.numShapes == len(expected_shapes)
        assert r.offsets == offsets_B
        assert r.shape_lengths_B == sizes_B



DBF_FIELD_TYPES = {
    "C": {},
    "N": {"max_decimal" : 20, "max_length": 22},  # max length=23 to avoid error due to precision limit, e.g.:
    "F": {"max_decimal" : 20, "max_length": 22},  # hypothesis.errors.InvalidArgument: max_value=100000000000000000000000
                                                   # cannot be exactly represented as a float of
                                                   # width 64 - use max_value=1e+23 instead.
    "L": {"max_length": 1},
    "D": {"min_length": 8, "max_length": 8},
}

@composite
def dbf_field(draw):
    field_type, bounds_dict = draw(sampled_from(list(DBF_FIELD_TYPES.items())))

    name = draw(
        text(
            alphabet=characters(codec="ascii"),
            min_size=1,
            max_size=10,
        )
    )

    max_length = bounds_dict.get("max_length", 254)
    min_length = bounds_dict.get("min_length", 1)
    max_decimal = bounds_dict.get("max_decimal", 0)
    size = draw(integers(min_value=min_length, max_value=max_length))
    decimal = draw(integers(min_value=0, max_value=max(0,min(size - 3, max_decimal))))


    return {"name": name, "field_type": field_type, "size": size, "decimal": decimal}

ascii_printable = string.ascii_letters + string.digits + string.punctuation #+ " "

def record_value_for_field(name: str, field_type: str, size: int, decimal: int = 0):

    if field_type == "C":
        return text(
            alphabet=ascii_printable,
            min_size=0,
            max_size=size,
        )
    if field_type in {"N", "F"}:

        int_digits = size if decimal == 0 else size - decimal - 1
        min_int = -(10 ** (int_digits - 1) - 1)
        max_int = 10 ** int_digits - 1

        if decimal == 0:
            return integers(min_value=min_int, max_value=max_int)

        # Max finite float: 2**1023 * (2 - 2**(-52))
        return floats(
            min_value=min_int - 1,
            max_value=max_int + 1,
            exclude_min=True,
            exclude_max=True,
        )
    if field_type == "L":
        return sampled_from([True, False, None])
    if field_type == "D":
        return one_of(dates(), dates().map(lambda d: d.strftime("%Y%m%d")))

    raise ValueError(f"Unsupported: {field_type=}")


@composite
def dbf_fields_and_records(
    draw,
    max_fields=10, # In DbfWriter.__init__, max_num_fields: int = 2046,
    max_records=20,
    ):

    fields = draw(lists(dbf_field(), min_size=1, max_size=max_fields))

    record_strategy = tuples(*(record_value_for_field(**field) for field in fields))

    records = draw(lists(record_strategy, min_size=0, max_size=max_records))

    return fields, records



@pytest.mark.hypothesis
@given(fields_and_records=dbf_fields_and_records())
def test_dbf_reader_writer_roundtrip(fields_and_records)-> None:
    fields, records = fields_and_records
    stream = io.BytesIO()
    with shp.DbfWriter(dbf=stream) as dbf_w:
        for field in fields:
            dbf_w.field(**field)
        for record in records:
            dbf_w.record(*record)
    stream.seek(0)
    with shp.DbfReader(dbf=stream) as r:
        actual_fields = iter(r.fields)
        next(actual_fields) # skip deletion flag
        for f_r, f_w in itertools.zip_longest(actual_fields, fields):
            actual_field_dict = f_r._asdict()
            for k in ("field_type", "size", "decimal"):
                assert actual_field_dict[k] == f_w[k], f"{k=}, {actual_field_dict[k]=}, {f_w[k]=}"
        for exp_rec, actual_rec in itertools.zip_longest(records, r.records()):
            for expected, actual, field in itertools.zip_longest(exp_rec, actual_rec, fields):
                field_type = field["field_type"]
                decimal = field["decimal"]
                if field_type == "D":
                    if isinstance(expected, datetime.date):
                        expected = expected.strftime("%Y%m%d")
                    if isinstance(actual, datetime.date):
                        actual = actual.strftime("%Y%m%d")
                elif field_type in ("N", "F"):
                    expected = float(format(expected, f".{decimal}f"))
                # elif field_type == "C":
                #     expected = expected.strip()
                assert actual == expected, f"{actual=}, {expected=}, {field_type=}, {type(actual)=}, {type(expected)=}"
