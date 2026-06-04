from __future__ import annotations

import argparse
import doctest
import os
import re
import sys
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

DEFAULT_README = Path(__file__).parent.parent / "README.md"


# Test config (for the Doctest runner and test_shapefile.py)
REPLACE_REMOTE_URLS_WITH_LOCALHOST = (
    os.getenv("REPLACE_REMOTE_URLS_WITH_LOCALHOST", "").lower() == "true"
)


# Begin Testing
def _get_doctests(readme: Path = DEFAULT_README) -> doctest.DocTest:
    # run tests
    with readme.open("rb") as fobj:
        tests = doctest.DocTestParser().get_doctest(
            string=fobj.read().decode("utf8").replace("\r\n", "\n"),
            globs={},
            name=fobj.name,  # readme.stem,
            filename=fobj.name,  # readme.name,
            lineno=0,
        )

    return tests


def _filter_network_doctests(
    examples: Iterable[doctest.Example],
    include_network: bool = False,
    include_non_network: bool = True,
) -> Iterator[doctest.Example]:
    globals_from_network_doctests = set()

    if not (include_network or include_non_network):
        return

    examples_it = iter(examples)

    yield next(examples_it)

    for example in examples_it:
        # Track variables in doctest shell sessions defined from commands
        # that poll remote URLs, to skip subsequent commands until all
        # such dependent variables are reassigned.

        if 'sf = shapefile.Reader("https://' in example.source:
            globals_from_network_doctests.add("sf")
            if include_network:
                yield example
            continue

        lhs = example.source.partition("=")[0]

        for target in lhs.split(","):
            target = target.strip()
            if target in globals_from_network_doctests:
                globals_from_network_doctests.remove(target)

        # Non-network tests dependent on the network tests.
        if globals_from_network_doctests:
            if include_network:
                yield example
            continue

        if not include_non_network:
            continue

        yield example


def _replace_remote_url_with_localhost(old_url: str) -> str:

    old_split = urlsplit(old_url)

    # Strip subpaths, so an artefacts
    # repo or file tree can be simpler and flat
    path = old_split.path.rpartition("/")[2]

    new_split = old_split._replace(
        scheme="http",
        netloc="localhost:8000",  # Default port of Python http.server
        path=path,
        query="",
        fragment="",
    )

    return str(urlunsplit(new_split))


_URL_STR_LITERAL_PATTERN = r'"(https?://.*)"'


def _change_remote_url_match_to_localhost(
    match: re.Match[Any],  # A Match from _URL_STR_LITERAL_PATTERN above
) -> str:

    old_url = match.group(1)
    new_url = _replace_remote_url_with_localhost(old_url)
    return f'"{new_url}"'


def _test(
    temp_dir: str | None = None,
    readme: Path = DEFAULT_README,
    include_network: bool = False,
    include_non_network: bool = True,
    verbosity: bool = False,
) -> int:

    if verbosity == 0:
        print("Getting doctests...")

    tests = _get_doctests(readme=readme)

    if verbosity == 0:
        print("Filtering doctests...")
    tests.examples = list(
        _filter_network_doctests(
            tests.examples,
            include_network=include_network,
            include_non_network=include_non_network,
        )
    )

    if REPLACE_REMOTE_URLS_WITH_LOCALHOST:
        if verbosity == 0:
            print("Replacing remote urls with http://localhost in doctests...")

        for example in tests.examples:
            example.source = re.sub(
                pattern=_URL_STR_LITERAL_PATTERN,
                repl=_change_remote_url_match_to_localhost,
                string=example.source,
            )

    if temp_dir is not None:
        for example in tests.examples:
            example.source = example.source.replace(
                "tests/shapefiles/test/", f"{temp_dir}/"
            )

    runner = doctest.DocTestRunner(verbose=verbosity, optionflags=doctest.FAIL_FAST)

    if verbosity == 0:
        print(f"Running {len(tests.examples)} doctests...")
    # Deleting a temp dir will error if it contains shapefiles to which
    # unclosed Readers still file objects open,
    # regardless of using clear_globs=True or calling gc.collect afterwards.
    failure_count, __test_count = runner.run(tests)

    # print results
    if verbosity:
        runner.summarize(True)
    else:
        if failure_count == 0:
            print("All test passed successfully")
        elif failure_count > 0:
            runner.summarize(verbosity)

    return failure_count


def main() -> None:
    """
    Doctests are contained in the file 'README.md', and are tested using the built-in
    testing libraries.
    """

    parser = argparse.ArgumentParser(
        prog="run_doctests.py",
        description="PyShp's doctest runner",
    )

    parser.add_argument(
        "--readme",
        type=Path,
        default=DEFAULT_README,
    )
    parser.add_argument(
        "-m",
        type=str,
        default="not network",
    )
    namespace = parser.parse_args()

    with tempfile.TemporaryDirectory() as td:
        failure_count = _test(
            temp_dir=Path(td).as_posix(),
            readme=namespace.readme,
            include_network=namespace.m.lower().strip() == "network",
            include_non_network=namespace.m.lower().strip() == "not network",
        )
    sys.exit(failure_count)


# This allows a PyShp wheel installed in the env to be tested
# against the doctests.
if __name__ == "__main__":
    main()
