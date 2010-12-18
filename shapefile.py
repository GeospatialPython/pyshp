"""
shapefile.py
Provides read and write support for ESRI Shapefiles.
author: jlawhead<at>nvs-inc.com
date: 20101127
"""

from struct import pack, unpack, calcsize
import os
import time
import array
#
# Constants for shape types
NULL = 0
POINT = 1
POLYLINE = 3
POLYGON = 5
MULTIPOINT = 8
POINTZ = 11
POLYLINEZ = 13
POLYGONZ = 15
MULTIPOINTZ = 18
POINTM = 21
POLYLINEM = 23
POLYGONM = 25
MULTIPOINTM = 28
MULTIPATCH = 31

class _Array(array.array):
	"""Converts python tuples to lits of the appropritate type.
	Used to unpack different shapefile header parts."""
	def __repr__(self):
		return str(self.tolist())

class _Shape:
	def __init__(self, shapeType=None):
		"""Stores the geometry of the different shape types
		specified in the Shapefile spec. Shape types are
		usually point, polyline, or polygons. Every shape type
		except the "Null" type contains points at some level for
		example verticies in a polygon. If a shape type has
		multiple shapes containing points within a single
		geometry record then those shapes are called parts. Parts
		are designated by their starting index in geometry record's
		list of shapes."""
		self.shapeType = shapeType
		self.points = []

class _ShapeRecord:
	"""A shape object of any type."""
	def __init__(self, shape=None, record=None):
		self.shape = shape
		self.record = record

class ShapefileException(Exception):
	"""An exception to handle shapefile specific problems."""
	pass

