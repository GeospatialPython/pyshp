from __future__ import annotations

import array
import os
from os import PathLike
from struct import Struct
from typing import Any, Generic, TypeVar, overload

from .types import T

# Helpers


unpack_2_int32_be = Struct(">2i").unpack


@overload
def fsdecode_if_pathlike(path: PathLike[Any]) -> str: ...
@overload
def fsdecode_if_pathlike(path: T) -> T: ...
def fsdecode_if_pathlike(path: Any) -> Any:
    if isinstance(path, PathLike):
        return os.fsdecode(path)  # str

    return path


# Begin

ARR_TYPE = TypeVar("ARR_TYPE", int, float)


# In Python 3.12 we can do:
# class _Array(array.array[ARR_TYPE], Generic[ARR_TYPE]):
class _Array(array.array, Generic[ARR_TYPE]):  # type: ignore[type-arg]
    """Converts python tuples to lists of the appropriate type.
    Used to unpack different shapefile header parts."""

    def __repr__(self) -> str:
        return str(self.tolist())
