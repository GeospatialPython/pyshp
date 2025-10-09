from __future__ import annotations
from datetime import date
from typing import NamedTuple, overload, SupportsIndex, Iterable, Any, Optional

from shapefile.constants import FIELD_TYPE_ALIASES, FieldType, ShapefileException
from shapefile.types import FieldTypeT, RecordValue, RecordValueNotDate, GeoJSONFeature, GeoJSONFeatureCollection, GeoJSONGeometryCollection
from shapefile.shapes import Shape, NULL

# Use functional syntax to have an attribute named type, a Python keyword
class Field(NamedTuple):
    name: str
    field_type: FieldTypeT
    size: int
    decimal: int

    @classmethod
    def from_unchecked(
        cls,
        name: str,
        field_type: str | bytes | FieldTypeT = "C",
        size: int = 50,
        decimal: int = 0,
    ) -> Field:
        try:
            type_ = FIELD_TYPE_ALIASES[field_type]
        except KeyError:
            raise ShapefileException(
                f"field_type must be in {{FieldType.__members__}}. Got: {field_type=}. "
            )

        if type_ is FieldType.D:
            size = 8
            decimal = 0
        elif type_ is FieldType.L:
            size = 1
            decimal = 0

        # A doctest in README.md previously passed in a string ('40') for size,
        # so explictly convert name to str, and size and decimal to ints.
        return cls(
            name=str(name), field_type=type_, size=int(size), decimal=int(decimal)
        )

    def __repr__(self) -> str:
        return f'Field(name="{self.name}", field_type=FieldType.{self.field_type}, size={self.size}, decimal={self.decimal})'


class _Record(list[RecordValue]):
    """
    A class to hold a record. Subclasses list to ensure compatibility with
    former work and to reuse all the optimizations of the builtin list.
    In addition to the list interface, the values of the record
    can also be retrieved using the field's name. For example if the dbf contains
    a field ID at position 0, the ID can be retrieved with the position, the field name
    as a key, or the field name as an attribute.

    >>> # Create a Record with one field, normally the record is created by the Reader class
    >>> r = _Record({'ID': 0}, [0])
    >>> print(r[0])
    >>> print(r['ID'])
    >>> print(r.ID)
    """

    def __init__(
        self,
        field_positions: dict[str, int],
        values: Iterable[RecordValue],
        oid: int | None = None,
    ):
        """
        A Record should be created by the Reader class

        :param field_positions: A dict mapping field names to field positions
        :param values: A sequence of values
        :param oid: The object id, an int (optional)
        """
        self.__field_positions = field_positions
        if oid is not None:
            self.__oid = oid
        else:
            self.__oid = -1
        list.__init__(self, values)

    def __getattr__(self, item: str) -> RecordValue:
        """
        __getattr__ is called if an attribute is used that does
        not exist in the normal sense. For example r=Record(...), r.ID
        calls r.__getattr__('ID'), but r.index(5) calls list.index(r, 5)
        :param item: The field name, used as attribute
        :return: Value of the field
        :raises: AttributeError, if item is not a field of the shapefile
                and IndexError, if the field exists but the field's
                corresponding value in the Record does not exist
        """
        try:
            if item == "__setstate__":  # Prevent infinite loop from copy.deepcopy()
                raise AttributeError("_Record does not implement __setstate__")
            index = self.__field_positions[item]
            return list.__getitem__(self, index)
        except KeyError:
            raise AttributeError(f"{item} is not a field name")
        except IndexError:
            raise IndexError(
                f"{item} found as a field but not enough values available."
            )

    def __setattr__(self, key: str, value: RecordValue) -> None:
        """
        Sets a value of a field attribute
        :param key: The field name
        :param value: the value of that field
        :return: None
        :raises: AttributeError, if key is not a field of the shapefile
        """
        if key.startswith("_"):  # Prevent infinite loop when setting mangled attribute
            return list.__setattr__(self, key, value)
        try:
            index = self.__field_positions[key]
            return list.__setitem__(self, index, value)
        except KeyError:
            raise AttributeError(f"{key} is not a field name")

    @overload
    def __getitem__(self, i: SupportsIndex) -> RecordValue: ...
    @overload
    def __getitem__(self, s: slice) -> list[RecordValue]: ...
    @overload
    def __getitem__(self, s: str) -> RecordValue: ...
    def __getitem__(
        self, item: SupportsIndex | slice | str
    ) -> RecordValue | list[RecordValue]:
        """
        Extends the normal list item access with
        access using a fieldname

        For example r['ID'], r[0]
        :param item: Either the position of the value or the name of a field
        :return: the value of the field
        """
        try:
            return list.__getitem__(self, item)  # type: ignore[index]
        except TypeError:
            try:
                index = self.__field_positions[item]  # type: ignore[index]
            except KeyError:
                index = None
        if index is not None:
            return list.__getitem__(self, index)

        raise IndexError(f'"{item}" is not a field name and not an int')

    @overload
    def __setitem__(self, key: SupportsIndex, value: RecordValue) -> None: ...
    @overload
    def __setitem__(self, key: slice, value: Iterable[RecordValue]) -> None: ...
    @overload
    def __setitem__(self, key: str, value: RecordValue) -> None: ...
    def __setitem__(
        self,
        key: SupportsIndex | slice | str,
        value: RecordValue | Iterable[RecordValue],
    ) -> None:
        """
        Extends the normal list item access with
        access using a fieldname

        For example r['ID']=2, r[0]=2
        :param key: Either the position of the value or the name of a field
        :param value: the new value of the field
        """
        try:
            return list.__setitem__(self, key, value)  # type: ignore[misc,assignment]
        except TypeError:
            index = self.__field_positions.get(key)  # type: ignore[arg-type]
            if index is not None:
                return list.__setitem__(self, index, value)  # type: ignore[misc]

            raise IndexError(f"{key} is not a field name and not an int")

    @property
    def oid(self) -> int:
        """The index position of the record in the original shapefile"""
        return self.__oid

    def as_dict(self, date_strings: bool = False) -> dict[str, RecordValue]:
        """
        Returns this Record as a dictionary using the field names as keys
        :return: dict
        """
        dct = {f: self[i] for f, i in self.__field_positions.items()}
        if date_strings:
            for k, v in dct.items():
                if isinstance(v, date):
                    dct[k] = f"{v.year:04d}{v.month:02d}{v.day:02d}"
        return dct

    def __repr__(self) -> str:
        return f"Record #{self.__oid}: {list(self)}"

    def __dir__(self) -> list[str]:
        """
        Helps to show the field names in an interactive environment like IPython.
        See: http://ipython.readthedocs.io/en/stable/config/integrating.html

        :return: List of method names and fields
        """
        default = list(
            dir(type(self))
        )  # default list methods and attributes of this class
        fnames = list(
            self.__field_positions.keys()
        )  # plus field names (random order if Python version < 3.6)
        return default + fnames

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, _Record):
            if self.__field_positions != other.__field_positions:
                return False
        return list.__eq__(self, other)


