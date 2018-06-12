"""
shapefile.py
Provides read and write support for ESRI Shapefiles.
author: jlawhead<at>geospatialpython.com
date: 2017/04/29
version: 2.0.0-dev
Compatible with Python versions 2.7-3.x
"""

__version__ = "2.0.0-dev"

from struct import pack, unpack, calcsize, error, Struct
import os
import sys
import time
import array
import tempfile
import warnings
import io
from datetime import date


# Constants for shape types
SHAPE_TYPES = {
    0: 'NULL',
    1: 'POINT',
    3: 'POLYLINE',
    5: 'POLYGON',
    8: 'MULTIPOINT',
    11: 'POINTZ',
    13: 'POLYLINEZ',
    15: 'POLYGONZ',
    18: 'MULTIPOINTZ',
    21: 'POINTM',
    23: 'POLYLINEM',
    25: 'POLYGONM',
    28: 'MULTIPOINTM',
    31: 'MULTIPATCH'}
# add inverse mapping and insert all into globals
_thismodule = sys.modules[__name__]
for num, name in list(SHAPE_TYPES.items()):
    setattr(_thismodule, name, num)
    if name in SHAPE_TYPES:
        # this is a conflict in shapetype names and should not happen
        raise Exception()
    SHAPE_TYPES[name] = num


# Python 2-3 handling

PYTHON3 = sys.version_info[0] == 3

if PYTHON3:
    xrange = range
    izip = zip
else:
    from itertools import izip


# Helpers

MISSING = [None,'']
NODATA = -10e38 # as per the ESRI shapefile spec, only used for m-values. 

if PYTHON3:
    def b(v, encoding='utf-8', encodingErrors='strict'):
        if isinstance(v, str):
            # For python 3 encode str to bytes.
            return v.encode(encoding, encodingErrors)
        elif isinstance(v, bytes):
            # Already bytes.
            return v
        else:
            # Error.
            raise Exception('Unknown input type')

    def u(v, encoding='utf-8', encodingErrors='strict'):
        if isinstance(v, bytes):
            # For python 3 decode bytes to str.
            return v.decode(encoding, encodingErrors)
        elif isinstance(v, str):
            # Already str.
            return v
        else:
            # Error.
            raise Exception('Unknown input type')

    def is_string(v):
        return isinstance(v, str)

else:
    def b(v, encoding='utf-8', encodingErrors='strict'):
        if isinstance(v, unicode):
            # For python 2 encode unicode to bytes.
            return v.encode(encoding, encodingErrors)
        elif isinstance(v, bytes):
            # Already bytes.
            return v
        else:
            # Error.
            raise Exception('Unknown input type')

    def u(v, encoding='utf-8', encodingErrors='strict'):
        if isinstance(v, bytes):
            # For python 2 decode bytes to unicode.
            return v.decode(encoding, encodingErrors)
        elif isinstance(v, unicode):
            # Already unicode.
            return v
        else:
            # Error.
            raise Exception('Unknown input type')

    def is_string(v):
        return isinstance(v, basestring)


# Begin

class _Array(array.array):
    """Converts python tuples to lits of the appropritate type.
    Used to unpack different shapefile header parts."""
    def __repr__(self):
        return str(self.tolist())

def signed_area(coords):
    """Return the signed area enclosed by a ring using the linear time
    algorithm. A value >= 0 indicates a counter-clockwise oriented ring.
    """
    xs, ys = map(list, zip(*coords))
    xs.append(xs[1])
    ys.append(ys[1])
    return sum(xs[i]*(ys[i+1]-ys[i-1]) for i in range(1, len(coords)))/2.0

def geojson_to_shape(geoj):
    # create empty shape
    shape = Shape()
    # set shapeType
    geojType = geoj["type"] if geoj else "Null"
    if geojType == "Null":
        shapeType = NULL
    elif geojType == "Point":
        shapeType = POINT
    elif geojType == "LineString":
        shapeType = POLYLINE
    elif geojType == "Polygon":
        shapeType = POLYGON
    elif geojType == "MultiPoint":
        shapeType = MULTIPOINT
    elif geojType == "MultiLineString":
        shapeType = POLYLINE
    elif geojType == "MultiPolygon":
        shapeType = POLYGON
    else:
        raise Exception("Cannot create Shape from GeoJSON type '%s'" % geojType)
    shape.shapeType = shapeType
    
    # set points and parts
    if geojType == "Point":
        shape.points = [ geoj["coordinates"] ]
        shape.parts = [0]
    elif geojType in ("MultiPoint","LineString"):
        shape.points = geoj["coordinates"]
        shape.parts = [0]
    elif geojType in ("Polygon"):
        points = []
        parts = []
        index = 0
        for ext_or_hole in geoj["coordinates"]:
            points.extend(ext_or_hole)
            parts.append(index)
            index += len(ext_or_hole)
        shape.points = points
        shape.parts = parts
    elif geojType in ("MultiLineString"):
        points = []
        parts = []
        index = 0
        for linestring in geoj["coordinates"]:
            points.extend(linestring)
            parts.append(index)
            index += len(linestring)
        shape.points = points
        shape.parts = parts
    elif geojType in ("MultiPolygon"):
        points = []
        parts = []
        index = 0
        for polygon in geoj["coordinates"]:
            for ext_or_hole in polygon:
                points.extend(ext_or_hole)
                parts.append(index)
                index += len(ext_or_hole)
        shape.points = points
        shape.parts = parts
    return shape

