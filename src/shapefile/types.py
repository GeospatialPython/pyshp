import io
from datetime import date
from os import PathLike
from typing import (
    IO,
    Any,
    Final,
    Literal,
    Optional,
    Protocol,
    TypeVar,
    Union,
)

## Custom type variables

T = TypeVar("T")
Point2D = tuple[float, float]
Point3D = tuple[float, float, float]
PointMT = tuple[float, float, Optional[float]]
PointZT = tuple[float, float, float, Optional[float]]

Coord = Union[Point2D, Point3D]
Coords = list[Coord]

PointT = Union[Point2D, PointMT, PointZT]
PointsT = list[PointT]

BBox = tuple[float, float, float, float]
MBox = tuple[float, float]
ZBox = tuple[float, float]


class WriteableBinStream(Protocol):
    def write(self, b: bytes) -> int: ...


class ReadableBinStream(Protocol):
    def read(self, size: int = -1) -> bytes: ...


class WriteSeekableBinStream(Protocol):
    def write(self, b: bytes) -> int: ...
    def seek(self, offset: int, whence: int = 0) -> int: ...
    def tell(self) -> int: ...


class ReadSeekableBinStream(Protocol):
    def seek(self, offset: int, whence: int = 0) -> int: ...
    def tell(self) -> int: ...
    def read(self, size: int = -1) -> bytes: ...


class ReadWriteSeekableBinStream(Protocol):
    def write(self, b: bytes) -> int: ...
    def seek(self, offset: int, whence: int = 0) -> int: ...
    def tell(self) -> int: ...
    def read(self, size: int = -1) -> bytes: ...


# File name, file object or anything with a read() method that returns bytes.
BinaryFileT = Union[str, PathLike[Any], IO[bytes]]
BinaryFileStreamT = Union[IO[bytes], io.BytesIO, WriteSeekableBinStream]

FieldTypeT = Literal["C", "D", "F", "L", "M", "N"]


# https://en.wikipedia.org/wiki/.dbf#Database_records
class FieldType:
    """A bare bones 'enum', as the enum library noticeably slows performance."""

    C: Final = "C"  # "Character"  # (str)
    D: Final = "D"  # "Date"
    F: Final = "F"  # "Floating point"
    L: Final = "L"  # "Logical"  # (bool)
    M: Final = "M"  # "Memo"  # Legacy. (10 digit str, starting block in an .dbt file)
    N: Final = "N"  # "Numeric"  # (int)
    __members__: set[FieldTypeT] = {
        "C",
        "D",
        "F",
        "L",
        "M",
        "N",
    }


FIELD_TYPE_ALIASES: dict[str | bytes, FieldTypeT] = {}
for c in FieldType.__members__:
    FIELD_TYPE_ALIASES[c.upper()] = c
    FIELD_TYPE_ALIASES[c.lower()] = c
    FIELD_TYPE_ALIASES[c.encode("ascii").lower()] = c
    FIELD_TYPE_ALIASES[c.encode("ascii").upper()] = c



RecordValueNotDate = Union[bool, int, float, str]

# A Possible value in a Shapefile dbf record, i.e. L, N, M, F, C, or D types
RecordValue = Union[RecordValueNotDate, date]
