from __future__ import annotations

import contextlib
import datetime
import io
import itertools
import string

import pytest
from hypothesis import HealthCheck, given, settings, reproduce_failure
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

def code_and_shape_strategy_from_triple(t):
    x, _name, shapes  = t
    return tuples(
        just(x),
        lists(
            one_of(shapes, null_shapes),
            min_size = 0, # Empty shp files are in the ESRI spec.
            max_size=MAX_NUM_SHAPES,
        ),
    )
codes_and_shapes_strategies = [
    code_and_shape_strategy_from_triple(t)
    for t in shape_codes_names_and_strategies
]

codes_and_shapes = one_of(codes_and_shapes_strategies)


def _assert_reader_matches_expected_shapes(r, code_ex, expected_shapes):
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
def test_shp_reader_writer_roundtrip(codes_and_shapes)-> None:

    code_ex, expected_shapes = codes_and_shapes
    stream = io.BytesIO()

    with shp.ShpWriter(shp=stream, shapeType=code_ex) as w:
        for shape in expected_shapes:
            w.shape(shape)

    with shp.ShpReader(shp=stream) as r:
        _assert_reader_matches_expected_shapes(r, code_ex, expected_shapes)



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


ENCODINGS = [
    "ascii",
    "utf-8",
]

encodings = sampled_from(ENCODINGS)


