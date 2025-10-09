from __future__ import annotations

import io
import os
import time
from datetime import date
from os import PathLike
from struct import error, pack
from types import TracebackType
from typing import (
    Any,
    Literal,
    NoReturn,
    TypeVar,
    Union,
    cast,
    overload,
)

from .classes import Field, RecordValue
from .constants import MISSING, NULL, SHAPETYPE_LOOKUP
from .exceptions import ShapefileException
from .geojson import GeoJSONHomogeneousGeometryObject, HasGeoInterface
from .helpers import fsdecode_if_pathlike
from .shapes import (
    SHAPE_CLASS_FROM_SHAPETYPE,
    SHAPETYPE_LOOKUP,
    MultiPatch,
    MultiPoint,
    MultiPointM,
    MultiPointZ,
    NullShape,
    Point,
    PointM,
    PointM_shapeTypes,
    PointZ,
    PointZ_shapeTypes,
    Polygon,
    PolygonM,
    PolygonZ,
    Polyline,
    PolylineM,
    PolylineZ,
    Shape,
    _CanHaveBBox_shapeTypes,
    _HasM,
    _HasM_shapeTypes,
    _HasZ,
    _HasZ_shapeTypes,
)
from .types import (
    BBox,
    BinaryFileStreamT,
    Field,
    FieldTypeT,
    MBox,
    PointsT,
    ReadWriteSeekableBinStream,
    WriteSeekableBinStream,
    ZBox,
)


