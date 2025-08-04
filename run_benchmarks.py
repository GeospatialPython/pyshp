# Based on Taneli Hukkinen's https://github.com/hukkin/tomli-w/blob/master/benchmark/run.py

from __future__ import annotations

import collections
import functools
import os
import timeit
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryFile as TempF
from typing import Iterable, Union, cast

import shapefile

# For shapefiles from https://github.com/JamesParrott/PyShp_test_shapefile
DEFAULT_PYSHP_TEST_REPO = (
    rf"{os.getenv('USERPROFILE')}\Coding\repos\PyShp_test_shapefile"
)
PYSHP_TEST_REPO = Path(os.getenv("PYSHP_TEST_REPO", DEFAULT_PYSHP_TEST_REPO))
REPO_ROOT = Path(__file__).parent


blockgroups_file = REPO_ROOT / "shapefiles" / "blockgroups.shp"
edit_file = REPO_ROOT / "shapefiles" / "test" / "edit.shp"
merge_file = REPO_ROOT / "shapefiles" / "test" / "merge.shp"
states_provinces_file = PYSHP_TEST_REPO / "ne_10m_admin_1_states_provinces.shp"
tiny_countries_file = PYSHP_TEST_REPO / "ne_110m_admin_0_tiny_countries.shp"
gis_osm_natural_file = PYSHP_TEST_REPO / "gis_osm_natural_a_free_1.zip"


def benchmark(
    name: str,
    run_count: int,
    func: Callable,
    col_widths: tuple,
    compare_to: float | None = None,
) -> float:
    placeholder = "Running..."
    print(f"{name:>{col_widths[0]}} | {placeholder}", end="", flush=True)
    time_taken = timeit.timeit(func, number=run_count)
    print("\b" * len(placeholder), end="")
    time_suffix = " s"
    print(f"{time_taken:{col_widths[1] - len(time_suffix)}.3g}{time_suffix}", end="")
    print()
    return time_taken


fields = {}
shapeRecords = collections.defaultdict(list)


def open_shapefile_with_PyShp(target: Union[str, os.PathLike]):
    with shapefile.Reader(target) as r:
        fields[target] = r.fields
        for shapeRecord in r.iterShapeRecords():
            shapeRecords[target].append(shapeRecord)


def write_shapefile_with_PyShp(target: Union[str, os.PathLike]):
    with TempF("wb") as shp, TempF("wb") as dbf, TempF("wb") as shx:
        with shapefile.Writer(shp=shp, dbf=dbf, shx=shx) as w:  # type: ignore [arg-type]
            for field_info_tuple in fields[target]:
                w.field(*field_info_tuple)
            for shapeRecord in shapeRecords[target]:
                w.shape(cast(shapefile.Shape, shapeRecord.shape))
                record = cast(Iterable, shapeRecord.record)
                w.record(*record)


SHAPEFILES = {
    "Blockgroups": blockgroups_file,
    "Edit": edit_file,
    "Merge": merge_file,
    "States_35MB": states_provinces_file,
    "Tiny Countries": tiny_countries_file,
    "GIS_OSM_zip_10MB": gis_osm_natural_file,
}


# Load files to avoid one off delays that only affect first disk seek
for file_path in SHAPEFILES.values():
    file_path.read_bytes()

reader_benchmarks = [
    functools.partial(
        benchmark,
        name=f"Read {test_name}",
        func=functools.partial(open_shapefile_with_PyShp, target=target),
    )
    for test_name, target in SHAPEFILES.items()
]

# Require fields and shapeRecords to first have been populated
# from data from previouly running the reader_benchmarks
writer_benchmarks = [
    functools.partial(
        benchmark,
        name=f"Write {test_name}",
        func=functools.partial(write_shapefile_with_PyShp, target=target),
    )
    for test_name, target in SHAPEFILES.items()
]


def run(run_count: int, benchmarks: list[Callable[[], None]]) -> None:
    col_widths = (22, 10)
    col_head = ("parser", "exec time", "performance (more is better)")
    print(f"Running benchmarks {run_count} times:")
    print("-" * col_widths[0] + "---" + "-" * col_widths[1])
    print(f"{col_head[0]:>{col_widths[0]}} | {col_head[1]:>{col_widths[1]}}")
    print("-" * col_widths[0] + "-+-" + "-" * col_widths[1])
    for benchmark in benchmarks:
        benchmark(  # type: ignore [call-arg]
            run_count=run_count,
            col_widths=col_widths,
        )


if __name__ == "__main__":
    print("Reader tests:")
    run(1, reader_benchmarks)  # type: ignore [arg-type]
    print("\n\nWriter tests:")
    run(1, writer_benchmarks)  # type: ignore [arg-type]
