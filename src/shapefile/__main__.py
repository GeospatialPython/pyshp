import sys

from ._doctest_runner import _test


def main() -> None:
    """
    Doctests are contained in the file 'README.md', and are tested using the built-in
    testing libraries.
    """
    failure_count = _test()
    sys.exit(failure_count)


if __name__ == "__main__":
    main()