class Writer:
    """Provides write support for ESRI Shapefiles."""

    W = TypeVar("W", bound=WriteSeekableBinStream)

    def __init__(
        self,
        target: str | PathLike[Any] | None = None,
        shapeType: int | None = None,
        autoBalance: bool = False,
        *,
        encoding: str = "utf-8",
        encodingErrors: str = "strict",
        shp: WriteSeekableBinStream | None = None,
        shx: WriteSeekableBinStream | None = None,
        dbf: WriteSeekableBinStream | None = None,
        # Keep kwargs even though unused, to preserve PyShp 2.4 API
        **kwargs: Any,
    ):
        self.target = target
        self.autoBalance = autoBalance
        self.fields: list[Field] = []
        self.shapeType = shapeType
        self.shp: WriteSeekableBinStream | None = None
        self.shx: WriteSeekableBinStream | None = None
        self.dbf: WriteSeekableBinStream | None = None
        self._files_to_close: list[BinaryFileStreamT] = []
        if target:
            target = fsdecode_if_pathlike(target)
            if not isinstance(target, str):
                raise TypeError(
                    f"The target filepath {target!r} must be of type str/unicode or path-like, not {type(target)}."
                )
            self.shp = self.__getFileObj(os.path.splitext(target)[0] + ".shp")
            self.shx = self.__getFileObj(os.path.splitext(target)[0] + ".shx")
            self.dbf = self.__getFileObj(os.path.splitext(target)[0] + ".dbf")
        elif shp or shx or dbf:
            if shp:
                self.shp = self.__getFileObj(shp)
            if shx:
                self.shx = self.__getFileObj(shx)
            if dbf:
                self.dbf = self.__getFileObj(dbf)
        else:
            raise TypeError(
                "Either the target filepath, or any of shp, shx, or dbf must be set to create a shapefile."
            )
        # Initiate with empty headers, to be finalized upon closing
        if self.shp:
            self.shp.write(b"9" * 100)
        if self.shx:
            self.shx.write(b"9" * 100)
        # Geometry record offsets and lengths for writing shx file.
        self.recNum = 0
        self.shpNum = 0
        self._bbox: BBox | None = None
        self._zbox: ZBox | None = None
        self._mbox: MBox | None = None
        # Use deletion flags in dbf? Default is false (0). Note: Currently has no effect, records should NOT contain deletion flags.
        self.deletionFlag = 0
        # Encoding
        self.encoding = encoding
        self.encodingErrors = encodingErrors

    def __len__(self) -> int:
        """Returns the current number of features written to the shapefile.
        If shapes and records are unbalanced, the length is considered the highest
        of the two."""
        return max(self.recNum, self.shpNum)

    def __enter__(self) -> Writer:
        """
        Enter phase of context manager.
        """
        return self

    def __exit__(
        self,
        exc_type: BaseException | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """
        Exit phase of context manager, finish writing and close the files.
        """
        self.close()
        return None

    def __del__(self) -> None:
        self.close()

    def close(self) -> None:
        """
        Write final shp, shx, and dbf headers, close opened files.
        """
        # Check if any of the files have already been closed
        shp_open = self.shp and not (hasattr(self.shp, "closed") and self.shp.closed)
        shx_open = self.shx and not (hasattr(self.shx, "closed") and self.shx.closed)
        dbf_open = self.dbf and not (hasattr(self.dbf, "closed") and self.dbf.closed)

        # Balance if already not balanced
        if self.shp and shp_open and self.dbf and dbf_open:
            if self.autoBalance:
                self.balance()
            if self.recNum != self.shpNum:
                raise ShapefileException(
                    "When saving both the dbf and shp file, "
                    f"the number of records ({self.recNum}) must correspond "
                    f"with the number of shapes ({self.shpNum})"
                )
        # Fill in the blank headers
        if self.shp and shp_open:
            self.__shapefileHeader(self.shp, headerType="shp")
        if self.shx and shx_open:
            self.__shapefileHeader(self.shx, headerType="shx")

        # Update the dbf header with final length etc
        if self.dbf and dbf_open:
            self.__dbfHeader()

        # Flush files
        for attribute in (self.shp, self.shx, self.dbf):
            if attribute is None:
                continue
            if hasattr(attribute, "flush") and not getattr(attribute, "closed", False):
                try:
                    attribute.flush()
                except OSError:
                    pass

        # Close any files that the writer opened (but not those given by user)
        for attribute in self._files_to_close:
            if hasattr(attribute, "close"):
                try:
                    attribute.close()
                except OSError:
                    pass
        self._files_to_close = []

    @overload
    def __getFileObj(self, f: str) -> WriteSeekableBinStream: ...
    @overload
    def __getFileObj(self, f: None) -> NoReturn: ...
    @overload
    def __getFileObj(self, f: WriteSeekableBinStream) -> WriteSeekableBinStream: ...
    def __getFileObj(
        self, f: str | None | WriteSeekableBinStream
    ) -> WriteSeekableBinStream:
        """Safety handler to verify file-like objects"""
        if not f:
            raise ShapefileException("No file-like object available.")
        if isinstance(f, str):
            pth = os.path.split(f)[0]
            if pth and not os.path.exists(pth):
                os.makedirs(pth)
            fp = open(f, "wb+")
            self._files_to_close.append(fp)
            return fp

        if hasattr(f, "write"):
            return f
        raise ShapefileException(f"Unsupported file-like object: {f}")

    def __shpFileLength(self) -> int:
        """Calculates the file length of the shp file."""
        shp = self.__getFileObj(self.shp)

        # Remember starting position

        start = shp.tell()
        # Calculate size of all shapes
        shp.seek(0, 2)
        size = shp.tell()
        # Calculate size as 16-bit words
        size //= 2
        # Return to start
        shp.seek(start)
        return size

    def _update_file_bbox(self, s: Shape) -> None:
        if s.shapeType == NULL:
            shape_bbox = None
        elif s.shapeType in _CanHaveBBox_shapeTypes:
            shape_bbox = s.bbox
        else:
            x, y = s.points[0][:2]
            shape_bbox = (x, y, x, y)

        if shape_bbox is None:
            return None

        if self._bbox:
            # compare with existing
            self._bbox = (
                min(shape_bbox[0], self._bbox[0]),
                min(shape_bbox[1], self._bbox[1]),
                max(shape_bbox[2], self._bbox[2]),
                max(shape_bbox[3], self._bbox[3]),
            )
        else:
            # first time bbox is being set
            self._bbox = shape_bbox
        return None

    def _update_file_zbox(self, s: _HasZ | PointZ) -> None:
        if self._zbox:
            # compare with existing
            self._zbox = (min(s.zbox[0], self._zbox[0]), max(s.zbox[1], self._zbox[1]))
        else:
            # first time zbox is being set
            self._zbox = s.zbox

    def _update_file_mbox(self, s: _HasM | PointM) -> None:
        mbox = s.mbox
        if self._mbox:
            # compare with existing
            self._mbox = (min(mbox[0], self._mbox[0]), max(mbox[1], self._mbox[1]))
        else:
            # first time mbox is being set
            self._mbox = mbox

    @property
    def shapeTypeName(self) -> str:
        return SHAPETYPE_LOOKUP[self.shapeType or 0]

    def bbox(self) -> BBox | None:
        """Returns the current bounding box for the shapefile which is
        the lower-left and upper-right corners. It does not contain the
        elevation or measure extremes."""
        return self._bbox

    def zbox(self) -> ZBox | None:
        """Returns the current z extremes for the shapefile."""
        return self._zbox

    def mbox(self) -> MBox | None:
        """Returns the current m extremes for the shapefile."""
        return self._mbox

    def __shapefileHeader(
        self,
        fileObj: WriteSeekableBinStream | None,
        headerType: Literal["shp", "dbf", "shx"] = "shp",
    ) -> None:
        """Writes the specified header type to the specified file-like object.
        Several of the shapefile formats are so similar that a single generic
        method to read or write them is warranted."""

        f = self.__getFileObj(fileObj)
        f.seek(0)
        # File code, Unused bytes
        f.write(pack(">6i", 9994, 0, 0, 0, 0, 0))
        # File length (Bytes / 2 = 16-bit words)
        if headerType == "shp":
            f.write(pack(">i", self.__shpFileLength()))
        elif headerType == "shx":
            f.write(pack(">i", ((100 + (self.shpNum * 8)) // 2)))
        # Version, Shape type
        if self.shapeType is None:
            self.shapeType = NULL
        f.write(pack("<2i", 1000, self.shapeType))
        # The shapefile's bounding box (lower left, upper right)
        if self.shapeType != 0:
            try:
                bbox = self.bbox()
                if bbox is None:
                    # The bbox is initialized with None, so this would mean the shapefile contains no valid geometries.
                    # In such cases of empty shapefiles, ESRI spec says the bbox values are 'unspecified'.
                    # Not sure what that means, so for now just setting to 0s, which is the same behavior as in previous versions.
                    # This would also make sense since the Z and M bounds are similarly set to 0 for non-Z/M type shapefiles.
                    # bbox = BBox(0, 0, 0, 0)
                    bbox = (0, 0, 0, 0)
                f.write(pack("<4d", *bbox))
            except error:
                raise ShapefileException(
                    "Failed to write shapefile bounding box. Floats required."
                )
        else:
            f.write(pack("<4d", 0, 0, 0, 0))
        # Elevation
        if self.shapeType in PointZ_shapeTypes | _HasZ_shapeTypes:
            # Z values are present in Z type
            zbox = self.zbox()
            if zbox is None:
                # means we have empty shapefile/only null geoms (see commentary on bbox above)
                # zbox = ZBox(0, 0)
                zbox = (0, 0)
        else:
            # As per the ESRI shapefile spec, the zbox for non-Z type shapefiles are set to 0s
            # zbox = ZBox(0, 0)
            zbox = (0, 0)
        # Measure
        if self.shapeType in PointM_shapeTypes | _HasM_shapeTypes:
            # M values are present in M or Z type
            mbox = self.mbox()
            if mbox is None:
                # means we have empty shapefile/only null geoms (see commentary on bbox above)
                # mbox = MBox(0, 0)
                mbox = (0, 0)
        else:
            # As per the ESRI shapefile spec, the mbox for non-M type shapefiles are set to 0s
            # mbox = MBox(0, 0)
            mbox = (0, 0)
        # Try writing
        try:
            f.write(pack("<4d", zbox[0], zbox[1], mbox[0], mbox[1]))
        except error:
            raise ShapefileException(
                "Failed to write shapefile elevation and measure values. Floats required."
            )

    def __dbfHeader(self) -> None:
        """Writes the dbf header and field descriptors."""
        f = self.__getFileObj(self.dbf)
        f.seek(0)
        version = 3
        year, month, day = time.localtime()[:3]
        year -= 1900
        # Get all fields, ignoring DeletionFlag if specified
        fields = [field for field in self.fields if field[0] != "DeletionFlag"]
        # Ensure has at least one field
        if not fields:
            raise ShapefileException(
                "Shapefile dbf file must contain at least one field."
            )
        numRecs = self.recNum
        numFields = len(fields)
        headerLength = numFields * 32 + 33
        if headerLength >= 65535:
            raise ShapefileException(
                "Shapefile dbf header length exceeds maximum length."
            )
        recordLength = sum(field.size for field in fields) + 1
        header = pack(
            "<BBBBLHH20x",
            version,
            year,
            month,
            day,
            numRecs,
            headerLength,
            recordLength,
        )
        f.write(header)
        # Field descriptors
        for field in fields:
            encoded_name = field.name.encode(self.encoding, self.encodingErrors)
            encoded_name = encoded_name.replace(b" ", b"_")
            encoded_name = encoded_name[:10].ljust(11).replace(b" ", b"\x00")
            encodedFieldType = field.field_type.encode("ascii")
            fld = pack(
                "<11sc4xBB14x",
                encoded_name,
                encodedFieldType,
                field.size,
                field.decimal,
            )
            f.write(fld)
        # Terminator
        f.write(b"\r")

    def shape(
        self,
        s: Shape | HasGeoInterface | GeoJSONHomogeneousGeometryObject,
    ) -> None:
        # Balance if already not balanced
        if self.autoBalance and self.recNum < self.shpNum:
            self.balance()
        # Check is shape or import from geojson
        if not isinstance(s, Shape):
            if hasattr(s, "__geo_interface__"):
                s = cast(HasGeoInterface, s)
                shape_dict = s.__geo_interface__
            elif isinstance(s, dict):  # TypedDict is a dict at runtime
                shape_dict = s
            else:
                raise TypeError(
                    "Can only write Shape objects, GeoJSON dictionaries, "
                    "or objects with the __geo_interface__, "
                    f"not: {s}"
                )
            s = Shape._from_geojson(shape_dict)
        # Write to file
        offset, length = self.__shpRecord(s)
        if self.shx:
            self.__shxRecord(offset, length)

    def __shpRecord(self, s: Shape) -> tuple[int, int]:
        f: WriteSeekableBinStream = self.__getFileObj(self.shp)
        offset = f.tell()
        self.shpNum += 1

        # Shape Type
        if self.shapeType is None and s.shapeType != NULL:
            self.shapeType = s.shapeType
        if s.shapeType not in (NULL, self.shapeType):
            raise ShapefileException(
                f"The shape's type ({s.shapeType}) must match "
                f"the type of the shapefile ({self.shapeType})."
            )

        # For both single point and multiple-points non-null shapes,
        # update bbox, mbox and zbox of the whole shapefile
        if s.shapeType != NULL:
            self._update_file_bbox(s)

        if s.shapeType in PointM_shapeTypes | _HasM_shapeTypes:
            self._update_file_mbox(cast(Union[_HasM, PointM], s))

        if s.shapeType in PointZ_shapeTypes | _HasZ_shapeTypes:
            self._update_file_zbox(cast(Union[_HasZ, PointZ], s))

        # Create an in-memory binary buffer to avoid
        # unnecessary seeks to files on disk
        # (other ops are already buffered until .seek
        # or .flush is called if not using RawIOBase).
        # https://docs.python.org/3/library/io.html#id2
        # https://docs.python.org/3/library/io.html#io.BufferedWriter
        b_io: ReadWriteSeekableBinStream = io.BytesIO()

        # Record number, Content length place holder
        b_io.write(pack(">2i", self.shpNum, -1))

        # Track number of content bytes written, excluding
        # self.shpNum and length (t.b.c.)
        n = 0

        n += b_io.write(pack("<i", s.shapeType))

        ShapeClass = SHAPE_CLASS_FROM_SHAPETYPE[s.shapeType]
        n += ShapeClass.write_to_byte_stream(
            b_io=b_io,
            s=s,
            i=self.shpNum,
        )

        # Finalize record length as 16-bit words
        length = n // 2

        # 4 bytes in is the content length field
        b_io.seek(4)
        b_io.write(pack(">i", length))

        # Flush to file.
        b_io.seek(0)
        f.write(b_io.read())
        return offset, length

    def __shxRecord(self, offset: int, length: int) -> None:
        """Writes the shx records."""

        f = self.__getFileObj(self.shx)
        try:
            f.write(pack(">i", offset // 2))
        except error:
            raise ShapefileException(
                "The .shp file has reached its file size limit > 4294967294 bytes (4.29 GB). To fix this, break up your file into multiple smaller ones."
            )
        f.write(pack(">i", length))

    def record(
        self,
        *recordList: RecordValue,
        **recordDict: RecordValue,
    ) -> None:
        """Creates a dbf attribute record. You can submit either a sequence of
        field values or keyword arguments of field names and values. Before
        adding records you must add fields for the record values using the
        field() method. If the record values exceed the number of fields the
        extra ones won't be added. In the case of using keyword arguments to specify
        field/value pairs only fields matching the already registered fields
        will be added."""
        # Balance if already not balanced
        if self.autoBalance and self.recNum > self.shpNum:
            self.balance()
        record: list[RecordValue]
        fieldCount = sum(1 for field in self.fields if field[0] != "DeletionFlag")
        if recordList:
            record = list(recordList)
            while len(record) < fieldCount:
                record.append("")
        elif recordDict:
            record = []
            for field in self.fields:
                if field[0] == "DeletionFlag":
                    continue  # ignore deletionflag field in case it was specified
                if field[0] in recordDict:
                    val = recordDict[field[0]]
                    if val is None:
                        record.append("")
                    else:
                        record.append(val)
                else:
                    record.append("")  # need empty value for missing dict entries
        else:
            # Blank fields for empty record
            record = ["" for _ in range(fieldCount)]
        self.__dbfRecord(record)

    def __dbfRecord(self, record: list[RecordValue]) -> None:
        """Writes the dbf records."""
        f = self.__getFileObj(self.dbf)
        if self.recNum == 0:
            # first records, so all fields should be set
            # allowing us to write the dbf header
            # cannot change the fields after this point
            self.__dbfHeader()
        # first byte of the record is deletion flag, always disabled
        f.write(b" ")
        # begin
        self.recNum += 1
        fields = (
            field for field in self.fields if field[0] != "DeletionFlag"
        )  # ignore deletionflag field in case it was specified
        for (fieldName, fieldType, size, deci), value in zip(fields, record):
            # write
            # fieldName, fieldType, size and deci were already checked
            # when their Field instance was created and added to self.fields
            str_val: str | None = None

            if fieldType in ("N", "F"):
                # numeric or float: number stored as a string, right justified, and padded with blanks to the width of the field.
                if value in MISSING:
                    str_val = "*" * size  # QGIS NULL
                elif not deci:
                    # force to int
                    try:
                        # first try to force directly to int.
                        # forcing a large int to float and back to int
                        # will lose information and result in wrong nr.
                        num_val = int(cast(int, value))
                    except ValueError:
                        # forcing directly to int failed, so was probably a float.
                        num_val = int(float(cast(float, value)))
                    str_val = format(num_val, "d")[:size].rjust(
                        size
                    )  # caps the size if exceeds the field size
                else:
                    f_val = float(cast(float, value))
                    str_val = format(f_val, f".{deci}f")[:size].rjust(
                        size
                    )  # caps the size if exceeds the field size
            elif fieldType == "D":
                # date: 8 bytes - date stored as a string in the format YYYYMMDD.
                if isinstance(value, date):
                    str_val = f"{value.year:04d}{value.month:02d}{value.day:02d}"
                elif isinstance(value, list) and len(value) == 3:
                    str_val = f"{value[0]:04d}{value[1]:02d}{value[2]:02d}"
                elif value in MISSING:
                    str_val = "0" * 8  # QGIS NULL for date type
                elif isinstance(value, str) and len(value) == 8:
                    pass  # value is already a date string
                else:
                    raise ShapefileException(
                        "Date values must be either a datetime.date object, a list, a YYYYMMDD string, or a missing value."
                    )
            elif fieldType == "L":
                # logical: 1 byte - initialized to 0x20 (space) otherwise T or F.
                if value in MISSING:
                    str_val = " "  # missing is set to space
                elif value in [True, 1]:
                    str_val = "T"
                elif value in [False, 0]:
                    str_val = "F"
                else:
                    str_val = " "  # unknown is set to space

            if str_val is None:
                # Types C and M, and anything else, value is forced to string,
                # encoded by the codec specified to the Writer (utf-8 by default),
                # then the resulting bytes are padded and truncated to the length
                # of the field
                encoded = (
                    str(value)
                    .encode(self.encoding, self.encodingErrors)[:size]
                    .ljust(size)
                )
            else:
                # str_val was given a not-None string value
                # under the checks for fieldTypes "N", "F", "D", or "L" above
                # Numeric, logical, and date numeric types are ascii already, but
                # for Shapefile or dbf spec reasons
                # "should be default ascii encoding"
                encoded = str_val.encode("ascii", self.encodingErrors)

            if len(encoded) != size:
                raise ShapefileException(
                    f"Shapefile Writer unable to pack incorrect sized {value=}"
                    f" (encoded as {len(encoded)}B) into field '{fieldName}' ({size}B)."
                )
            f.write(encoded)

    def balance(self) -> None:
        """Adds corresponding empty attributes or null geometry records depending
        on which type of record was created to make sure all three files
        are in synch."""
        while self.recNum > self.shpNum:
            self.null()
        while self.recNum < self.shpNum:
            self.record()

    def null(self) -> None:
        """Creates a null shape."""
        self.shape(NullShape())

    def point(self, x: float, y: float) -> None:
        """Creates a POINT shape."""
        pointShape = Point(x, y)
        self.shape(pointShape)

    def pointm(self, x: float, y: float, m: float | None = None) -> None:
        """Creates a POINTM shape.
        If the m (measure) value is not set, it defaults to NoData."""
        pointShape = PointM(x, y, m)
        self.shape(pointShape)

    def pointz(
        self, x: float, y: float, z: float = 0.0, m: float | None = None
    ) -> None:
        """Creates a POINTZ shape.
        If the z (elevation) value is not set, it defaults to 0.
        If the m (measure) value is not set, it defaults to NoData."""
        pointShape = PointZ(x, y, z, m)
        self.shape(pointShape)

    def multipoint(self, points: PointsT) -> None:
        """Creates a MULTIPOINT shape.
        Points is a list of xy values."""
        # nest the points inside a list to be compatible with the generic shapeparts method
        shape = MultiPoint(points=points)
        self.shape(shape)

    def multipointm(self, points: PointsT) -> None:
        """Creates a MULTIPOINTM shape.
        Points is a list of xym values.
        If the m (measure) value is not included, it defaults to None (NoData)."""
        # nest the points inside a list to be compatible with the generic shapeparts method
        shape = MultiPointM(points=points)
        self.shape(shape)

    def multipointz(self, points: PointsT) -> None:
        """Creates a MULTIPOINTZ shape.
        Points is a list of xyzm values.
        If the z (elevation) value is not included, it defaults to 0.
        If the m (measure) value is not included, it defaults to None (NoData)."""
        # nest the points inside a list to be compatible with the generic shapeparts method
        shape = MultiPointZ(points=points)
        self.shape(shape)

    def line(self, lines: list[PointsT]) -> None:
        """Creates a POLYLINE shape.
        Lines is a collection of lines, each made up of a list of xy values."""
        shape = Polyline(lines=lines)
        self.shape(shape)

    def linem(self, lines: list[PointsT]) -> None:
        """Creates a POLYLINEM shape.
        Lines is a collection of lines, each made up of a list of xym values.
        If the m (measure) value is not included, it defaults to None (NoData)."""
        shape = PolylineM(lines=lines)
        self.shape(shape)

    def linez(self, lines: list[PointsT]) -> None:
        """Creates a POLYLINEZ shape.
        Lines is a collection of lines, each made up of a list of xyzm values.
        If the z (elevation) value is not included, it defaults to 0.
        If the m (measure) value is not included, it defaults to None (NoData)."""
        shape = PolylineZ(lines=lines)
        self.shape(shape)

    def poly(self, polys: list[PointsT]) -> None:
        """Creates a POLYGON shape.
        Polys is a collection of polygons, each made up of a list of xy values.
        Note that for ordinary polygons the coordinates must run in a clockwise direction.
        If some of the polygons are holes, these must run in a counterclockwise direction."""
        shape = Polygon(lines=polys)
        self.shape(shape)

    def polym(self, polys: list[PointsT]) -> None:
        """Creates a POLYGONM shape.
        Polys is a collection of polygons, each made up of a list of xym values.
        Note that for ordinary polygons the coordinates must run in a clockwise direction.
        If some of the polygons are holes, these must run in a counterclockwise direction.
        If the m (measure) value is not included, it defaults to None (NoData)."""
        shape = PolygonM(lines=polys)
        self.shape(shape)

    def polyz(self, polys: list[PointsT]) -> None:
        """Creates a POLYGONZ shape.
        Polys is a collection of polygons, each made up of a list of xyzm values.
        Note that for ordinary polygons the coordinates must run in a clockwise direction.
        If some of the polygons are holes, these must run in a counterclockwise direction.
        If the z (elevation) value is not included, it defaults to 0.
        If the m (measure) value is not included, it defaults to None (NoData)."""
        shape = PolygonZ(lines=polys)
        self.shape(shape)

    def multipatch(self, parts: list[PointsT], partTypes: list[int]) -> None:
        """Creates a MULTIPATCH shape.
        Parts is a collection of 3D surface patches, each made up of a list of xyzm values.
        PartTypes is a list of types that define each of the surface patches.
        The types can be any of the following module constants: TRIANGLE_STRIP,
        TRIANGLE_FAN, OUTER_RING, INNER_RING, FIRST_RING, or RING.
        If the z (elevation) value is not included, it defaults to 0.
        If the m (measure) value is not included, it defaults to None (NoData)."""
        shape = MultiPatch(lines=parts, partTypes=partTypes)
        self.shape(shape)

    def field(
        # Types of args should match *Field
        self,
        name: str,
        field_type: FieldTypeT = "C",
        size: int = 50,
        decimal: int = 0,
    ) -> None:
        """Adds a dbf field descriptor to the shapefile."""
        if len(self.fields) >= 2046:
            raise ShapefileException(
                "Shapefile Writer reached maximum number of fields: 2046."
            )
        field_ = Field.from_unchecked(name, field_type, size, decimal)
        self.fields.append(field_)