@composite
def _dbf_fields_strategy(draw, encoding: str) -> dict[str, str | int]:
    field_type, bounds_dict = draw(sampled_from(list(DBF_FIELD_TYPES.items())))

    name = draw(
        text(
            alphabet=characters(
                codec=encoding,
                # https://en.wikipedia.org/wiki/Unicode_character_property#General_Category
                exclude_categories=["Cs", "Co", "Cn"], # Cs - surrogates
                # exclude_characters=[" "],
            ),
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


@composite
def encodings_and_dbf_fields(draw):
    encoding = draw(encodings)
    fields_strategy = _dbf_fields_strategy(encoding)
    field = draw(fields_strategy)
    return encoding, field

def _get_fields_context(fields, codec, strict=False):
    for field in fields:
        if (len(field["name"].encode(codec)) > 10 or
            "\x00" in field["name"] or
            (" " in field["name"] and not strict)
            ):
            if strict:
                return pytest.raises(shp.DbfStringDataLoss), True
            return pytest.warns(shp.PossibleDataLoss), False
    return contextlib.nullcontext(), False

@pytest.mark.hypothesis
@settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(encoding_and_dbf_field=encodings_and_dbf_fields())
def test_dbf_Field_roundtrips(encoding_and_dbf_field: dict) -> None:

    encoding, field_kwargs = encoding_and_dbf_field

    w_context, error_expected = _get_fields_context([field_kwargs], encoding, strict=True)

    with w_context:
        expected = shp.Field.from_unchecked(
            encoding=encoding,
            strict=True,
            **field_kwargs,
        )
        encoded = expected.encode_field_descriptor(strict=True)
    if error_expected:
        return
    stream = io.BytesIO()
    stream.write(encoded)
    stream.seek(0)

    actual = shp.Field.from_byte_stream(
        stream,
        encoding=encoding,
    )

    assert isinstance(actual, shp.Field)
    assert actual.name == expected.name
    assert actual[1:] == expected[1:]


ascii_printable = string.ascii_letters + string.digits + string.punctuation + " "

def record_value_for_field(name: str, field_type: str, size: int, decimal: int, encoding: str):

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


def _dbf_encoding_fields_and_record_strategy(
    draw,
    max_fields: int=10, # In DbfWriter.__init__, max_num_fields: int = 2046,
    ):

    encoding = draw(encodings)

    fields = draw(lists(_dbf_fields_strategy(encoding), min_size=1, max_size=max_fields))

    record_strategy = tuples(*(record_value_for_field(encoding=encoding, **field) for field in fields))

    return encoding, fields, record_strategy


@composite
def dbf_encoding_fields_and_records(
    draw,
    max_fields=10, # In DbfWriter.__init__, max_num_fields: int = 2046,
    max_records=20,
    ):

    encoding, fields, record_strategy = _dbf_encoding_fields_and_record_strategy(draw, max_fields)

    records = draw(lists(record_strategy, min_size=0, max_size=max_records))

    return encoding, fields, records


def _assert_reader_matches_expected_fields(r, expected_fields, writer_strict):
    assert len(expected_fields) == len(r.data_fields), f"{expected_fields=}, {r.data_fields=}"

    for f_r, f_w in zip(r.data_fields, expected_fields):
        expected_name = f_w["name"]
        if not writer_strict:
            expected_name = expected_name.replace(" ", "_")
        expected_name = expected_name.rstrip("\x00")
        assert expected_name.startswith(f_r.name), f"{expected_name=}, {f_r.name=}"
        actual_field_dict = f_r._asdict()
        for k in ("field_type", "size", "decimal"):
            assert actual_field_dict[k] == f_w[k], f"{k=}, {actual_field_dict[k]=}, {f_w[k]=}"

def _assert_reader_matches_expected_records(r, fields, written_records):
    actual_records = r.records()
    expected_records = [rec for rec in written_records if rec is not None]
    assert len(expected_records) == len(actual_records), f"{expected_records=}, {actual_records=}"
    for exp_rec, actual_rec in zip(expected_records, actual_records):
        for expected, actual, field in itertools.zip_longest(exp_rec, actual_rec, fields):
            field_type = field["field_type"]
            decimal = field["decimal"]
            if field_type == "D":
                if isinstance(expected, datetime.date):
                    expected = expected.strftime("%Y%m%d")
                if isinstance(actual, datetime.date):
                    actual = actual.strftime("%Y%m%d")
            elif field_type in ("N", "F") and decimal >= 1:
                expected = float(format(expected, f".{decimal}f"))
            assert actual == expected, f"{actual=}, {expected=}, {field_type=}, {type(actual)=}, {type(expected)=}"


def _write_fields_and_records_to_strict(w, fields, records):

    field_indices, written_records = set(), []


    for i, field in enumerate(fields):
        try:
            w.field(**field)
        except shp.DbfStringDataLoss:
            pass
        else:
            field_indices.add(i)

    if not field_indices:
        return None, None


    for record in records:
        rec_list = [
            val
            for i, val in enumerate(record)
            if i in field_indices
        ]
        try:
            w.record(*rec_list)
        except shp.DbfStringDataLoss:
            written_records.append(None)
        else:
            written_records.append(rec_list)


    written_fields = [field for i, field in enumerate(fields) if i in field_indices]

    return written_fields, written_records

@pytest.mark.hypothesis
@given(codec_fields_and_records=dbf_encoding_fields_and_records())
def test_dbf_reader_writer_roundtrip(codec_fields_and_records)-> None:
    codec, fields, records = codec_fields_and_records
    stream = io.BytesIO()

    # pytest.raises and pytest.warns can obscure other
    # exceptions inside them
    w = shp.DbfWriter(dbf=stream, encoding=codec, strict=True)

    written_fields, written_records = _write_fields_and_records_to_strict(w, fields, records)

    if not written_fields or written_records is None:
        return

    w.close()


    with shp.DbfReader(dbf=stream, encoding=codec) as r:
        _assert_reader_matches_expected_fields(r, written_fields, True)
        _assert_reader_matches_expected_records(r, written_fields, written_records)


@composite
def codes_codecs_fields_shapes_and_records(draw):
    code, shapes = draw(codes_and_shapes)
    encoding, fields, records_strategy = _dbf_encoding_fields_and_record_strategy(draw, max_fields=10)
    N = len(shapes)
    records = [draw(records_strategy) for _ in range(N)]

    return code, encoding, fields, shapes, records


@pytest.mark.hypothesis
@settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(codes_codecs_fields_shapes_and_records=codes_codecs_fields_shapes_and_records())
def test_shapefile_reader_writer_roundtrip(codes_codecs_fields_shapes_and_records)-> None:

    code_ex, encoding, fields, shapes, records = codes_codecs_fields_shapes_and_records
    streams = {"shp" : io.BytesIO(), "shx" : io.BytesIO(), "dbf" : io.BytesIO(),}
    w = shp.Writer(shapeType = code_ex, encoding=encoding, strict=True, **streams)

    expected_shapes = []

    written_fields, written_records = _write_fields_and_records_to_strict(w, fields, records)

    if not written_fields:
        try:
            w.close()
        except shp.dbfFileException:
            pass
        return

    for shape, written_record in zip(shapes, written_records):
        if written_record is None:
            continue
        w.shape(shape)
        expected_shapes.append(shape)

    w.close()

    with shp.Reader(encoding=encoding, **streams) as r:
        _assert_reader_matches_expected_fields(r, written_fields, True)
        _assert_reader_matches_expected_records(r, written_fields, written_records)
        _assert_reader_matches_expected_shapes(r, code_ex, expected_shapes)