class Shape(object):
    def __init__(self, shapeType=NULL, points=None, parts=None, partTypes=None):
        """Stores the geometry of the different shape types
        specified in the Shapefile spec. Shape types are
        usually point, polyline, or polygons. Every shape type
        except the "Null" type contains points at some level for
        example verticies in a polygon. If a shape type has
        multiple shapes containing points within a single
        geometry record then those shapes are called parts. Parts
        are designated by their starting index in geometry record's
        list of shapes. For MultiPatch geometry, partTypes designates
        the patch type of each of the parts. 
        """
        self.shapeType = shapeType
        self.points = points or []
        self.parts = parts or []
        if partTypes:
            self.partTypes = partTypes

    @property
    def __geo_interface__(self):
        if not self.parts or not self.points:
            Exception('Invalid shape, cannot create GeoJSON representation. Shape type is "%s" but does not contain any parts and/or points.' % self.shapeType)

        if self.shapeType in [POINT, POINTM, POINTZ]:
            return {
            'type': 'Point',
            'coordinates': tuple(self.points[0])
            }
        elif self.shapeType in [MULTIPOINT, MULTIPOINTM, MULTIPOINTZ]:
            return {
            'type': 'MultiPoint',
            'coordinates': tuple([tuple(p) for p in self.points])
            }
        elif self.shapeType in [POLYLINE, POLYLINEM, POLYLINEZ]:
            if len(self.parts) == 1:
                return {
                'type': 'LineString',
                'coordinates': tuple([tuple(p) for p in self.points])
                }
            else:
                ps = None
                coordinates = []
                for part in self.parts:
                    if ps == None:
                        ps = part
                        continue
                    else:
                        coordinates.append(tuple([tuple(p) for p in self.points[ps:part]]))
                        ps = part
                else:
                    coordinates.append(tuple([tuple(p) for p in self.points[part:]]))
                return {
                'type': 'MultiLineString',
                'coordinates': tuple(coordinates)
                }
        elif self.shapeType in [POLYGON, POLYGONM, POLYGONZ]:
            if len(self.parts) == 1:
                return {
                'type': 'Polygon',
                'coordinates': (tuple([tuple(p) for p in self.points]),)
                }
            else:
                ps = None
                coordinates = []
                for part in self.parts:
                    if ps == None:
                        ps = part
                        continue
                    else:
                        coordinates.append(tuple([tuple(p) for p in self.points[ps:part]]))
                        ps = part
                else:
                    coordinates.append(tuple([tuple(p) for p in self.points[part:]]))
                polys = []
                poly = [coordinates[0]]
                for coord in coordinates[1:]:
                    if signed_area(coord) < 0:
                        polys.append(poly)
                        poly = [coord]
                    else:
                        poly.append(coord)
                polys.append(poly)
                if len(polys) == 1:
                    return {
                    'type': 'Polygon',
                    'coordinates': tuple(polys[0])
                    }
                elif len(polys) > 1:
                    return {
                    'type': 'MultiPolygon',
                    'coordinates': polys
                    }
        else:
            raise Exception('Shape type "%s" cannot be represented as GeoJSON.' % self.shapeType)

class ShapeRecord(object):
    """A ShapeRecord object containing a shape along with its attributes."""
    def __init__(self, shape=None, record=None):
        self.shape = shape
        self.record = record

class ShapefileException(Exception):
    """An exception to handle shapefile specific problems."""
    pass