class Reader:
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
	def __init__(self, shapefile=None):
		self.shp = None
		self.shx = None
		self.dbf = None
		self.shapeName = "Not specified"
		self._offsets = []
		self.shpLength = None
		self.numRecords = None
		self.fields = []
		self.__dbfHdrLength = 0
		self.load(shapefile)

	def load(self, shapefile=None):
		"""Opens a shapefile from a filename or file-like
		object. Normally this method would be called by the
		constructor with the file object or file name as an
		argument."""
		if shapefile:
			(shapeName, ext) = os.path.splitext(shapefile)
			self.shapeName = shapeName
			try:
				self.shp = file("%s.shp" % shapeName, "rb")
				self.__shpHeader()
			except IOError: pass
			try:
				self.shx = file("%s.shx" % shapeName, "rb")
			#	self.__shapeIndex()
			except IOError: pass
			try:
				self.dbf = file("%s.dbf" % shapeName, "rb")
				self.__dbfHeader()
			except IOError: pass

	def __getFileObj(self, f):
		"""Checks to see if the requested shapefile file object is
		available. If not a ShapefileException is raised."""
		if not f:
			raise ShapefileException("Required file not available.")
		return f

	def __restrictIndex(self, i):
		"""Provides list-like handling of a record index with a clearer
		error message if the index is out of bounds."""
		if self.numRecords:
			max = self.numRecords - 1
			if abs(i) > max:
				raise IndexError("Shape or Record index out of range.")
			if i < 0: i = range(self.numRecords)[i]
		return i

	def __shpHeader(self):
		"""Reads the header information from a .shp or .shx file."""
		f = self.__getFileObj(self.shp)
		# File length (16-bit word * 2 = bytes)
		f.seek(24)
		self.shpLength = unpack(">i", f.read(4))[0] * 2
		# Shape type
		f.seek(32)
		self.shapeType= unpack("i", f.read(4))[0]
		# The shapefile's bounding box (lower left, upper right)
		self.bbox = _Array('d', unpack("<4d", f.read(32)))
		# Elevation
		self.elevation = _Array('d', unpack("<2d", f.read(16)))
		# Measure
		self.measure = _Array('d', unpack("<2d", f.read(16)))

	def __shape(self):
		"""Returns the header info and geometry for a single shape."""
		f = self.__getFileObj(self.shp)
		record = _Shape()
		nParts = nPoints = zmin = zmax = mmin = mmax = None
		(recNum, recLength) = unpack(">2i", f.read(8))
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
		if shapeType in (3,5,8,13,15,23,25,31):
			nPoints = unpack("<i", f.read(4))[0]
		# Read parts
		if nParts:
			record.parts = _Array('i', unpack("<%si" % nParts, f.read(nParts * 4)))
		# Read part types for Multipatch - 31
		if shapeType == 31:
			record.partTypes = _Array('i', unpack("<%si" % nParts, f.read(nParts * 4)))
		# Read points - produces a list of [x,y] values
		if nPoints:
			record.points = [_Array('d', unpack("<2d", f.read(16))) for p in range(nPoints)]
		# Read z extremes and values
		if shapeType in (13,15,18,31):
			(zmin, zmax) = unpack("<2d", f.read(16))
			record.z = _Array('d', unpack("<%sd" % nPoints, f.read(nPoints * 8)))
		# Read m extremes and values
		if shapeType in (9,13,15,18,23,25,31):
			(mmin, mmax) = unpack("<2d", f.read(16))
			record.m = _Array('d', unpack("%sd" % nPoints, f.read(nPoints * 8)))
		# Read a single point
		if shapeType in (1,11,21):
			record.points = [_Array('d', unpack("<2d", f.read(16)))]
		# Read a single Z value
		if shapeType == 11:
			record.z = unpack("<d", f.read(8))
		# Read a single M value
		if shapeType in (11, 21):
			record.m = unpack("<d", f.read(8))
		return record

	def __shapeIndex(self, i=None):
		"""Returns the offset in a .shp file for a shape based on information
		in the .shx index file."""
		f = self.__getFileObj(self.shx)
		if not f:
			return None
		if not self._offsets:
			# File length (16-bit word * 2 = bytes) - header length
			f.seek(24)
			shxRecordLength = (unpack(">i", f.read(4))[0] * 2) - 100
			numRecords = shxRecordLength / 8
			# Jump to the first record.
			f.seek(100)
			for r in range(numRecords):
				# Offsets are 16-bit words just like the file length
				self._offsets.append(unpack(">i", f.read(4))[0] * 2)
				f.seek(f.tell() + 4)
		if i:
			return self._offsets[i]

	def shape(self, i=0):
		"""Returns a shape object for a shape in the the geometry
		record file."""
		f = self.shp
		i = self.__restrictIndex(i)
		offset = self.__shapeIndex(i)
		if not offset:
			# Shx index not available so use the full list.
			shapes = self.shapes()
			return shapes[i]
		f.seek(offset)
		return self.__shape()

	def shapes(self):
		"""Returns all shapes in a shapefile."""
		self.shp.seek(100)
		shapes = []
		while self.shp.tell() < self.shpLength:
			shapes.append(self.__shape())
		return shapes

	def __dbfHeaderLength(self):
		"""Retrieves the header length of a dbf file header."""
		if not self.__dbfHdrLength:
			f = self.__getFileObj(self.dbf)
			(self.numRecords, self.__dbfHdrLength) = \
				unpack("<xxxxLH22x", f.read(32))
		return self.__dbfHdrLength

	def __dbfHeader(self):
		"""Reads a dbf header. Xbase-related code borrows heavily from ActiveState Python Cookbook Recipe 362715 by Raymond Hettinger"""
		f = self.__getFileObj(self.dbf)
		headerLength = self.__dbfHeaderLength()
		numFields = (headerLength - 33) // 32
		for field in range(numFields):
			fieldDesc = list(unpack("<11sc4xBB14x", f.read(32)))
			name = 0
			fieldDesc[name] = fieldDesc[name][:fieldDesc[name].index("\x00")]
			fieldDesc[name] = fieldDesc[name].lstrip()
			self.fields.append(fieldDesc)
		terminator = f.read(1)
		assert terminator == "\r"
		self.fields.insert(0, ('DeletionFlag', 'C', 1, 0))

	def __recordFmt(self):
		"""Calculates the size of a .shp geometry record."""
		if not self.numRecords:
			self.__dbfHeader()
		fmt = ''.join(['%ds' % fieldinfo[2] for fieldinfo in self.fields])
		fmtSize = calcsize(fmt)
		return (fmt, fmtSize)

	def __record(self):
		"""Reads and returns a dbf record row as a list of values."""
		f = self.__getFileObj(self.dbf)
		recFmt = self.__recordFmt()
		recordContents = unpack(recFmt[0], f.read(recFmt[1]))
		if recordContents[0] != ' ':
			# deleted record
			return None
		record = []
		for (name, typ, size, deci), value in zip(self.fields,
													recordContents):
			if name == 'DeletionFlag':
				continue
			if typ == "N":
				value = value.replace('\0', '').strip()
				if value == '':
					value = 0
				elif deci:
					value = float(value)
				else:
					value = int(value)
			elif typ == 'D':
				y, m, d = int(value[:4]), int(value[4:6]), int(value[6:8])
				value = [y, m, d]
			elif typ == 'L':
				value = (value in 'YyTt' and 'T') or \
							(value in 'NnFf' and 'F') or '?'
			else:
				value = value.strip()
			record.append(value)
		return record

	def record(self, i=0):
		"""Returns a specific dbf record based on the supplied index."""
		f = self.__getFileObj(self.dbf)
		if not self.numRecords:
			self.__dbfHeader()
		i = self.__restrictIndex(i)
		recSize = self.__recordFmt()[1]
		f.seek(0)
		f.seek(self.__dbfHeaderLength() + (i * recSize))
		return self.__record()

	def records(self):
		"""Returns all records in a dbf file."""
		if not self.numRecords:
			self.__dbfHeader()
		records = []
		f = self.__getFileObj(self.dbf)
		f.seek(self.__dbfHeaderLength())
		for i in xrange(self.numRecords):
			r = self.__record()
			if r:
				records.append(r)
		return records

	def shapeRecord(self, i=0):
		"""Returns a combination geometry and attribute record for the
		supplied record index."""
		i = self.__restrictIndex(i)
		return _ShapeRecord(shape=self.shape(i),
								record=self.record(i))

	def shapeRecords(self):
		"""Returns a list of combination geometry/attribute records for
		all records in a shapefile."""
		shapeRecords = []
		return [_ShapeRecord(shape=rec[0], record=rec[1]) \
					for rec in zip(self.shapes(), self.records())]

