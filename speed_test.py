# Based on Taneli Hukkinen's https://github.com/hukkin/tomli-w/blob/master/benchmark/run.py

from __future__ import annotations

import functools
import os
import timeit
from collections.abc import Callable
from pathlib import Path
from typing import Union

import shapefile as shp

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
    col_width: tuple,
    compare_to: float | None = None,
) -> float:
    placeholder = "Running..."
    print(f"{name:>{col_width[0]}} | {placeholder}", end="", flush=True)
    time_taken = timeit.timeit(func, number=run_count)
    print("\b" * len(placeholder), end="")
    time_suffix = " s"
    print(f"{time_taken:{col_width[1]-len(time_suffix)}.3g}{time_suffix}", end="")
    print()
    return time_taken


def open_shapefile_with_PyShp(target: Union[str, os.PathLike]):
    with shp.Reader(target) as r:
        for shapeRecord in r.iterShapeRecords():
            pass


READER_TESTS = {
    "Blockgroups": blockgroups_file,
    "Edit": edit_file,
    "Merge": merge_file,
    "States_35MB": states_provinces_file,
    "Tiny Countries": tiny_countries_file,
    "GIS_OSM_zip_10MB": gis_osm_natural_file,
}


def run(run_count: int) -> None:
    col_width = (21, 10)
    col_head = ("parser", "exec time", "performance (more is better)")
    # Load files to avoid one off delays that only affect first disk seek
    for file_path in READER_TESTS.values():
        file_path.read_bytes()
    print(f"Running benchmarks {run_count} times:")
    print("-" * col_width[0] + "---" + "-" * col_width[1])
    print(f"{col_head[0]:>{col_width[0]}} | {col_head[1]:>{col_width[1]}}")
    print("-" * col_width[0] + "-+-" + "-" * col_width[1])
    for test_name, target in READER_TESTS.items():
        benchmark(
            f"Read {test_name}",
            run_count,
            functools.partial(open_shapefile_with_PyShp, target=target),
            col_width,
        )

if __name__ == "__main__":
    run(1)