class Reader(object):
    """Reads the three files of a shapefile as a unit or
    separately.  If one of the three files (.shp, .shx,
    .dbf) is missing no exception is thrown until you try
    to call a method that depends on that particular file.
    The .shx index file is used if available for efficiency
    but is not required to read the geometry from the .shp
    file. The "shapefile" argument in the constructor is the
    name of the file you want to open.

    You can instantiate a Reader without specifying a shapefile
    and then specify one later with the load() method.

    Only the shapefile headers are read upon loading. Content
    within each file is only accessed when required and as
    efficiently as possible. Shapefiles are usually not large
    but they can be.
    """
    def __init__(self, *args, **kwargs):
        self.shp = None
        self.shx = None
        self.dbf = None
        self.shapeName = "Not specified"
        self._offsets = []
        self.shpLength = None
        self.numRecords = None
        self.fields = []
        self.__dbfHdrLength = 0
        self.encoding = kwargs.pop('encoding', 'utf-8')
        self.encodingErrors = kwargs.pop('encodingErrors', 'strict')
        # See if a shapefile name was passed as an argument
        if len(args) > 0:
            if is_string(args[0]):
                self.load(args[0])
                return
        if "shp" in kwargs.keys():
            if hasattr(kwargs["shp"], "read"):
                self.shp = kwargs["shp"]
                # Copy if required
                try:
                    self.shp.seek(0)
                except (NameError, io.UnsupportedOperation):
                    self.shp = io.BytesIO(self.shp.read())
            if "shx" in kwargs.keys():
                if hasattr(kwargs["shx"], "read"):
                    self.shx = kwargs["shx"]
                    # Copy if required
                    try:
                        self.shx.seek(0)
                    except (NameError, io.UnsupportedOperation):
                        self.shx = io.BytesIO(self.shx.read())
        if "dbf" in kwargs.keys():
            if hasattr(kwargs["dbf"], "read"):
                self.dbf = kwargs["dbf"]
                # Copy if required
                try:
                    self.dbf.seek(0)
                except (NameError, io.UnsupportedOperation):
                    self.dbf = io.BytesIO(self.dbf.read())
        if self.shp or self.dbf:        
            self.load()
        else:
            raise ShapefileException("Shapefile Reader requires a shapefile or file-like object.")

    def __str__(self):
        """
        Use some general info on the shapefile as __str__
        """
        info = ['shapefile Reader']
        if self.shp:
            info.append("    {} shapes (type '{}')".format(
                len(self.shapes()), SHAPE_TYPES[self.shapeType]))
        if self.dbf:
            info.append('    {} records ({} fields)'.format(
                self.numRecords, len(self.fields)))
        return '\n'.join(info)

    def __enter__(self):
        """
        Enter phase of context manager.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit phase of context manager, close opened files.
        """
        self.close()

    def __len__(self):
        """Returns the number of shapes/records in the shapefile."""
        return self.numRecords

    def __iter__(self):
        """Iterates through the shapes/records in the shapefile."""
        for shaperec in self.iterShapeRecords():
            yield shaperec

    @property
    def __geo_interface__(self):
        fieldnames = [f[0] for f in self.fields]
        features = []
        for feat in self.iterShapeRecords():
            fdict = {'type': 'Feature',
                     'properties': dict(*zip(fieldnames,
                                             list(feat.record)
                                             )),
                     'geometry': feat.shape.__geo_interface__}
            features.append(fdict)
        return {'type': 'FeatureCollection',
                'bbox': self.bbox,
                'features': features}        

    def load(self, shapefile=None):
        """Opens a shapefile from a filename or file-like
        object. Normally this method would be called by the
        constructor with the file name as an argument."""
        if shapefile:
            (shapeName, ext) = os.path.splitext(shapefile)
            self.shapeName = shapeName
            self.load_shp(shapeName)
            self.load_shx(shapeName)
            self.load_dbf(shapeName)
            if not (self.shp and self.dbf):
                raise ShapefileException("Unable to open %s.dbf or %s.shp." % (shapeName, shapeName))
        if self.shp:
            self.__shpHeader()
        if self.dbf:
            self.__dbfHeader()

    def load_shp(self, shapefile_name):
        """
        Attempts to load file with .shp extension as both lower and upper case
        """
        shp_ext = 'shp'
        try:
            self.shp = open("%s.%s" % (shapefile_name, shp_ext), "rb")
        except IOError:
            try:
                self.shp = open("%s.%s" % (shapefile_name, shp_ext.upper()), "rb")
            except IOError:
                pass

    def load_shx(self, shapefile_name):
        """
        Attempts to load file with .shx extension as both lower and upper case
        """
        shx_ext = 'shx'
        try:
            self.shx = open("%s.%s" % (shapefile_name, shx_ext), "rb")
        except IOError:
            try:
                self.shx = open("%s.%s" % (shapefile_name, shx_ext.upper()), "rb")
            except IOError:
                pass

    def load_dbf(self, shapefile_name):
        """
        Attempts to load file with .dbf extension as both lower and upper case
        """
        dbf_ext = 'dbf'
        try:
            self.dbf = open("%s.%s" % (shapefile_name, dbf_ext), "rb")
        except IOError:
            try:
                self.dbf = open("%s.%s" % (shapefile_name, dbf_ext.upper()), "rb")
            except IOError:
                pass

    def __del__(self):
        self.close()

    def close(self):
        for attribute in (self.shp, self.shx, self.dbf):
            if hasattr(attribute, 'close'):
                try:
                    attribute.close()
                except IOError:
                    pass

    def __getFileObj(self, f):
        """Checks to see if the requested shapefile file object is
        available. If not a ShapefileException is raised."""
        if not f:
            raise ShapefileException("Shapefile Reader requires a shapefile or file-like object.")
        if self.shp and self.shpLength is None:
            self.load()
        if self.dbf and len(self.fields) == 0:
            self.load()
        return f

    def __restrictIndex(self, i):
        """Provides list-like handling of a record index with a clearer
        error message if the index is out of bounds."""
        if self.numRecords:
            rmax = self.numRecords - 1
            if abs(i) > rmax:
                raise IndexError("Shape or Record index out of range.")
            if i < 0: i = range(self.numRecords)[i]
        return i

    def __shpHeader(self):
        """Reads the header information from a .shp or .shx file."""
        if not self.shp:
            raise ShapefileException("Shapefile Reader requires a shapefile or file-like object. (no shp file found")
        shp = self.shp
        # File length (16-bit word * 2 = bytes)
        shp.seek(24)
        self.shpLength = unpack(">i", shp.read(4))[0] * 2
        # Shape type
        shp.seek(32)
        self.shapeType= unpack("<i", shp.read(4))[0]
        # The shapefile's bounding box (lower left, upper right)
        self.bbox = _Array('d', unpack("<4d", shp.read(32)))
        # Elevation
        self.elevation = _Array('d', unpack("<2d", shp.read(16)))
        # Measure
        self.measure = []
        for m in _Array('d', unpack("<2d", shp.read(16))):
            # Measure values less than -10e38 are nodata values according to the spec
            if m > NODATA:
                self.measure.append(m)
            else:
                self.measure.append(None)

    def __shape(self):
        """Returns the header info and geometry for a single shape."""
        f = self.__getFileObj(self.shp)
        record = Shape()
        nParts = nPoints = zmin = zmax = mmin = mmax = None
        (recNum, recLength) = unpack(">2i", f.read(8))
        # Determine the start of the next record
        next = f.tell() + (2 * recLength)
        shapeType = unpack("<i", f.read(4))[0]
        record.shapeType = shapeType
        # For Null shapes create an empty points list for consistency
        if shapeType == 0:
            record.points = []
        # All shape types capable of having a bounding box
        elif shapeType in (3,5,8,13,15,18,23,25,28,31):
            record.bbox = _Array('d', unpack("<4d", f.read(32)))
        # Shape types with parts
        if shapeType in (3,5,13,15,23,25,31):
            nParts = unpack("<i", f.read(4))[0]
        # Shape types with points
        if shapeType in (3,5,8,13,15,18,23,25,28,31):
            nPoints = unpack("<i", f.read(4))[0]
        # Read parts
        if nParts:
            record.parts = _Array('i', unpack("<%si" % nParts, f.read(nParts * 4)))
        # Read part types for Multipatch - 31
        if shapeType == 31:
            record.partTypes = _Array('i', unpack("<%si" % nParts, f.read(nParts * 4)))
        # Read points - produces a list of [x,y] values
        if nPoints:
            flat = unpack("<%sd" % (2 * nPoints), f.read(16*nPoints))
            record.points = list(izip(*(iter(flat),) * 2))
        # Read z extremes and values
        if shapeType in (13,15,18,31):
            (zmin, zmax) = unpack("<2d", f.read(16))
            record.z = _Array('d', unpack("<%sd" % nPoints, f.read(nPoints * 8)))
        # Read m extremes and values
        if shapeType in (13,15,18,23,25,28,31):
            (mmin, mmax) = unpack("<2d", f.read(16))
            # Measure values less than -10e38 are nodata values according to the spec
            record.m = []
            for m in _Array('d', unpack("<%sd" % nPoints, f.read(nPoints * 8))):
                if m > NODATA:
                    record.m.append(m)
                else:
                    record.m.append(None)
        # Read a single point
        if shapeType in (1,11,21):
            record.points = [_Array('d', unpack("<2d", f.read(16)))]
        # Read a single Z value
        if shapeType == 11:
            record.z = list(unpack("<d", f.read(8)))
        # Read a single M value
        if shapeType == 21 or (shapeType == 11 and f.tell() < next):
            (m,) = unpack("<d", f.read(8))
            # Measure values less than -10e38 are nodata values according to the spec
            if m > NODATA:
                record.m = [m]
            else:
                record.m = [None]
        # Seek to the end of this record as defined by the record header because
        # the shapefile spec doesn't require the actual content to meet the header
        # definition.  Probably allowed for lazy feature deletion. 
        f.seek(next)
        return record

    def __shapeIndex(self, i=None):
        """Returns the offset in a .shp file for a shape based on information
        in the .shx index file."""
        shx = self.shx
        if not shx:
            return None
        if not self._offsets:
            # File length (16-bit word * 2 = bytes) - header length
            shx.seek(24)
            shxRecordLength = (unpack(">i", shx.read(4))[0] * 2) - 100
            numRecords = shxRecordLength // 8
            # Jump to the first record.
            shx.seek(100)
            shxRecords = _Array('i')
            # Each offset consists of two nrs, only the first one matters
            shxRecords.fromfile(shx, 2 * numRecords)
            if sys.byteorder != 'big':
                 shxRecords.byteswap()
            self._offsets = [2 * el for el in shxRecords[::2]]
        if not i == None:
            return self._offsets[i]

    def shape(self, i=0):
        """Returns a shape object for a shape in the the geometry
        record file."""
        shp = self.__getFileObj(self.shp)
        i = self.__restrictIndex(i)
        offset = self.__shapeIndex(i)
        if not offset:
            # Shx index not available so iterate the full list.
            for j,k in enumerate(self.iterShapes()):
                if j == i:
                    return k
        shp.seek(offset)
        return self.__shape()

    def shapes(self):
        """Returns all shapes in a shapefile."""
        shp = self.__getFileObj(self.shp)
        # Found shapefiles which report incorrect
        # shp file length in the header. Can't trust
        # that so we seek to the end of the file
        # and figure it out.
        shp.seek(0,2)
        self.shpLength = shp.tell()
        shp.seek(100)
        shapes = []
        while shp.tell() < self.shpLength:
            shapes.append(self.__shape())
        return shapes

    def iterShapes(self):
        """Serves up shapes in a shapefile as an iterator. Useful
        for handling large shapefiles."""
        shp = self.__getFileObj(self.shp)
        shp.seek(0,2)
        self.shpLength = shp.tell()
        shp.seek(100)
        while shp.tell() < self.shpLength:
            yield self.__shape()    

    def __dbfHeader(self):
        """Reads a dbf header. Xbase-related code borrows heavily from ActiveState Python Cookbook Recipe 362715 by Raymond Hettinger"""
        if not self.dbf:
            raise ShapefileException("Shapefile Reader requires a shapefile or file-like object. (no dbf file found)")
        dbf = self.dbf
        # read relevant header parts
        self.numRecords, self.__dbfHdrLength, self.__recordLength = \
                unpack("<xxxxLHH20x", dbf.read(32))
        # read fields
        numFields = (self.__dbfHdrLength - 33) // 32
        for field in range(numFields):
            fieldDesc = list(unpack("<11sc4xBB14x", dbf.read(32)))
            name = 0
            idx = 0
            if b"\x00" in fieldDesc[name]:
                idx = fieldDesc[name].index(b"\x00")
            else:
                idx = len(fieldDesc[name]) - 1
            fieldDesc[name] = fieldDesc[name][:idx]
            fieldDesc[name] = u(fieldDesc[name], "ascii")
            fieldDesc[name] = fieldDesc[name].lstrip()
            fieldDesc[1] = u(fieldDesc[1], "ascii")
            self.fields.append(fieldDesc)
        terminator = dbf.read(1)
        if terminator != b"\r":
            raise ShapefileException("Shapefile dbf header lacks expected terminator. (likely corrupt?)")
        self.fields.insert(0, ('DeletionFlag', 'C', 1, 0))
        fmt,fmtSize = self.__recordFmt()
        self.__recStruct = Struct(fmt)

    def __recordFmt(self):
        """Calculates the format and size of a .dbf record."""
        if self.numRecords is None:
            self.__dbfHeader()
        fmt = ''.join(['%ds' % fieldinfo[2] for fieldinfo in self.fields])
        fmtSize = calcsize(fmt)
        # total size of fields should add up to recordlength from the header
        while fmtSize < self.__recordLength:
            # if not, pad byte until reaches recordlength
            fmt += "x" 
            fmtSize += 1
        return (fmt, fmtSize)

    def __record(self):
        """Reads and returns a dbf record row as a list of values."""
        f = self.__getFileObj(self.dbf)
        recordContents = self.__recStruct.unpack(f.read(self.__recStruct.size))
        if recordContents[0] != b' ':
            # deleted record
            return None
        record = []
        for (name, typ, size, deci), value in zip(self.fields, recordContents):
            if name == 'DeletionFlag':
                continue
            elif typ in ("N","F"):
                # numeric or float: number stored as a string, right justified, and padded with blanks to the width of the field. 
                value = value.replace(b'\0', b'').strip()
                value = value.replace(b'*', b'')  # QGIS NULL is all '*' chars
                if value == b'':
                    value = None
                elif deci:
                    try:
                        value = float(value)
                    except ValueError:
                        #not parseable as float, set to None
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
                            #not parseable as int, set to None
                            value = None
            elif typ == 'D':
                # date: 8 bytes - date stored as a string in the format YYYYMMDD.
                if value.count(b'0') == len(value):  # QGIS NULL is all '0' chars
                    value = None
                else:
                    try:
                        y, m, d = int(value[:4]), int(value[4:6]), int(value[6:8])
                        value = date(y, m, d)
                    except:
                        value = value.strip()
            elif typ == 'L':
                # logical: 1 byte - initialized to 0x20 (space) otherwise T or F.
                if value == b" ":
                    value = None # space means missing or not yet set
                else:
                    if value in b'YyTt1':
                        value = True
                    elif value in b'NnFf0':
                        value = False
                    else:
                        value = None # unknown value is set to missing
            else:
                # anything else is forced to string/unicode
                value = u(value, self.encoding, self.encodingErrors)
                value = value.strip()
            record.append(value)
        return record

    def record(self, i=0):
        """Returns a specific dbf record based on the supplied index."""
        f = self.__getFileObj(self.dbf)
        if self.numRecords is None:
            self.__dbfHeader()
        i = self.__restrictIndex(i)
        recSize = self.__recStruct.size
        f.seek(0)
        f.seek(self.__dbfHdrLength + (i * recSize))
        return self.__record()

    def records(self):
        """Returns all records in a dbf file."""
        if self.numRecords is None:
            self.__dbfHeader()
        records = []
        f = self.__getFileObj(self.dbf)
        f.seek(self.__dbfHdrLength)
        for i in range(self.numRecords):
            r = self.__record()
            if r:
                records.append(r)
        return records

    def iterRecords(self):
        """Serves up records in a dbf file as an iterator.
        Useful for large shapefiles or dbf files."""
        if self.numRecords is None:
            self.__dbfHeader()
        f = self.__getFileObj(self.dbf)
        f.seek(self.__dbfHdrLength)
        for i in xrange(self.numRecords):
            r = self.__record()
            if r:
                yield r

    def shapeRecord(self, i=0):
        """Returns a combination geometry and attribute record for the
        supplied record index."""
        i = self.__restrictIndex(i)
        return ShapeRecord(shape=self.shape(i), record=self.record(i))

    def shapeRecords(self):
        """Returns a list of combination geometry/attribute records for
        all records in a shapefile."""
        shapeRecords = []
        return [ShapeRecord(shape=rec[0], record=rec[1]) \
                                for rec in zip(self.shapes(), self.records())]

    def iterShapeRecords(self):
        """Returns a generator of combination geometry/attribute records for
        all records in a shapefile."""
        for shape, record in izip(self.iterShapes(), self.iterRecords()):
            yield ShapeRecord(shape=shape, record=record)


