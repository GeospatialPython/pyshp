from __future__ import annotations

import io
import os
import sys
import tempfile
import zipfile
from collections.abc import Container, Iterable, Iterator
from datetime import date
from os import PathLike
from struct import Struct, calcsize, unpack
from types import TracebackType
from typing import IO, Any, Union, cast
from urllib.error import HTTPError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from .classes import (
    FIELD_TYPE_ALIASES,
    GeoJSONFeatureCollectionWithBBox,
    ShapeRecord,
    ShapeRecords,
    Shapes,
    _Array,
    _Record,
)
from .constants import NODATA, SHAPE_CLASS_FROM_SHAPETYPE, SHAPETYPE_LOOKUP
from .exceptions import ShapefileException
from .helpers import fsdecode_if_pathlike, unpack_2_int32_be
from .shapes import Shape
from .types import (
    BBox,
    BinaryFileStreamT,
    BinaryFileT,
    Field,
    FieldType,
    ReadSeekableBinStream,
    T,
    ZBox,
)


class _NoShpSentinel:
    """For use as a default value for shp to preserve the
    behaviour (from when all keyword args were gathered
    in the **kwargs dict) in case someone explictly
    called Reader(shp=None) to load self.shx.
    """


_NO_SHP_SENTINEL = _NoShpSentinel()