class Writer:
	"""Provides write support for ESRI Shapefiles."""
	def __init__(self, shapeType=None):
		self._shapes = []
		self.fields = []
		self.records = []
		self.shapeType = shapeType
		self.shp = None
		self.shx = None
		self.dbf = None
		# Geometry record offsets and lengths for writing shx file.
		self._offsets = []
		self._lengths = []
		# Use deletion flags in dbf? Default is false (0).
		self.deletionFlag = 0

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
			return file(f, "wb")

	def __shpFileLength(self):
		"""Calculates the file length of the shp file."""
		# Start with header length
		size = 100
		# Calculate size of all shapes
		for s in self._shapes:
			# Add in record header and shape type fields
			size += 12
			# nParts and nPoints do not apply to all shapes
			if self.shapeType not in (0,1):
				nParts = len(s.parts)
				nPoints = len(s.points)
			# All shape types capable of having a bounding box
			if self.shapeType in (3,5,8,13,15,18,23,25,28,31):
				size += 32
			# Shape types with parts
			if self.shapeType in (3,5,13,15,23,25,31):
				# Parts count
				size += 4
				# Parts index array
				size += nParts * 4
			# Shape types with points
			if self.shapeType in (3,5,8,13,15,23,25,31):
				# Points count
				size += 4
				# Points array
				size += 16 * nPoints
			# Calc size of part types for Multipatch (31)
			if self.shapeType == 31:
				size += nParts * 4
			# Calc z extremes and values
			if self.shapeType in (13,15,18,31):
				# z extremes
				size += 16
				# z array
				size += 8 * nPoints
			# Read m extremes and values
			if self.shapeType in (9,13,15,18,23,25,31):
				# m extremes
				size += 16
				# m array
				size += 8 * nPoints
			# Read a single point
			if self.shapeType in (1,11,21):
				size += 16
			# Read a single Z value
			if self.shapeType == 11:
				size += 8
			# Read a single M value
			if self.shapeType in (11, 21):
				size += 8
		# Calculate size as 16-bit words
		size /= 2
		return size

	def __bbox(self, shapes, shapeTypes=[]):
		x = []
		y = []
		for s in shapes:
			shapeType = self.shapeType
			if shapeTypes:
				shapeType = shapeTypes[shapes.index(s)]
			px, py = zip(*s.points)[:2]
			x.extend(px)
			y.extend(py)
		return [min(x), min(y), max(x), max(y)]

	def __zbox(self, shapes, shapeTypes=[]):
		z = []
		for s in shapes:
			shapeType = self.shapeType
			if shapeTypes:
				shapeType = shapeTypes[shapes.index(s)]
			try:
				if shapeType == 11:
					z.append(s[2])
				else:
					for p in s.points:
						z.append(p[2])
			except IndexError:
				pass
		if not z: z.append(0)
		return [min(z), max(z)]

	def __mbox(self, shapes, shapeTypes=[]):
		m = [0]
		for s in shapes:
			shapeType = self.shapeType
			if shapeTypes:
				shapeType = shapeTypes[shapes.index(s)]
			try:
				if shapeType in (11, 21):
					m.append(s[2])
				else:
					for p in s.points:
						m.append(p[3])
			except IndexError:
				pass
		return [min(m), max(m)]

	def bbox(self):
		"""Returns the current bounding box for the shapefile which is
		the lower-left and upper-right corners. It does not contain the
		elevation or measure extremes."""
		return self.__bbox(self._shapes)

	def zbox(self):
		"""Returns the current z extremes for the shapefile."""
		return self.__zbox(self._shapes)

	def mbox(self):
		"""Returns the current m extremes for the shapefile."""
		return self.__mbox(self._shapes)

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
			f.write(pack('>i', ((100 + (len(self._shapes) * 8)) / 2)))
		# Version, Shape type                                  
		f.write(pack("<2i", 1000, self.shapeType))
		# The shapefile's bounding box (lower left, upper right)
		f.write(pack("<4d", *self.bbox()))
		# Elevation
		z = self.zbox()
		# Measure
		m = self.mbox()
		f.write(pack("<4d", z[0], z[1], m[0], m[1]))

	def __dbfHeader(self):
		"""Writes the dbf header and field descriptors."""
		f = self.__getFileObj(self.dbf)
		f.seek(0)
		version = 3
		year, month, day = time.localtime()[:3]
		year -= 1900
		# Remove deletion flag placeholder from fields
		for field in self.fields:
			if field[0].startswith("Deletion"):
				self.fields.remove(field)
		numRecs = len(self.records)
		numFields = len(self.fields)
		headerLength = numFields * 32 + 33
		recordLength = sum([int(field[2]) for field in self.fields]) + 1
		header = pack('<BBBBLHH20x', version, year, month, day, numRecs,
			headerLength, recordLength)
		f.write(header)
		# Field descriptors
		for field in self.fields:
			name, fieldType, size, decimal = field
			name = name.replace(' ', '_')
			name = name.ljust(11).replace(' ', '\x00')
			size = int(size)
			fld = pack('<11sc4xBB14x', name, fieldType, size, decimal)
			f.write(fld)
		# Terminator
		f.write('\r')

	def __shpRecords(self):
		"""Write the shp records"""
		f = self.__getFileObj(self.shp)
		f.seek(100)
		recNum = 1
		for s in self._shapes:
			self._offsets.append(f.tell())
			# Record number, Content length place holder
			f.write(pack(">2i", recNum, 0))
			recNum += 1
			start = f.tell()
			# Shape Type
			f.write(pack("<i", s.shapeType))
			# All shape types capable of having a bounding box
			if s.shapeType in (3,5,8,13,15,18,23,25,28,31):
				f.write(pack("<4d", *self.__bbox([s])))
			# Shape types with parts
			if s.shapeType in (3,5,13,15,23,25,31):
				# Number of parts
				f.write(pack("<i", len(s.parts)))
			# Shape types with points
			if s.shapeType in (3,5,8,13,15,23,25,31):
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
			# Write points
			if s.shapeType in (3,5,8,13,15,23,25,31):
				for part in s.parts:
					[f.write(pack("<2d", *p[:2])) for p in s.points]	
			# Write z extremes and values
			if s.shapeType in (13,15,18,31):
				f.write(pack("<2d", *self.__zbox(s.parts)))
				for part in s.parts:
					[f.write(pack("<d", *p)) for p in part]
			# Write m extremes and values
			if s.shapeType in (9,13,15,18,23,25,31):
				f.write(pack("<2d", *self.__mbox(s.parts)))
				for part in s.parts:
					[f.write(pack("<d", p[3])) for p in part]
			# Write a single point
			if s.shapeType in (1,11,21):
				for p in s.points:
					f.write(pack("<2d", p[0], p[1]))
			# Write a single Z value
			if s.shapeType == 11:
				for part in s.parts:
					for point in parts:
						f.write(pack("<d", point[2]))
			# Write a single M value
			if s.shapeType in (11, 21):
				for part in s.parts:
					[f.write(pack("<d", p[3])) for p in part]
			# Finalize record length as 16-bit words
			finish = f.tell()
			length = (finish - start) / 2
			self._lengths.append(length)
			# start - 4 bytes is the content length field
			f.seek(start-4)
			f.write(pack(">i", length))
			f.seek(finish)

	def __shxRecords(self):
		"""Writes the shx records."""
		f = self.__getFileObj(self.shx)
		f.seek(100)
		for i in range(len(self._shapes)):
			f.write(pack(">i", self._offsets[i]/2))
			f.write(pack(">i", self._lengths[i]))

	def __dbfRecords(self):
	    """Writes the dbf records."""
	    f = self.__getFileObj(self.dbf)
	    for record in self.records:
	        if not self.fields[0][0].startswith("Deletion"):
	            f.write(' ') # deletion flag
	        for (fieldName, fieldType, size, decimal), value in zip(self.fields, record):
	            fieldType = fieldType.upper()
	            size = int(size)
	            if fieldType.upper() == "N":
	                value = str(value).rjust(size)
	            elif fieldType == 'L':
	                value = str(value)[0].upper()
	            else:
	                value = str(value)[:size].ljust(size)
	            assert len(value) == size
	            f.write(value)

	def null(self):
		"""Creates a null shape."""
		self._shapes.append(_Shape(NULL))

	def point(self, x, y, z=0, m=0):
		"""Creates a point shape."""
		pointShape = _Shape(POINT)
		pointShape.points.append([x, y, z, m])
		self._shapes.append(pointShape)

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
		polyShape = _Shape(shapeType)
		polyShape.parts = []
		polyShape.points = []
		for part in parts:
			polyShape.parts.append(len(polyShape.points))
			for point in part:
				# Make sure point has z and m values
				while len(point) < 4:
					point.append(0)
				polyShape.points.append(point)
		if polyShape.shapeType == 31:
			if not partTypes:
				for part in parts:
					partTypes.append(polyShape.shapeType)
			polyShape.partTypes = partTypes
		self._shapes.append(polyShape)

	def field(self, name, fieldType="C", size="50", decimal=0):
		"""Adds a dbf field descriptor to the shapefile."""
		self.fields.append((name, fieldType, size, decimal))

	def record(self, *recordList, **recordDict):
		"""Creates a dbf attribute record. You can submit either a sequence of
		field values or a dictionary with field names and values. Before
		adding records you must add fields for the record values using the
		fields() method. If the record values exceed the number of fields the
		extra ones won't be added. In the case of using a dictionary to specify
		field/value pairs only fields matching the already registered fields
		will be added."""
		record = []
		fieldCount = len(self.fields)
		# Compensate for deletion flag
		if self.fields[0][0].startswith("Deletion"): fieldCount -= 1
		if recordList:
			[record.append(recordList[i]) for i in range(fieldCount)]
		elif recordDict:
				for field in self.fields:
					if recordDict.get(field[0], None):
						record.append(recordDict[field[0]])
		if record:
			self.records.append(record)

	def shape(self, i):
		return self._shapes[i]

	def shapes(self):
		"""Return the current list of shapes."""
		return self._shapes

	def saveShp(self, target):
		"""Save an shp file."""
		target = os.path.splitext(target)[0] + '.shp'
		if not self.shapeType:
			self.shapeType = self._shapes[0].shapeType
		self.shp = self.__getFileObj(target)
		self.__shapefileHeader(self.shp, headerType='shp')
		self.__shpRecords()
		self.shp.close()

	def saveShx(self, target):
		"""Save an shx file."""
		target = os.path.splitext(target)[0] + '.shx'
		if not self.shapeType:
			self.shapeType = self._shapes[0].shapeType
		self.shx = self.__getFileObj(target)
		self.__shapefileHeader(self.shx, headerType='shx')
		self.__shxRecords()
		self.shx.close()

	def saveDbf(self, target):
		"""Save a dbf file."""
		target = os.path.splitext(target)[0] + '.dbf'
		self.dbf = self.__getFileObj(target)
		self.__dbfHeader()
		self.__dbfRecords()
		self.dbf.close()

	def save(self, target=""):
		"""Save the shapefile data to three files or
		three file-like objects. SHP and DBF files can
		be written exclusively using saveShp, saveShx, and saveDbf respectively."""
		# TODO: Create a unique filename for target if None.
		self.saveShp(target)
		self.saveShx(target)
		self.saveDbf(target)