class Writer(object):
    """Provides write support for ESRI Shapefiles."""
    def __init__(self, shapeType=None, autoBalance=False, bufsize=None, **kwargs):
        self.autoBalance = autoBalance
        self.fields = []
        self.shapeType = shapeType
        self.shp = None
        self.shx = None
        self.dbf = None
        # Create temporary files for immediate writing, minus the header
        self.bufsize = bufsize or 1056*1000*100 # default is 100 mb
        self._shp = tempfile.TemporaryFile()
        self._shx = tempfile.TemporaryFile()
        self._dbf = tempfile.TemporaryFile()
        # Geometry record offsets and lengths for writing shx file.
        self.recNum = 0
        self.shpNum = 0
        self._bbox = None
        self._zbox = None
        self._mbox = None
        # Use deletion flags in dbf? Default is false (0).
        self.deletionFlag = 0
        # Encoding
        self.encoding = kwargs.pop('encoding', 'utf-8')
        self.encodingErrors = kwargs.pop('encodingErrors', 'strict')

    def __len__(self):
        """Returns the current number of features written to the shapefile. 
        If shapes and records are unbalanced, the length is considered the highest
        of the two."""
        return max(self.recNum, self.shpNum) 

    def __getFileObj(self, f):
        """Safety handler to verify file-like objects"""
        if not f:
            raise ShapefileException("No file-like object available.")
        elif hasattr(f, "write"):
            return f
        else:
            pth = os.path.split(f)[0]
            if pth and not os.path.exists(pth):
                os.makedirs(pth)
            return open(f, "wb")

    def __shpFileLength(self):
        """Calculates the file length of the shp file."""
        # Start with header length
        size = 100
        # Calculate size of all shapes
        self._shp.seek(0,2)
        size += self._shp.tell()
        # Calculate size as 16-bit words
        size //= 2
        return size

    def __bbox(self, s):
        x = []
        y = []
        if len(s.points) > 0:
            px, py = list(zip(*s.points))[:2]
            x.extend(px)
            y.extend(py)
        else:
            # this should not happen.
            # any shape that is not null should have at least one point, and only those should be sent here. 
            # could also mean that earlier code failed to add points to a non-null shape. 
            raise Exception("Cannot create bbox. Expected a valid shape with at least one point. Got a shape of type '%s' and 0 points." % s.shapeType)
        bbox = [min(x), min(y), max(x), max(y)]
        # update global
        if self._bbox:
            # compare with existing
            self._bbox = [min(bbox[0],self._bbox[0]), min(bbox[1],self._bbox[1]), max(bbox[2],self._bbox[2]), max(bbox[3],self._bbox[3])]
        else:
            # first time bbox is being set
            self._bbox = bbox
        return bbox

    def __zbox(self, s):
        z = []
        for p in s.points:
            try:
                z.append(p[2])
            except IndexError:
                #warnings.warn('One or more of the shape points had a missing z-value and were skipped when calculating the Z bounding box.')
                pass
        if not z:
            # none of the shapes had z values
            # z dimension does not have the concept of nodata values
            # but setting them to 0 is probably ok, since it means all are on the same elavation
            #warnings.warn('None of the shape points had any z-values, setting the Z bounding box to (0,0).')
            z.append(0)
        zbox = [min(z), max(z)]
        # update global
        if self._zbox:
            # compare with existing
            self._zbox = [min(zbox[0],self._zbox[0]), max(zbox[1],self._zbox[1])]
        else:
            # first time zbox is being set
            self._zbox = zbox
        return zbox

    def __mbox(self, s):
        mpos = 3 if s.shapeType in (11,13,15,18,31) else 2
        m = []
        for p in s.points:
            try:
                m.append(p[mpos])
            except IndexError:
                #warnings.warn('One or more of the shape points had a missing m-value and were skipped when calculating the M bounding box.')
                pass
        if not m:
            # none of the shapes had m values
            # be flexible on this and set them to m nodata values, as per the ESRI spec
            #warnings.warn('None of the shape points had any m-values, setting the M bounding box to (nodata,nodata).')
            m.append(NODATA)
        mbox = [min(m), max(m)]
        # update global
        if self._mbox:
            # compare with existing
            self._mbox = [min(mbox[0],self._mbox[0]), max(mbox[1],self._mbox[1])]
        else:
            # first time mbox is being set
            self._mbox = mbox
        return mbox

    def bbox(self):
        """Returns the current bounding box for the shapefile which is
        the lower-left and upper-right corners. It does not contain the
        elevation or measure extremes."""
        return self._bbox

    def zbox(self):
        """Returns the current z extremes for the shapefile."""
        return self._zbox

    def mbox(self):
        """Returns the current m extremes for the shapefile."""
        return self._mbox

    def __shapefileHeader(self, fileObj, headerType='shp'):
        """Writes the specified header type to the specified file-like object.
        Several of the shapefile formats are so similar that a single generic
        method to read or write them is warranted."""
        f = self.__getFileObj(fileObj)
        f.seek(0)
        # File code, Unused bytes
        f.write(pack(">6i", 9994,0,0,0,0,0))
        # File length (Bytes / 2 = 16-bit words)
        if headerType == 'shp':
            f.write(pack(">i", self.__shpFileLength()))
        elif headerType == 'shx':
            f.write(pack('>i', ((100 + (self.shpNum * 8)) // 2)))
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
                    bbox = [0,0,0,0] 
                f.write(pack("<4d", *bbox))
            except error:
                raise ShapefileException("Failed to write shapefile bounding box. Floats required.")
        else:
            f.write(pack("<4d", 0,0,0,0))
        # Elevation
        if self.shapeType in (11,13,15,18):
            # Z values are present in Z type
            zbox = self.zbox()
        else:
            # As per the ESRI shapefile spec, the zbox for non-Z type shapefiles are set to 0s
            zbox = [0,0]
        # Measure
        if self.shapeType in (11,13,15,18,21,23,25,28,31):
            # M values are present in M or Z type
            mbox = self.mbox()
        else:
            # As per the ESRI shapefile spec, the mbox for non-M type shapefiles are set to 0s
            mbox = [0,0]
        # Try writing
        try:
            f.write(pack("<4d", zbox[0], zbox[1], mbox[0], mbox[1]))
        except error:
            raise ShapefileException("Failed to write shapefile elevation and measure values. Floats required.")

    def __dbfHeader(self):
        """Writes the dbf header and field descriptors."""
        f = self.__getFileObj(self.dbf)
        f.seek(0)
        version = 3
        year, month, day = time.localtime()[:3]
        year -= 1900
        # Remove deletion flag placeholder from fields
        for field in self.fields:
            if str(field[0]).startswith("Deletion"):
                self.fields.remove(field)
        numRecs = self.recNum
        numFields = len(self.fields)
        headerLength = numFields * 32 + 33
        if headerLength >= 65535:
            raise ShapefileException(
                    "Shapefile dbf header length exceeds maximum length.")
        recordLength = sum([int(field[2]) for field in self.fields]) + 1
        header = pack('<BBBBLHH20x', version, year, month, day, numRecs,
                headerLength, recordLength)
        f.write(header)
        # Field descriptors
        for field in self.fields:
            name, fieldType, size, decimal = field
            name = b(name, 'ascii', self.encodingErrors)
            name = name.replace(b' ', b'_')
            name = name.ljust(11).replace(b' ', b'\x00')
            fieldType = b(fieldType, 'ascii', self.encodingErrors)
            size = int(size)
            fld = pack('<11sc4xBB14x', name, fieldType, size, decimal)
            f.write(fld)
        # Terminator
        f.write(b'\r')

    def shape(self, s):
        # Balance if already not balanced
        if self.autoBalance and self.recNum < self.shpNum:
            self.balance()
        # Check is shape or import from geojson
        if not isinstance(s, Shape):
            if hasattr(s, "__geo_interface__"):
                s = s.__geo_interface__
            if isinstance(s, dict):
                s = geojson_to_shape(s)
            else:
                raise Exception("Can only write Shape objects, GeoJSON dictionaries, "
                                "or objects with the __geo_interface__, "
                                "not: %r" % s)
        # Write to file
        offset,length = self.__shpRecord(s)
        self.__shxRecord(offset, length)

    def __shpRecord(self, s):
        f = self.__getFileObj(self._shp)
        offset = 100 + f.tell()
        # Record number, Content length place holder
        f.write(pack(">2i", self.shpNum, 0))
        self.shpNum += 1
        start = f.tell()
        # Shape Type
        if self.shapeType is None and s.shapeType != NULL:
            self.shapeType = s.shapeType
        if self.shapeType != 31 and s.shapeType != NULL and s.shapeType != self.shapeType:
            raise Exception("The shape's type (%s) must match the type of the shapefile (%s)." % (s.shapeType, self.shapeType))
        f.write(pack("<i", s.shapeType))

        # For point just update bbox of the whole shapefile
        if s.shapeType in (1,11,21):
            self.__bbox(s)
        # All shape types capable of having a bounding box
        if s.shapeType in (3,5,8,13,15,18,23,25,28,31):
            try:
                f.write(pack("<4d", *self.__bbox(s)))
            except error:
                raise ShapefileException("Failed to write bounding box for record %s. Expected floats." % recNum)
        # Shape types with parts
        if s.shapeType in (3,5,13,15,23,25,31):
            # Number of parts
            f.write(pack("<i", len(s.parts)))
        # Shape types with multiple points per record
        if s.shapeType in (3,5,8,13,15,18,23,25,28,31):
            # Number of points
            f.write(pack("<i", len(s.points)))
        # Write part indexes
        if s.shapeType in (3,5,13,15,23,25,31):
            for p in s.parts:
                f.write(pack("<i", p))
        # Part types for Multipatch (31)
        if s.shapeType == 31:
            for pt in s.partTypes:
                f.write(pack("<i", pt))
        # Write points for multiple-point records
        if s.shapeType in (3,5,8,13,15,18,23,25,28,31):
            try:
                [f.write(pack("<2d", *p[:2])) for p in s.points]
            except error:
                raise ShapefileException("Failed to write points for record %s. Expected floats." % recNum)
        # Write z extremes and values
        # Note: missing z values are autoset to 0, but not sure if this is ideal.
        if s.shapeType in (13,15,18,31):
            try:
                f.write(pack("<2d", *self.__zbox(s)))
            except error:
                raise ShapefileException("Failed to write elevation extremes for record %s. Expected floats." % recNum)
            try:
                if hasattr(s,"z"):
                    # if z values are stored in attribute
                    f.write(pack("<%sd" % len(s.z), *s.z))
                else:
                    # if z values are stored as 3rd dimension
                    [f.write(pack("<d", p[2] if len(p) > 2 else 0)) for p in s.points]  
            except error:
                raise ShapefileException("Failed to write elevation values for record %s. Expected floats." % recNum)
        # Write m extremes and values
        # When reading a file, pyshp converts NODATA m values to None, so here we make sure to convert them back to NODATA
        # Note: missing m values are autoset to NODATA.
        if s.shapeType in (13,15,18,23,25,28,31):
            try:
                f.write(pack("<2d", *self.__mbox(s)))
            except error:
                raise ShapefileException("Failed to write measure extremes for record %s. Expected floats" % recNum)
            try:
                if hasattr(s,"m"): 
                    # if m values are stored in attribute
                    f.write(pack("<%sd" % len(s.m), *[m if m is not None else NODATA for m in s.m]))
                else:
                    # if m values are stored as 3rd/4th dimension
                    # 0-index position of m value is 3 if z type (x,y,z,m), or 2 if m type (x,y,m)
                    mpos = 3 if s.shapeType in (13,15,18,31) else 2
                    [f.write(pack("<d", p[mpos] if len(p) > mpos and p[mpos] is not None else NODATA)) for p in s.points]
            except error:
                raise ShapefileException("Failed to write measure values for record %s. Expected floats" % recNum)
        # Write a single point
        if s.shapeType in (1,11,21):
            try:
                f.write(pack("<2d", s.points[0][0], s.points[0][1]))
            except error:
                raise ShapefileException("Failed to write point for record %s. Expected floats." % recNum)
        # Write a single Z value
        # Note: missing z values are autoset to 0, but not sure if this is ideal.
        if s.shapeType == 11:
            # update the global z box
            self.__zbox(s)
            # then write value
            if hasattr(s, "z"):
                # if z values are stored in attribute
                try:
                    if not s.z:
                        s.z = (0,)    
                    f.write(pack("<d", s.z[0]))
                except error:
                    raise ShapefileException("Failed to write elevation value for record %s. Expected floats." % recNum)
            else:
                # if z values are stored as 3rd dimension
                try:
                    if len(s.points[0])<3:
                        s.points[0].append(0)
                    f.write(pack("<d", s.points[0][2]))
                except error:
                    raise ShapefileException("Failed to write elevation value for record %s. Expected floats." % recNum)
        # Write a single M value
        # Note: missing m values are autoset to NODATA.
        if s.shapeType in (11,21):
            # update the global m box
            self.__mbox(s)
            # then write value
            if hasattr(s, "m"):
                # if m values are stored in attribute
                try:
                    if not s.m:
                        s.m = (NODATA,) 
                    f.write(pack("<1d", s.m[0]))
                except error:
                    raise ShapefileException("Failed to write measure value for record %s. Expected floats." % recNum)
            else:
                # if m values are stored as 3rd/4th dimension
                # 0-index position of m value is 3 if z type (x,y,z,m), or 2 if m type (x,y,m)
                try:
                    mpos = 3 if s.shapeType == 11 else 2
                    if len(s.points[0])<mpos+1:
                        s.points[0].append(NODATA)
                    f.write(pack("<1d", s.points[0][mpos]))
                except error:
                    raise ShapefileException("Failed to write measure value for record %s. Expected floats." % recNum)
        # Finalize record length as 16-bit words
        finish = f.tell()
        length = (finish - start) // 2
        # start - 4 bytes is the content length field
        f.seek(start-4)
        f.write(pack(">i", length))
        f.seek(finish)
        return offset,length

    def __shxRecord(self, offset, length):
         """Writes the shx records."""
         f = self.__getFileObj(self._shx)
         f.write(pack(">i", offset // 2))
         f.write(pack(">i", length))

    def record(self, *recordList, **recordDict):
        """Creates a dbf attribute record. You can submit either a sequence of
        field values or keyword arguments of field names and values. Before
        adding records you must add fields for the record values using the
        fields() method. If the record values exceed the number of fields the
        extra ones won't be added. In the case of using keyword arguments to specify
        field/value pairs only fields matching the already registered fields
        will be added."""
        # Balance if already not balanced
        if self.autoBalance and self.recNum > self.shpNum:
            self.balance()
            
        record = []
        fieldCount = len(self.fields)
        # Compensate for deletion flag
        if self.fields[0][0].startswith("Deletion"): fieldCount -= 1
        if recordList:
            record = [recordList[i] for i in range(fieldCount)]
        elif recordDict:
            for field in self.fields:
                if field[0] in recordDict:
                    val = recordDict[field[0]]
                    if val is None:
                        record.append("")
                    else:
                        record.append(val)
        else:
            # Blank fields for empty record
            record = ["" for i in range(fieldCount)]
        self.__dbfRecord(record)

    def __dbfRecord(self, record):
        """Writes the dbf records."""
        f = self.__getFileObj(self._dbf)
        self.recNum += 1
        if not self.fields[0][0].startswith("Deletion"):
            f.write(b' ') # deletion flag
        for (fieldName, fieldType, size, deci), value in zip(self.fields, record):
            fieldType = fieldType.upper()
            size = int(size)
            if fieldType in ("N","F"):
                # numeric or float: number stored as a string, right justified, and padded with blanks to the width of the field.
                if value in MISSING:
                    value = b"*"*size # QGIS NULL
                elif not deci:
                    # force to int
                    try:
                        # first try to force directly to int.
                        # forcing a large int to float and back to int
                        # will lose information and result in wrong nr.
                        value = int(value) 
                    except ValueError:
                        # forcing directly to int failed, so was probably a float.
                        value = int(float(value))
                    value = format(value, "d")[:size].rjust(size) # caps the size if exceeds the field size
                else:
                    value = float(value)
                    value = format(value, ".%sf"%deci)[:size].rjust(size) # caps the size if exceeds the field size
            elif fieldType == "D":
                # date: 8 bytes - date stored as a string in the format YYYYMMDD.
                if isinstance(value, date):
                    value = '{:04d}{:02d}{:02d}'.format(value.year, value.month, value.day)
                elif isinstance(value, list) and len(value) == 3:
                    value = '{:04d}{:02d}{:02d}'.format(*value)
                elif value in MISSING:
                    value = b'0' * 8 # QGIS NULL for date type
                elif is_string(value) and len(value) == 8:
                    pass # value is already a date string
                else:
                    raise ShapefileException("Date values must be either a datetime.date object, a list, a YYYYMMDD string, or a missing value.")
            elif fieldType == 'L':
                # logical: 1 byte - initialized to 0x20 (space) otherwise T or F.
                if value in MISSING:
                    value = b' ' # missing is set to space
                elif value in [True,1]:
                    value = b'T'
                elif value in [False,0]:
                    value = b'F'
                else:
                    value = b' ' # unknown is set to space
            else:
                # anything else is forced to string, truncated to the length of the field
                value = b(value, self.encoding, self.encodingErrors)[:size].ljust(size)
            if not isinstance(value, bytes):
                # just in case some of the numeric format() and date strftime() results are still in unicode (Python 3 only)
                value = b(value, 'ascii', self.encodingErrors) # should be default ascii encoding
            if len(value) != size:
                raise ShapefileException(
                    "Shapefile Writer unable to pack incorrect sized value"
                    " (size %d) into field '%s' (size %d)." % (len(value), fieldName, size))
            f.write(value)

    def balance(self):
        """Adds corresponding empty attributes or null geometry records depending
        on which type of record was created to make sure all three files
        are in synch."""
        while self.recNum > self.shpNum:
            self.null()
        while self.recNum < self.shpNum:
            self.record()

    def null(self):
        """Creates a null shape."""
        self.shape(Shape(NULL))

    def point(self, x, y, z=0, m=NODATA, shapeType=POINT):
        """Creates a point shape."""
        pointShape = Shape(shapeType)
        if shapeType == POINT:
            pointShape.points.append([x, y])
        elif shapeType == POINTM:
            pointShape.points.append([x, y, m])
        elif shapeType == POINTZ:
            pointShape.points.append([x, y, z, m])
        self.shape(pointShape)

    def line(self, parts=[], shapeType=POLYLINE):
        """Creates a line shape. This method is just a convienience method
        which wraps 'poly()'.
        """
        self.poly(parts, shapeType, [])

    def poly(self, parts=[], shapeType=POLYGON, partTypes=[]):
        """Creates a shape that has multiple collections of points (parts)
        including lines, polygons, and even multipoint shapes. If no shape type
        is specified it defaults to 'polygon'. If no part types are specified
        (which they normally won't be) then all parts default to the shape type.
        """
        polyShape = Shape(shapeType)
        polyShape.parts = []
        polyShape.points = []
        # Make sure polygons are closed
        if shapeType in (5,15,25,31):
            for part in parts:
                    if part[0] != part[-1]:
                        part.append(part[0])
        for part in parts:
            polyShape.parts.append(len(polyShape.points))
            for point in part:
                # Ensure point is list
                if not isinstance(point, list):
                    point = list(point)
                # Make sure point has z and m values
                # TODO: Positions and values of missing z/m depend on shapeType
                #while len(point) < 4:
                #    point.append(0)
                polyShape.points.append(point)
        if polyShape.shapeType == 31:
            if not partTypes:
                for part in parts:
                    partTypes.append(polyShape.shapeType)
            polyShape.partTypes = partTypes
        self.shape(polyShape)

    def field(self, name, fieldType="C", size="50", decimal=0):
        """Adds a dbf field descriptor to the shapefile."""
        if fieldType == "D":
            size = "8"
            decimal = 0
        elif fieldType == "L":
            size = "1"
            decimal = 0
        if len(self.fields) >= 2046:
            raise ShapefileException(
                "Shapefile Writer reached maximum number of fields: 2046.")
        self.fields.append((name, fieldType, size, decimal))

    def saveShp(self, target):
        """Save an shp file."""
        if not hasattr(target, "write"):
            target = os.path.splitext(target)[0] + '.shp'
        self.shp = self.__getFileObj(target)
        self.__shapefileHeader(self.shp, headerType='shp')
        self.shp.seek(100)
        self._shp.seek(0)
        chunk = True
        while chunk:
            chunk = self._shp.read(self.bufsize)
            self.shp.write(chunk)

    def saveShx(self, target):
        """Save an shx file."""
        if not hasattr(target, "write"):
            target = os.path.splitext(target)[0] + '.shx'
        self.shx = self.__getFileObj(target)
        self.__shapefileHeader(self.shx, headerType='shx')
        self.shx.seek(100)
        self._shx.seek(0)
        chunk = True
        while chunk:
            chunk = self._shx.read(self.bufsize)
            self.shx.write(chunk)

    def saveDbf(self, target):
        """Save a dbf file."""
        if not hasattr(target, "write"):
            target = os.path.splitext(target)[0] + '.dbf'
        self.dbf = self.__getFileObj(target)
        self.__dbfHeader() # writes to .dbf
        self._dbf.seek(0)
        chunk = True
        while chunk:
            chunk = self._dbf.read(self.bufsize)
            self.dbf.write(chunk)

    def save(self, target=None, shp=None, shx=None, dbf=None):
        """Save the shapefile data to three files or
        three file-like objects. SHP and DBF files can also
        be written exclusively using saveShp, saveShx, and saveDbf respectively.
        If target is specified but not shp, shx, or dbf then the target path and
        file name are used.  If no options or specified, a unique base file name
        is generated to save the files and the base file name is returned as a 
        string. 
        """
        # Balance if already not balanced
        if shp and dbf:
            if self.autoBalance:
                self.balance()
            if self.recNum != self.shpNum:
                raise ShapefileException("When saving both the dbf and shp file, "
                                         "the number of records (%s) must correspond "
                                         "with the number of shapes (%s)" % (self.recNum, self.shpNum))
        # Save
        if shp:
            self.saveShp(shp)
        if shx:
            self.saveShx(shx)
        if dbf:
            self.saveDbf(dbf)
        # Create a unique file name if one is not defined
        if not shp and not shx and not dbf:
            generated = False
            if not target:
                temp = tempfile.NamedTemporaryFile(prefix="shapefile_",dir=os.getcwd())
                target = temp.name
                generated = True         
            self.saveShp(target)
            self.shp.close()
            self.saveShx(target)
            self.shx.close()
            self.saveDbf(target)
            self.dbf.close()
            if generated:
                return target

# Begin Testing
def test(**kwargs):
    import doctest
    doctest.NORMALIZE_WHITESPACE = 1
    verbosity = kwargs.get('verbose', 0)
    if verbosity == 0:
        print('Running doctests...')

    # ignore py2-3 unicode differences
    import re
    class Py23DocChecker(doctest.OutputChecker):
        def check_output(self, want, got, optionflags):
            if sys.version_info[0] == 2:
                got = re.sub("u'(.*?)'", "'\\1'", got)
                got = re.sub('u"(.*?)"', '"\\1"', got)
            res = doctest.OutputChecker.check_output(self, want, got, optionflags)
            return res
        def summarize(self):
            doctest.OutputChecker.summarize(True)

    # run tests
    runner = doctest.DocTestRunner(checker=Py23DocChecker(), verbose=verbosity)
    with open("README.md","rb") as fobj:
        test = doctest.DocTestParser().get_doctest(string=fobj.read().decode("utf8"), globs={}, name="README", filename="README.md", lineno=0)
    failure_count, test_count = runner.run(test)

    # print results
    if verbosity:
        runner.summarize(True)
    else:
        if failure_count == 0:
            print('All test passed successfully')
        elif failure_count > 0:
            runner.summarize(verbosity)

    return failure_count
    
if __name__ == "__main__":
    """
    Doctests are contained in the file 'README.md', and are tested using the built-in
    testing libraries. 
    """
    failure_count = test()
    sys.exit(failure_count)
