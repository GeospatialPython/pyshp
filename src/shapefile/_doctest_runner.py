import doctest
import sys
from typing import Iterable, Iterator
from urllib.parse import urlparse, urlunparse

from .constants import REPLACE_REMOTE_URLS_WITH_LOCALHOST

def _get_doctests() -> doctest.DocTest:
    # run tests
    with open("README.md", "rb") as fobj:
        tests = doctest.DocTestParser().get_doctest(
            string=fobj.read().decode("utf8").replace("\r\n", "\n"),
            globs={},
            name="README",
            filename="README.md",
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


def _replace_remote_url(
    old_url: str,
    # Default port of Python http.server
    port: int = 8000,
    scheme: str = "http",
    netloc: str = "localhost",
    path: str | None = None,
    params: str = "",
    query: str = "",
    fragment: str = "",
) -> str:
    old_parsed = urlparse(old_url)

    # Strip subpaths, so an artefacts
    # repo or file tree can be simpler and flat
    if path is None:
        path = old_parsed.path.rpartition("/")[2]

    if port not in (None, ""):  # type: ignore[comparison-overlap]
        netloc = f"{netloc}:{port}"

    new_parsed = old_parsed._replace(
        scheme=scheme,
        netloc=netloc,
        path=path,
        params=params,
        query=query,
        fragment=fragment,
    )

    new_url = urlunparse(new_parsed)
    return new_url


def _test(args: list[str] = sys.argv[1:], verbosity: bool = False) -> int:
    if verbosity == 0:
        print("Getting doctests...")

    import re

    tests = _get_doctests()

    if len(args) >= 2 and args[0] == "-m":
        if verbosity == 0:
            print("Filtering doctests...")
        tests.examples = list(
            _filter_network_doctests(
                tests.examples,
                include_network=args[1] == "network",
                include_non_network=args[1] == "not network",
            )
        )

    if REPLACE_REMOTE_URLS_WITH_LOCALHOST:
        if verbosity == 0:
            print("Replacing remote urls with http://localhost in doctests...")

        for example in tests.examples:
            match_url_str_literal = re.search(r'"(https://.*)"', example.source)
            if not match_url_str_literal:
                continue
            old_url = match_url_str_literal.group(1)
            new_url = _replace_remote_url(old_url)
            example.source = example.source.replace(old_url, new_url)

    runner = doctest.DocTestRunner(verbose=verbosity, optionflags=doctest.FAIL_FAST)

    if verbosity == 0:
        print(f"Running {len(tests.examples)} doctests...")
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