class Editor(Writer):
	def __init__(self, shapefile=None, shapeType=POINT, autoBalance=1):
		self.autoBalance = autoBalance
		if not shapefile:
			Writer.__init__(self, shapeType)
		elif isinstance(shapefile, basestring):
			base = os.path.splitext(shapefile)[0]
			if os.path.isfile("%s.shp" % base):
				r = Reader(base)
				Writer.__init__(self, r.shapeType)
				self._shapes = r.shapes()
				self.fields = r.fields
				self.records = r.records()

	def select(self, expr):
		"""Select one or more shapes (to be implemented)"""
		# TODO: Implement expressions to select shapes.
		pass

	def delete(self, shape=None, part=None, point=None):
		"""Deletes the specified part of any shape by specifying a shape
		number, part number, or point number."""
		# shape, part, point
		if shape and part and point:
			del self._shapes[shape][part][point]
		# shape, part
		elif shape and part and not point:
			del self._shapes[shape][part]
		# shape
		elif shape and not part and not point:
			del self._shapes[shape]
		# point
		elif not shape and not part and point:
			for s in self._shapes:
				if s.shapeType == 1:
					del self._shapes[point]
				else:
					for part in s.parts:
						del s[part][point]
		# part, point
		elif not shape and part and point:
			for s in self._shapes:
				del s[part][point]
		# part
		elif not shape and part and not point:
			for s in self._shapes:
				del s[part]

	def point(self, x=None, y=None, z=None, m=None, shape=None, part=None, point=None, addr=None):
		"""Creates/updates a point shape. The arguments allows
		you to update a specific point by shape, part, point of any
		shape type."""
		# shape, part, point
		if shape and part and point:
			try: self._shapes[shape]
			except IndexError: self._shapes.append([])
			try: self._shapes[shape][part]
			except IndexError: self._shapes[shape].append([])
			try: self._shapes[shape][part][point]
			except IndexError: self._shapes[shape][part].append([])
			p = self._shapes[shape][part][point]
			if x: p[0] = x
			if y: p[1] = y
			if z: p[2] = z
			if m: p[3] = m
			self._shapes[shape][part][point] = p
		# shape, part
		elif shape and part and not point:
			try: self._shapes[shape]
			except IndexError: self._shapes.append([])
			try: self._shapes[shape][part]
			except IndexError: self._shapes[shape].append([])
			points = self._shapes[shape][part]
			for i in range(len(points)):
				p = points[i]
				if x: p[0] = x
				if y: p[1] = y
				if z: p[2] = z
				if m: p[3] = m
				self._shapes[shape][part][i] = p
		# shape
		elif shape and not part and not point:
			try: self._shapes[shape]
			except IndexError: self._shapes.append([])

		# point
		# part
		if addr:
			shape, part, point = addr
			self._shapes[shape][part][point] = [x, y, z, m]
		else:
			Writer.point(self, x, y, z, m)
		if self.autoBalance:
			self.balance()

	def validate(self):
		"""An optional method to try and validate the shapefile
		as much as possible before writing it (not implemented)."""
		#TODO: Implement validation method
		pass

	def balance(self):
		"""Adds a corresponding empty attribute or null geometry record depending
		on which type of record was created to make sure all three files
		are in synch."""
		if len(self.records) > len(self._shapes):
			self.null()
		elif len(self.records) < len(self._shapes):
			self.record()

	def __fieldNorm(self, fieldName):
		"""Normalizes a dbf field name to fit within the spec and the
		expectations of certain ESRI software."""
		if len(fieldName) > 11: fieldName = fieldName[:11]
		fieldName = fieldName.upper()
		fieldName.replace(' ', '_')

# Begin Testing
def test():
	import doctest
	import usage
	doctest.NORMALIZE_WHITESPACE = 1
	doctest.testmod(usage, verbose=1)

if __name__ == "__main__":
	"""
	Doctests are contained in the module 'usage.py'. This library was developed
	using Python 2.3. Python 2.4 and above have some excellent improvements in the built-in
	testing libraries but for now unit testing is done using what's available in
	2.3.
	"""
	test()