class Reader:
    """Reads the three files of a shapefile as a unit or
    separately.  If one of the three files (.shp, .shx,
    .dbf) is missing no exception is thrown until you try
    to call a method that depends on that particular file.
    The .shx index file is used if available for efficiency
    but is not required to read the geometry from the .shp
    file. The "shapefile" argument in the constructor is the
    name of the file you want to open, and can be the path
    to a shapefile on a local filesystem, inside a zipfile,
    or a url.

    You can instantiate a Reader without specifying a shapefile
    and then specify one later with the load() method.

    Only the shapefile headers are read upon loading. Content
    within each file is only accessed when required and as
    efficiently as possible. Shapefiles are usually not large
    but they can be.
    """

    CONSTITUENT_FILE_EXTS = ["shp", "shx", "dbf"]
    assert all(ext.islower() for ext in CONSTITUENT_FILE_EXTS)

    def _assert_ext_is_supported(self, ext: str) -> None:
        assert ext in self.CONSTITUENT_FILE_EXTS

    def __init__(
        self,
        shapefile_path: str | PathLike[Any] = "",
        /,
        *,
        encoding: str = "utf-8",
        encodingErrors: str = "strict",
        shp: _NoShpSentinel | BinaryFileT | None = _NO_SHP_SENTINEL,
        shx: BinaryFileT | None = None,
        dbf: BinaryFileT | None = None,
        # Keep kwargs even though unused, to preserve PyShp 2.4 API
        **kwargs: Any,
    ):
        self.shp = None
        self.shx = None
        self.dbf = None
        self._files_to_close: list[BinaryFileStreamT] = []
        self.shapeName = "Not specified"
        self._offsets: list[int] = []
        self.shpLength: int | None = None
        self.numRecords: int | None = None
        self.numShapes: int | None = None
        self.fields: list[Field] = []
        self.__dbfHdrLength = 0
        self.__fieldLookup: dict[str, int] = {}
        self.encoding = encoding
        self.encodingErrors = encodingErrors
        # See if a shapefile name was passed as the first argument
        if shapefile_path:
            path = fsdecode_if_pathlike(shapefile_path)
            if isinstance(path, str):
                if ".zip" in path:
                    # Shapefile is inside a zipfile
                    if path.count(".zip") > 1:
                        # Multiple nested zipfiles
                        raise ShapefileException(
                            f"Reading from multiple nested zipfiles is not supported: {path}"
                        )
                    # Split into zipfile and shapefile paths
                    if path.endswith(".zip"):
                        zpath = path
                        shapefile = None
                    else:
                        zpath = path[: path.find(".zip") + 4]
                        shapefile = path[path.find(".zip") + 4 + 1 :]

                    zipfileobj: (
                        tempfile._TemporaryFileWrapper[bytes] | io.BufferedReader
                    )
                    # Create a zip file handle
                    if zpath.startswith("http"):
                        # Zipfile is from a url
                        # Download to a temporary url and treat as normal zipfile
                        req = Request(
                            zpath,
                            headers={
                                "User-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"
                            },
                        )
                        resp = urlopen(req)
                        # write zipfile data to a read+write tempfile and use as source, gets deleted when garbage collected
                        zipfileobj = tempfile.NamedTemporaryFile(
                            mode="w+b", suffix=".zip", delete=True
                        )
                        zipfileobj.write(resp.read())
                        zipfileobj.seek(0)
                    else:
                        # Zipfile is from a file
                        zipfileobj = open(zpath, mode="rb")
                    # Open the zipfile archive
                    with zipfile.ZipFile(zipfileobj, "r") as archive:
                        if not shapefile:
                            # Only the zipfile path is given
                            # Inspect zipfile contents to find the full shapefile path
                            shapefiles = [
                                name
                                for name in archive.namelist()
                                if (name.endswith(".SHP") or name.endswith(".shp"))
                            ]
                            # The zipfile must contain exactly one shapefile
                            if len(shapefiles) == 0:
                                raise ShapefileException(
                                    "Zipfile does not contain any shapefiles"
                                )
                            if len(shapefiles) == 1:
                                shapefile = shapefiles[0]
                            else:
                                raise ShapefileException(
                                    f"Zipfile contains more than one shapefile: {shapefiles}. "
                                    "Please specify the full path to the shapefile you would like to open."
                                )
                        # Try to extract file-like objects from zipfile
                        shapefile = os.path.splitext(shapefile)[
                            0
                        ]  # root shapefile name
                        for lower_ext in self.CONSTITUENT_FILE_EXTS:
                            for cased_ext in [lower_ext, lower_ext.upper()]:
                                try:
                                    member = archive.open(f"{shapefile}.{cased_ext}")
                                    # write zipfile member data to a read+write tempfile and use as source, gets deleted on close()
                                    fileobj = tempfile.NamedTemporaryFile(
                                        mode="w+b", delete=True
                                    )
                                    fileobj.write(member.read())
                                    fileobj.seek(0)
                                    setattr(self, lower_ext, fileobj)
                                    self._files_to_close.append(fileobj)
                                except (OSError, AttributeError, KeyError):
                                    pass
                    # Close and delete the temporary zipfile
                    try:
                        zipfileobj.close()
                        # TODO Does catching all possible exceptions really increase
                        # the chances of closing the zipfile successully, or does it
                        # just mean .close() failures will still fail, but fail
                        # silently?
                    except:  # noqa: E722
                        pass
                    # Try to load shapefile
                    if self.shp or self.dbf:
                        # Load and exit early
                        self.load()
                        return

                    raise ShapefileException(
                        f"No shp or dbf file found in zipfile: {path}"
                    )

                if path.startswith("http"):
                    # Shapefile is from a url
                    # Download each file to temporary path and treat as normal shapefile path
                    urlinfo = urlparse(path)
                    urlpath = urlinfo[2]
                    urlpath, _ = os.path.splitext(urlpath)
                    shapefile = os.path.basename(urlpath)
                    for ext in ["shp", "shx", "dbf"]:
                        try:
                            _urlinfo = list(urlinfo)
                            _urlinfo[2] = urlpath + "." + ext
                            _path = urlunparse(_urlinfo)
                            req = Request(
                                _path,
                                headers={
                                    "User-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"
                                },
                            )
                            resp = urlopen(req)
                            # write url data to a read+write tempfile and use as source, gets deleted on close()
                            fileobj = tempfile.NamedTemporaryFile(
                                mode="w+b", delete=True
                            )
                            fileobj.write(resp.read())
                            fileobj.seek(0)
                            setattr(self, ext, fileobj)
                            self._files_to_close.append(fileobj)
                        except HTTPError:
                            pass
                    if self.shp or self.dbf:
                        # Load and exit early
                        self.load()
                        return

                    raise ShapefileException(f"No shp or dbf file found at url: {path}")

                # Local file path to a shapefile
                # Load and exit early
                self.load(path)
                return

        if shp is not _NO_SHP_SENTINEL:
            shp = cast(Union[str, PathLike[Any], IO[bytes], None], shp)
            self.shp = self.__seek_0_on_file_obj_wrap_or_open_from_name("shp", shp)
            self.shx = self.__seek_0_on_file_obj_wrap_or_open_from_name("shx", shx)

        self.dbf = self.__seek_0_on_file_obj_wrap_or_open_from_name("dbf", dbf)

        # Load the files
        if self.shp or self.dbf:
            self._try_to_set_constituent_file_headers()

    def __seek_0_on_file_obj_wrap_or_open_from_name(
        self,
        ext: str,
        file_: BinaryFileT | None,
    ) -> None | IO[bytes]:
        # assert ext in {'shp', 'dbf', 'shx'}
        self._assert_ext_is_supported(ext)

        if file_ is None:
            return None

        if isinstance(file_, (str, PathLike)):
            baseName, __ = os.path.splitext(file_)
            return self._load_constituent_file(baseName, ext)

        if hasattr(file_, "read"):
            # Copy if required
            try:
                file_.seek(0)
                return file_
            except (NameError, io.UnsupportedOperation):
                return io.BytesIO(file_.read())

        raise ShapefileException(
            f"Could not load shapefile constituent file from: {file_}"
        )

    def __str__(self) -> str:
        """
        Use some general info on the shapefile as __str__
        """
        info = ["shapefile Reader"]
        if self.shp:
            info.append(
                f"    {len(self)} shapes (type '{SHAPETYPE_LOOKUP[self.shapeType]}')"
            )
        if self.dbf:
            info.append(f"    {len(self)} records ({len(self.fields)} fields)")
        return "\n".join(info)

    def __enter__(self) -> Reader:
        """
        Enter phase of context manager.
        """
        return self

    # def __exit__(self, exc_type, exc_val, exc_tb) -> None:
    def __exit__(
        self,
        exc_type: BaseException | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """
        Exit phase of context manager, close opened files.
        """
        self.close()
        return None

    def __len__(self) -> int:
        """Returns the number of shapes/records in the shapefile."""
        if self.dbf:
            # Preferably use dbf record count
            if self.numRecords is None:
                self.__dbfHeader()

            # .__dbfHeader sets self.numRecords or raises Exception
            return cast(int, self.numRecords)

        if self.shp:
            # Otherwise use shape count
            if self.shx:
                if self.numShapes is None:
                    self.__shxHeader()

                # .__shxHeader sets self.numShapes or raises Exception
                return cast(int, self.numShapes)

            # Index file not available, iterate all shapes to get total count
            if self.numShapes is None:
                # Determine length of shp file
                shp = self.shp
                checkpoint = shp.tell()
                shp.seek(0, 2)
                shpLength = shp.tell()
                shp.seek(100)
                # Do a fast shape iteration until end of file.
                offsets = []
                pos = shp.tell()
                while pos < shpLength:
                    offsets.append(pos)
                    # Unpack the shape header only
                    (__recNum, recLength) = unpack_2_int32_be(shp.read(8))
                    # Jump to next shape position
                    pos += 8 + (2 * recLength)
                    shp.seek(pos)
                # Set numShapes and offset indices
                self.numShapes = len(offsets)
                self._offsets = offsets
                # Return to previous file position
                shp.seek(checkpoint)

            return self.numShapes

        # No file loaded yet, treat as 'empty' shapefile
        return 0

    def __iter__(self) -> Iterator[ShapeRecord]:
        """Iterates through the shapes/records in the shapefile."""
        yield from self.iterShapeRecords()

    @property
    def __geo_interface__(self) -> GeoJSONFeatureCollectionWithBBox:
        shaperecords = self.shapeRecords()
        fcollection = GeoJSONFeatureCollectionWithBBox(
            bbox=list(self.bbox),
            **shaperecords.__geo_interface__,
        )
        return fcollection

    @property
    def shapeTypeName(self) -> str:
        return SHAPETYPE_LOOKUP[self.shapeType]

    def load(self, shapefile: str | None = None) -> None:
        """Opens a shapefile from a filename or file-like
        object. Normally this method would be called by the
        constructor with the file name as an argument."""
        if shapefile:
            (shapeName, __ext) = os.path.splitext(shapefile)
            self.shapeName = shapeName
            self.load_shp(shapeName)
            self.load_shx(shapeName)
            self.load_dbf(shapeName)
            if not (self.shp or self.dbf):
                raise ShapefileException(
                    f"Unable to open {shapeName}.dbf or {shapeName}.shp."
                )
        self._try_to_set_constituent_file_headers()

    def _try_to_set_constituent_file_headers(self) -> None:
        if self.shp:
            self.__shpHeader()
        if self.dbf:
            self.__dbfHeader()
        if self.shx:
            self.__shxHeader()

    def _try_get_open_constituent_file(
        self,
        shapefile_name: str,
        ext: str,
    ) -> IO[bytes] | None:
        """
        Attempts to open a .shp, .dbf or .shx file,
        with both lower case and upper case file extensions,
        and return it.  If it was not possible to open the file, None is returned.
        """
        # typing.LiteralString is only available from PYthon 3.11 onwards.
        # https://docs.python.org/3/library/typing.html#typing.LiteralString
        # assert ext in {'shp', 'dbf', 'shx'}
        self._assert_ext_is_supported(ext)

        try:
            return open(f"{shapefile_name}.{ext}", "rb")
        except OSError:
            try:
                return open(f"{shapefile_name}.{ext.upper()}", "rb")
            except OSError:
                return None

    def _load_constituent_file(
        self,
        shapefile_name: str,
        ext: str,
    ) -> IO[bytes] | None:
        """
        Attempts to open a .shp, .dbf or .shx file, with the extension
        as both lower and upper case, and if successful append it to
        self._files_to_close.
        """
        shp_dbf_or_dhx_file = self._try_get_open_constituent_file(shapefile_name, ext)
        if shp_dbf_or_dhx_file is not None:
            self._files_to_close.append(shp_dbf_or_dhx_file)
        return shp_dbf_or_dhx_file

    def load_shp(self, shapefile_name: str) -> None:
        """
        Attempts to load file with .shp extension as both lower and upper case
        """
        self.shp = self._load_constituent_file(shapefile_name, "shp")

    def load_shx(self, shapefile_name: str) -> None:
        """
        Attempts to load file with .shx extension as both lower and upper case
        """
        self.shx = self._load_constituent_file(shapefile_name, "shx")

    def load_dbf(self, shapefile_name: str) -> None:
        """
        Attempts to load file with .dbf extension as both lower and upper case
        """
        self.dbf = self._load_constituent_file(shapefile_name, "dbf")

    def __del__(self) -> None:
        self.close()

    def close(self) -> None:
        # Close any files that the reader opened (but not those given by user)
        for attribute in self._files_to_close:
            if hasattr(attribute, "close"):
                try:
                    attribute.close()
                except OSError:
                    pass
        self._files_to_close = []

    def __getFileObj(self, f: T | None) -> T:
        """Checks to see if the requested shapefile file object is
        available. If not a ShapefileException is raised."""
        if not f:
            raise ShapefileException(
                "Shapefile Reader requires a shapefile or file-like object."
            )
        if self.shp and self.shpLength is None:
            self.load()
        if self.dbf and len(self.fields) == 0:
            self.load()
        return f

    def __restrictIndex(self, i: int) -> int:
        """Provides list-like handling of a record index with a clearer
        error message if the index is out of bounds."""
        if self.numRecords:
            rmax = self.numRecords - 1
            if abs(i) > rmax:
                raise IndexError(
                    f"Shape or Record index: {i} out of range.  Max index: {rmax}"
                )
            if i < 0:
                i = range(self.numRecords)[i]
        return i

    def __shpHeader(self) -> None:
        """Reads the header information from a .shp file."""
        if not self.shp:
            raise ShapefileException(
                "Shapefile Reader requires a shapefile or file-like object. (no shp file found"
            )

        shp = self.shp
        # File length (16-bit word * 2 = bytes)
        shp.seek(24)
        self.shpLength = unpack(">i", shp.read(4))[0] * 2
        # Shape type
        shp.seek(32)
        self.shapeType = unpack("<i", shp.read(4))[0]
        # The shapefile's bounding box (lower left, upper right)
        # self.bbox: BBox = tuple(_Array("d", unpack("<4d", shp.read(32))))
        self.bbox: BBox = unpack("<4d", shp.read(32))
        # xmin, ymin, xmax, ymax = unpack("<4d", shp.read(32))
        # self.bbox = BBox(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)
        # Elevation
        # self.zbox: ZBox = tuple(_Array("d", unpack("<2d", shp.read(16))))
        self.zbox: ZBox = unpack("<2d", shp.read(16))
        # zmin, zmax = unpack("<2d", shp.read(16))
        # self.zbox = ZBox(zmin=zmin, zmax=zmax)
        # Measure
        # Measure values less than -10e38 are nodata values according to the spec
        m_bounds = [
            float(m_bound) if m_bound >= NODATA else None
            for m_bound in unpack("<2d", shp.read(16))
        ]
        # self.mbox = MBox(mmin=m_bounds[0], mmax=m_bounds[1])
        self.mbox: tuple[float | None, float | None] = (m_bounds[0], m_bounds[1])

    def __shape(self, oid: int | None = None, bbox: BBox | None = None) -> Shape | None:
        """Returns the header info and geometry for a single shape."""

        f = self.__getFileObj(self.shp)

        # shape = Shape(oid=oid)
        (__recNum, recLength) = unpack_2_int32_be(f.read(8))
        # Determine the start of the next record

        # Convert from num of 16 bit words, to 8 bit bytes
        recLength_bytes = 2 * recLength

        # next_shape = f.tell() + recLength_bytes

        # Read entire record into memory to avoid having to call
        # seek on the file afterwards
        b_io: ReadSeekableBinStream = io.BytesIO(f.read(recLength_bytes))
        b_io.seek(0)

        shapeType = unpack("<i", b_io.read(4))[0]

        ShapeClass = SHAPE_CLASS_FROM_SHAPETYPE[shapeType]
        shape = ShapeClass.from_byte_stream(
            shapeType, b_io, recLength_bytes, oid=oid, bbox=bbox
        )

        # Seek to the end of this record as defined by the record header because
        # the shapefile spec doesn't require the actual content to meet the header
        # definition.  Probably allowed for lazy feature deletion.
        # f.seek(next_shape)

        return shape

    def __shxHeader(self) -> None:
        """Reads the header information from a .shx file."""
        shx = self.shx
        if not shx:
            raise ShapefileException(
                "Shapefile Reader requires a shapefile or file-like object. (no shx file found"
            )
        # File length (16-bit word * 2 = bytes) - header length
        shx.seek(24)
        shxRecordLength = (unpack(">i", shx.read(4))[0] * 2) - 100
        self.numShapes = shxRecordLength // 8

    def __shxOffsets(self) -> None:
        """Reads the shape offset positions from a .shx file"""
        shx = self.shx
        if not shx:
            raise ShapefileException(
                "Shapefile Reader requires a shapefile or file-like object. (no shx file found"
            )
        if self.numShapes is None:
            raise ShapefileException(
                "numShapes must not be None. "
                " Was there a problem with .__shxHeader() ?"
                f"Got: {self.numShapes=}"
            )
        # Jump to the first record.
        shx.seek(100)
        # Each index record consists of two nrs, we only want the first one
        shxRecords = _Array[int]("i", shx.read(2 * self.numShapes * 4))
        if sys.byteorder != "big":
            shxRecords.byteswap()
        self._offsets = [2 * el for el in shxRecords[::2]]

    def __shapeIndex(self, i: int | None = None) -> int | None:
        """Returns the offset in a .shp file for a shape based on information
        in the .shx index file."""
        shx = self.shx
        # Return None if no shx or no index requested
        if not shx or i is None:
            return None
        # At this point, we know the shx file exists
        if not self._offsets:
            self.__shxOffsets()
        return self._offsets[i]

    def shape(self, i: int = 0, bbox: BBox | None = None) -> Shape | None:
        """Returns a shape object for a shape in the geometry
        record file.
        If the 'bbox' arg is given (list or tuple of xmin,ymin,xmax,ymax),
        returns None if the shape is not within that region.
        """
        shp = self.__getFileObj(self.shp)
        i = self.__restrictIndex(i)
        offset = self.__shapeIndex(i)
        if not offset:
            # Shx index not available.
            # Determine length of shp file
            shp.seek(0, 2)
            shpLength = shp.tell()
            shp.seek(100)
            # Do a fast shape iteration until the requested index or end of file.
            _i = 0
            offset = shp.tell()
            while offset < shpLength:
                if _i == i:
                    # Reached the requested index, exit loop with the offset value
                    break
                # Unpack the shape header only
                (__recNum, recLength) = unpack_2_int32_be(shp.read(8))
                # Jump to next shape position
                offset += 8 + (2 * recLength)
                shp.seek(offset)
                _i += 1
            # If the index was not found, it likely means the .shp file is incomplete
            if _i != i:
                raise ShapefileException(
                    f"Shape index {i} is out of bounds; the .shp file only contains {_i} shapes"
                )

        # Seek to the offset and read the shape
        shp.seek(offset)
        return self.__shape(oid=i, bbox=bbox)

    def shapes(self, bbox: BBox | None = None) -> Shapes:
        """Returns all shapes in a shapefile.
        To only read shapes within a given spatial region, specify the 'bbox'
        arg as a list or tuple of xmin,ymin,xmax,ymax.
        """
        shapes = Shapes()
        shapes.extend(self.iterShapes(bbox=bbox))
        return shapes

    def iterShapes(self, bbox: BBox | None = None) -> Iterator[Shape | None]:
        """Returns a generator of shapes in a shapefile. Useful
        for handling large shapefiles.
        To only read shapes within a given spatial region, specify the 'bbox'
        arg as a list or tuple of xmin,ymin,xmax,ymax.
        """
        shp = self.__getFileObj(self.shp)
        # Found shapefiles which report incorrect
        # shp file length in the header. Can't trust
        # that so we seek to the end of the file
        # and figure it out.
        shp.seek(0, 2)
        shpLength = shp.tell()
        shp.seek(100)

        if self.numShapes:
            # Iterate exactly the number of shapes from shx header
            for i in range(self.numShapes):
                # MAYBE: check if more left of file or exit early?
                shape = self.__shape(oid=i, bbox=bbox)
                if shape:
                    yield shape
        else:
            # No shx file, unknown nr of shapes
            # Instead iterate until reach end of file
            # Collect the offset indices during iteration
            i = 0
            offsets = []
            pos = shp.tell()
            while pos < shpLength:
                offsets.append(pos)
                shape = self.__shape(oid=i, bbox=bbox)
                pos = shp.tell()
                if shape:
                    yield shape
                i += 1
            # Entire shp file consumed
            # Update the number of shapes and list of offsets
            assert i == len(offsets)
            self.numShapes = i
            self._offsets = offsets

    def __dbfHeader(self) -> None:
        """Reads a dbf header. Xbase-related code borrows heavily from ActiveState Python Cookbook Recipe 362715 by Raymond Hettinger"""

        if not self.dbf:
            raise ShapefileException(
                "Shapefile Reader requires a shapefile or file-like object. (no dbf file found)"
            )
        dbf = self.dbf
        # read relevant header parts
        dbf.seek(0)
        self.numRecords, self.__dbfHdrLength, self.__recordLength = unpack(
            "<xxxxLHH20x", dbf.read(32)
        )

        # read fields
        numFields = (self.__dbfHdrLength - 33) // 32
        for __field in range(numFields):
            encoded_field_tuple: tuple[bytes, bytes, int, int] = unpack(
                "<11sc4xBB14x", dbf.read(32)
            )
            encoded_name, encoded_type_char, size, decimal = encoded_field_tuple

            if b"\x00" in encoded_name:
                idx = encoded_name.index(b"\x00")
            else:
                idx = len(encoded_name) - 1
            encoded_name = encoded_name[:idx]
            name = encoded_name.decode(self.encoding, self.encodingErrors)
            name = name.lstrip()

            field_type = FIELD_TYPE_ALIASES[encoded_type_char]

            self.fields.append(Field(name, field_type, size, decimal))
        terminator = dbf.read(1)
        if terminator != b"\r":
            raise ShapefileException(
                "Shapefile dbf header lacks expected terminator. (likely corrupt?)"
            )

        # insert deletion field at start
        self.fields.insert(0, Field("DeletionFlag", FieldType.C, 1, 0))

        # store all field positions for easy lookups
        # note: fieldLookup gives the index position of a field inside Reader.fields
        self.__fieldLookup = {f[0]: i for i, f in enumerate(self.fields)}

        # by default, read all fields except the deletion flag, hence "[1:]"
        # note: recLookup gives the index position of a field inside a _Record list
        fieldnames = [f[0] for f in self.fields[1:]]
        __fieldTuples, recLookup, recStruct = self.__recordFields(fieldnames)
        self.__fullRecStruct = recStruct
        self.__fullRecLookup = recLookup

    def __recordFmt(self, fields: Container[str] | None = None) -> tuple[str, int]:
        """Calculates the format and size of a .dbf record. Optional 'fields' arg
        specifies which fieldnames to unpack and which to ignore. Note that this
        always includes the DeletionFlag at index 0, regardless of the 'fields' arg.
        """
        if self.numRecords is None:
            self.__dbfHeader()
        structcodes = [f"{fieldinfo.size}s" for fieldinfo in self.fields]
        if fields is not None:
            # only unpack specified fields, ignore others using padbytes (x)
            structcodes = [
                code
                if fieldinfo.name in fields
                or fieldinfo.name == "DeletionFlag"  # always unpack delflag
                else f"{fieldinfo.size}x"
                for fieldinfo, code in zip(self.fields, structcodes)
            ]
        fmt = "".join(structcodes)
        fmtSize = calcsize(fmt)
        # total size of fields should add up to recordlength from the header
        while fmtSize < self.__recordLength:
            # if not, pad byte until reaches recordlength
            fmt += "x"
            fmtSize += 1
        return (fmt, fmtSize)

    def __recordFields(
        self, fields: Iterable[str] | None = None
    ) -> tuple[list[Field], dict[str, int], Struct]:
        """Returns the necessary info required to unpack a record's fields,
        restricted to a subset of fieldnames 'fields' if specified.
        Returns a list of field info tuples, a name-index lookup dict,
        and a Struct instance for unpacking these fields. Note that DeletionFlag
        is not a valid field.
        """
        if fields is not None:
            # restrict info to the specified fields
            # first ignore repeated field names (order doesn't matter)
            unique_fields = list(set(fields))
            # get the struct
            fmt, __fmtSize = self.__recordFmt(fields=unique_fields)
            recStruct = Struct(fmt)
            # make sure the given fieldnames exist
            for name in unique_fields:
                if name not in self.__fieldLookup or name == "DeletionFlag":
                    raise ValueError(f'"{name}" is not a valid field name')
            # fetch relevant field info tuples
            fieldTuples = []
            for fieldinfo in self.fields[1:]:
                name = fieldinfo[0]
                if name in unique_fields:
                    fieldTuples.append(fieldinfo)
            # store the field positions
            recLookup = {f[0]: i for i, f in enumerate(fieldTuples)}
        else:
            # use all the dbf fields
            fieldTuples = self.fields[1:]  # sans deletion flag
            recStruct = self.__fullRecStruct
            recLookup = self.__fullRecLookup
        return fieldTuples, recLookup, recStruct

    def __record(
        self,
        fieldTuples: list[Field],
        recLookup: dict[str, int],
        recStruct: Struct,
        oid: int | None = None,
    ) -> _Record | None:
        """Reads and returns a dbf record row as a list of values. Requires specifying
        a list of field info Field namedtuples 'fieldTuples', a record name-index dict 'recLookup',
        and a Struct instance 'recStruct' for unpacking these fields.
        """
        f = self.__getFileObj(self.dbf)

        # The only format chars in from self.__recordFmt, in recStruct from __recordFields,
        # are s and x (ascii encoded str and pad byte) so everything in recordContents is bytes
        # https://docs.python.org/3/library/struct.html#format-characters
        recordContents = recStruct.unpack(f.read(recStruct.size))

        # deletion flag field is always unpacked as first value (see __recordFmt)
        if recordContents[0] != b" ":
            # deleted record
            return None

        # drop deletion flag from values
        recordContents = recordContents[1:]

        # check that values match fields
        if len(fieldTuples) != len(recordContents):
            raise ShapefileException(
                f"Number of record values ({len(recordContents)}) is different from the requested "
                f"number of fields ({len(fieldTuples)})"
            )

        # parse each value
        record = []
        for (__name, typ, __size, decimal), value in zip(fieldTuples, recordContents):
            if typ is FieldType.N or typ is FieldType.F:
                # numeric or float: number stored as a string, right justified, and padded with blanks to the width of the field.
                value = value.split(b"\0")[0]
                value = value.replace(b"*", b"")  # QGIS NULL is all '*' chars
                if value == b"":
                    value = None
                elif decimal:
                    try:
                        value = float(value)
                    except ValueError:
                        # not parseable as float, set to None
                        value = None
                else:
                    # force to int
                    try:
                        # first try to force directly to int.
                        # forcing a large int to float and back to int
                        # will lose information and result in wrong nr.
                        value = int(value)
                    except ValueError:
                        # forcing directly to int failed, so was probably a float.
                        try:
                            value = int(float(value))
                        except ValueError:
                            # not parseable as int, set to None
                            value = None
            elif typ is FieldType.D:
                # date: 8 bytes - date stored as a string in the format YYYYMMDD.
                if (
                    not value.replace(b"\x00", b"")
                    .replace(b" ", b"")
                    .replace(b"0", b"")
                ):
                    # dbf date field has no official null value
                    # but can check for all hex null-chars, all spaces, or all 0s (QGIS null)
                    value = None
                else:
                    try:
                        # return as python date object
                        y, m, d = int(value[:4]), int(value[4:6]), int(value[6:8])
                        value = date(y, m, d)
                    except (TypeError, ValueError):
                        # if invalid date, just return as unicode string so user can decimalde
                        value = str(value.strip())
            elif typ is FieldType.L:
                # logical: 1 byte - initialized to 0x20 (space) otherwise T or F.
                if value == b" ":
                    value = None  # space means missing or not yet set
                else:
                    if value in b"YyTt1":
                        value = True
                    elif value in b"NnFf0":
                        value = False
                    else:
                        value = None  # unknown value is set to missing
            else:
                value = value.decode(self.encoding, self.encodingErrors)
                value = value.strip().rstrip(
                    "\x00"
                )  # remove null-padding at end of strings
            record.append(value)

        return _Record(recLookup, record, oid)

    def record(self, i: int = 0, fields: list[str] | None = None) -> _Record | None:
        """Returns a specific dbf record based on the supplied index.
        To only read some of the fields, specify the 'fields' arg as a
        list of one or more fieldnames.
        """
        f = self.__getFileObj(self.dbf)
        if self.numRecords is None:
            self.__dbfHeader()
        i = self.__restrictIndex(i)
        recSize = self.__recordLength
        f.seek(0)
        f.seek(self.__dbfHdrLength + (i * recSize))
        fieldTuples, recLookup, recStruct = self.__recordFields(fields)
        return self.__record(
            oid=i, fieldTuples=fieldTuples, recLookup=recLookup, recStruct=recStruct
        )

    def records(self, fields: list[str] | None = None) -> list[_Record]:
        """Returns all records in a dbf file.
        To only read some of the fields, specify the 'fields' arg as a
        list of one or more fieldnames.
        """
        if self.numRecords is None:
            self.__dbfHeader()
        records = []
        f = self.__getFileObj(self.dbf)
        f.seek(self.__dbfHdrLength)
        fieldTuples, recLookup, recStruct = self.__recordFields(fields)
        # self.__dbfHeader() sets self.numRecords, so it's fine to cast it to int
        # (to tell mypy it's not None).
        for i in range(cast(int, self.numRecords)):
            r = self.__record(
                oid=i, fieldTuples=fieldTuples, recLookup=recLookup, recStruct=recStruct
            )
            if r:
                records.append(r)
        return records

    def iterRecords(
        self,
        fields: list[str] | None = None,
        start: int = 0,
        stop: int | None = None,
    ) -> Iterator[_Record | None]:
        """Returns a generator of records in a dbf file.
        Useful for large shapefiles or dbf files.
        To only read some of the fields, specify the 'fields' arg as a
        list of one or more fieldnames.
        By default yields all records.  Otherwise, specify start
        (default: 0) or stop (default: number_of_records)
        to only yield record numbers i, where
        start <= i < stop, (or
        start <= i < number_of_records + stop
        if stop < 0).
        """
        if self.numRecords is None:
            self.__dbfHeader()
        if not isinstance(self.numRecords, int):
            raise ShapefileException(
                "Error when reading number of Records in dbf file header"
            )
        f = self.__getFileObj(self.dbf)
        start = self.__restrictIndex(start)
        if stop is None:
            stop = self.numRecords
        elif abs(stop) > self.numRecords:
            raise IndexError(
                f"abs(stop): {abs(stop)} exceeds number of records: {self.numRecords}."
            )
        elif stop < 0:
            stop = range(self.numRecords)[stop]
        recSize = self.__recordLength
        f.seek(self.__dbfHdrLength + (start * recSize))
        fieldTuples, recLookup, recStruct = self.__recordFields(fields)
        for i in range(start, stop):
            r = self.__record(
                oid=i, fieldTuples=fieldTuples, recLookup=recLookup, recStruct=recStruct
            )
            if r:
                yield r

    def shapeRecord(
        self,
        i: int = 0,
        fields: list[str] | None = None,
        bbox: BBox | None = None,
    ) -> ShapeRecord | None:
        """Returns a combination geometry and attribute record for the
        supplied record index.
        To only read some of the fields, specify the 'fields' arg as a
        list of one or more fieldnames.
        If the 'bbox' arg is given (list or tuple of xmin,ymin,xmax,ymax),
        returns None if the shape is not within that region.
        """
        i = self.__restrictIndex(i)
        shape = self.shape(i, bbox=bbox)
        if shape:
            record = self.record(i, fields=fields)
            return ShapeRecord(shape=shape, record=record)
        return None

    def shapeRecords(
        self,
        fields: list[str] | None = None,
        bbox: BBox | None = None,
    ) -> ShapeRecords:
        """Returns a list of combination geometry/attribute records for
        all records in a shapefile.
        To only read some of the fields, specify the 'fields' arg as a
        list of one or more fieldnames.
        To only read entries within a given spatial region, specify the 'bbox'
        arg as a list or tuple of xmin,ymin,xmax,ymax.
        """
        return ShapeRecords(self.iterShapeRecords(fields=fields, bbox=bbox))

    def iterShapeRecords(
        self,
        fields: list[str] | None = None,
        bbox: BBox | None = None,
    ) -> Iterator[ShapeRecord]:
        """Returns a generator of combination geometry/attribute records for
        all records in a shapefile.
        To only read some of the fields, specify the 'fields' arg as a
        list of one or more fieldnames.
        To only read entries within a given spatial region, specify the 'bbox'
        arg as a list or tuple of xmin,ymin,xmax,ymax.
        """
        if bbox is None:
            # iterate through all shapes and records
            for shape, record in zip(
                self.iterShapes(), self.iterRecords(fields=fields)
            ):
                yield ShapeRecord(shape=shape, record=record)
        else:
            # only iterate where shape.bbox overlaps with the given bbox
            # TODO: internal __record method should be faster but would have to
            # make sure to seek to correct file location...

            # fieldTuples,recLookup,recStruct = self.__recordFields(fields)
            for shape in self.iterShapes(bbox=bbox):
                if shape:
                    # record = self.__record(oid=i, fieldTuples=fieldTuples, recLookup=recLookup, recStruct=recStruct)
                    record = self.record(i=shape.oid, fields=fields)
                    yield ShapeRecord(shape=shape, record=record)