class ShapeRecord:
    """A ShapeRecord object containing a shape along with its attributes.
    Provides the GeoJSON __geo_interface__ to return a Feature dictionary."""

    def __init__(self, shape: Shape | None = None, record: _Record | None = None):
        self.shape = shape
        self.record = record

    @property
    def __geo_interface__(self) -> GeoJSONFeature:
        return {
            "type": "Feature",
            "properties": None
            if self.record is None
            else self.record.as_dict(date_strings=True),
            "geometry": None
            if self.shape is None or self.shape.shapeType == NULL
            else self.shape.__geo_interface__,
        }


class Shapes(list[Optional[Shape]]):
    """A class to hold a list of Shape objects. Subclasses list to ensure compatibility with
    former work and to reuse all the optimizations of the builtin list.
    In addition to the list interface, this also provides the GeoJSON __geo_interface__
    to return a GeometryCollection dictionary."""

    def __repr__(self) -> str:
        return f"Shapes: {list(self)}"

    @property
    def __geo_interface__(self) -> GeoJSONGeometryCollection:
        # Note: currently this will fail if any of the shapes are null-geometries
        # could be fixed by storing the shapefile shapeType upon init, returning geojson type with empty coords
        collection = GeoJSONGeometryCollection(
            type="GeometryCollection",
            geometries=[shape.__geo_interface__ for shape in self if shape is not None],
        )
        return collection


class ShapeRecords(list[ShapeRecord]):
    """A class to hold a list of ShapeRecord objects. Subclasses list to ensure compatibility with
    former work and to reuse all the optimizations of the builtin list.
    In addition to the list interface, this also provides the GeoJSON __geo_interface__
    to return a FeatureCollection dictionary."""

    def __repr__(self) -> str:
        return f"ShapeRecords: {list(self)}"

    @property
    def __geo_interface__(self) -> GeoJSONFeatureCollection:
        return GeoJSONFeatureCollection(
            type="FeatureCollection",
            features=[shaperec.__geo_interface__ for shaperec in self],
        )