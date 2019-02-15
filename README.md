# PyShp

The Python Shapefile Library (PyShp) reads and writes ESRI Shapefiles in pure Python.

![pyshp logo](http://4.bp.blogspot.com/_SBi37QEsCvg/TPQuOhlHQxI/AAAAAAAAAE0/QjFlWfMx0tQ/S350/GSP_Logo.png "PyShp")

[![Build Status](https://travis-ci.org/GeospatialPython/pyshp.svg?branch=master)](https://travis-ci.org/GeospatialPython/pyshp)

## Contents

[Overview](#overview)

[Version Changes](#version-changes)

[Examples](#examples)
- [Reading Shapefiles](#reading-shapefiles)
  - [The Reader Class](#the-reader-class)
  - [Reading Geometry](#reading-geometry)
  - [Reading Records](#reading-records)
  - [Reading Geometry and Records Simultaneously](#reading-geometry-and-records-simultaneously)
- [Writing Shapefiles](#writing-shapefiles)
  - [The Writer Class](#the-writer-class)
  - [Adding Records](#adding-records)
  - [Adding Geometry](#adding-geometry)
  - [Geometry and Record Balancing](#geometry-and-record-balancing)
  
[How To's](#how-tos)
- [3D and Other Geometry Types](#3d-and-other-geometry-types)
- [Working with Large Shapefiles](#working-with-large-shapefiles)
- [Unicode and Shapefile Encodings](#unicode-and-shapefile-encodings)

[Testing](#testing)


# Overview

The Python Shapefile Library (PyShp) provides read and write support for the
Esri Shapefile format. The Shapefile format is a popular Geographic
Information System vector data format created by Esri. For more information
about this format please read the well-written "ESRI Shapefile Technical
Description - July 1998" located at [http://www.esri.com/library/whitepapers/p
dfs/shapefile.pdf](http://www.esri.com/library/whitepapers/pdfs/shapefile.pdf)
. The Esri document describes the shp and shx file formats. However a third
file format called dbf is also required. This format is documented on the web
as the "XBase File Format Description" and is a simple file-based database
format created in the 1960's. For more on this specification see: [http://www.clicketyclick.dk/databases/xbase/format/index.html](http://www.clicketyclick.dk/databases/xbase/format/index.html)

Both the Esri and XBase file-formats are very simple in design and memory
efficient which is part of the reason the shapefile format remains popular
despite the numerous ways to store and exchange GIS data available today.

Pyshp is compatible with Python 2.7-3.x.

This document provides examples for using PyShp to read and write shapefiles. However 
many more examples are continually added to the blog [http://GeospatialPython.com](http://GeospatialPython.com),
and by searching for PyShp on [https://gis.stackexchange.com](https://gis.stackexchange.com). 

Currently the sample census blockgroup shapefile referenced in the examples is available on the GitHub project site at
[https://github.com/GeospatialPython/pyshp](https://github.com/GeospatialPython/pyshp). These
examples are straight-forward and you can also easily run them against your
own shapefiles with minimal modification. 

Important: If you are new to GIS you should read about map projections.
Please visit: [https://github.com/GeospatialPython/pyshp/wiki/Map-Projections](https://github.com/GeospatialPython/pyshp/wiki/Map-Projections)

I sincerely hope this library eliminates the mundane distraction of simply
reading and writing data, and allows you to focus on the challenging and FUN
part of your geospatial project.


# Version Changes

## 2.1.0

### New Features:
- Added back read/write support for unicode field names. 
- Improved Record representation
- More support for geojson on Reader, ShapeRecord, ShapeRecords, and shapes()

### Bug fixes:

- Fixed error when reading optional m-values
- Fixed Record attribute autocomplete in Python 3
- Misc readme cleanup

## 2.0.0

The newest version of PyShp, version 2.0 introduced some major new improvements. 
A great thanks to all who have contributed code and raised issues, and for everyone's
patience and understanding during the transition period. 
Some of the new changes are incompatible with previous versions. 
Users of the previous version 1.x should therefore take note of the following changes
(Note: Some contributor attributions may be missing): 

### Major Changes:

- Full support for unicode text, with custom encoding, and exception handling. 
  - Means that the Reader returns unicode, and the Writer accepts unicode. 
- PyShp has been simplified to a pure input-output library using the Reader and Writer classes, dropping the Editor class. 
- Switched to a new streaming approach when writing files, keeping memory-usage at a minimum:
  - Specify filepath/destination and text encoding when creating the Writer. 
  - The file is written incrementally with each call to shape/record. 
  - Adding shapes is now done using dedicated methods for each shapetype. 
- Reading shapefiles is now more convenient:
  - Shapefiles can be opened using the context manager, and files are properly closed. 
  - Shapefiles can be iterated, have a length, and supports the geo interface. 
  - New ways of inspecing shapefile metadata by printing. [@megies]
  - More convenient accessing of Record values as attributes. [@philippkraft]
  - More convenient shape type name checking. [@megies] 
- Add more support and documentation for MultiPatch 3D shapes. 
- The Reader "elevation" and "measure" attributes now renamed "zbox" and "mbox", to make it clear they refer to the min/max values. 
- Better documentation of previously unclear aspects, such as field types. 

### Important Fixes:

- More reliable/robust:
  - Fixed shapefile bbox error for empty or point type shapefiles. [@mcuprjak]
  - Reading and writing Z and M type shapes is now more robust, fixing many errors, and has been added to the documentation. [@ShinNoNoir]
  - Improved parsing of field value types, fixed errors and made more flexible. 
  - Fixed bug when writing shapefiles with datefield and date values earlier than 1900 [@megies]
- Fix some geo interface errors, including checking polygon directions.
- Bug fixes for reading from case sensitive file names, individual files separately, and from file-like objects. [@gastoneb, @kb003308, @erickskb]
- Enforce maximum field limit. [@mwtoews]


# Examples

Before doing anything you must import the library.


	>>> import shapefile

The examples below will use a shapefile created from the U.S. Census Bureau
Blockgroups data set near San Francisco, CA and available in the git
repository of the PyShp GitHub site.

## Reading Shapefiles

### The Shapefile Class

To read a shapefile create a new "Reader" object and pass it the name of an
existing shapefile. The shapefile format is actually a collection of three
files. You specify the base filename of the shapefile or the complete filename
of any of the shapefile component files.


	>>> sf = shapefile.Reader("shapefiles/blockgroups")

OR


	>>> sf = shapefile.Reader("shapefiles/blockgroups.shp")

OR


	>>> sf = shapefile.Reader("shapefiles/blockgroups.dbf")

OR any of the other 5+ formats which are potentially part of a shapefile. The
library does not care about file extensions.

#### Reading Shapefiles Using the Context Manager

The "Reader" class can be used as a context manager, to ensure open file
objects are properly closed when done reading the data:

    >>> with shapefile.Reader("shapefiles/blockgroups.shp") as shp:
    ...     print(shp)
    shapefile Reader
        663 shapes (type 'POLYGON')
        663 records (44 fields)

#### Reading Shapefiles from File-Like Objects

You can also load shapefiles from any Python file-like object using keyword
arguments to specify any of the three files. This feature is very powerful and
allows you to load shapefiles from a url, a zip file, a serialized object,
or in some cases a database.


	>>> myshp = open("shapefiles/blockgroups.shp", "rb")
	>>> mydbf = open("shapefiles/blockgroups.dbf", "rb")
	>>> r = shapefile.Reader(shp=myshp, dbf=mydbf)

Notice in the examples above the shx file is never used. The shx file is a
very simple fixed-record index for the variable-length records in the shp
file. This file is optional for reading. If it's available PyShp will use the
shx file to access shape records a little faster but will do just fine without
it.

#### Reading Shapefile Meta-Data

Shapefiles have a number of attributes for inspecting the file contents.
A shapefile is a container for a specific type of geometry, and this can be checked using the 
shapeType attribute. 


	>>> sf.shapeType
	5

Shape types are represented by numbers between 0 and 31 as defined by the
shapefile specification and listed below. It is important to note that the numbering system has
several reserved numbers that have not been used yet, therefore the numbers of
the existing shape types are not sequential:

- NULL = 0
- POINT = 1
- POLYLINE = 3
- POLYGON = 5
- MULTIPOINT = 8
- POINTZ = 11
- POLYLINEZ = 13
- POLYGONZ = 15
- MULTIPOINTZ = 18
- POINTM = 21
- POLYLINEM = 23
- POLYGONM = 25
- MULTIPOINTM = 28
- MULTIPATCH = 31
	
Based on this we can see that our blockgroups shapefile contains
Polygon type shapes. The shape types are also defined as constants in
the shapefile module, so that we can compare types more intuitively:


	>>> sf.shapeType == shapefile.POLYGON
	True

For convenience, you can also get the name of the shape type as a string:


	>>> sf.shapeTypeName == 'POLYGON'
	True
	
Other pieces of meta-data that we can check include the number of features 
and the bounding box area the shapefile covers:


	>>> len(sf)
	663
	>>> sf.bbox
	[-122.515048, 37.652916, -122.327622, 37.863433]
	
Finally, if you would prefer to work with the entire shapefile in a different
format, you can convert all of it to a GeoJSON dictionary, although you may lose
some information in the process, such as z- and m-values: 


	>>> sf.__geo_interface__['type']
	'FeatureCollection'

### Reading Geometry

A shapefile's geometry is the collection of points or shapes made from
vertices and implied arcs representing physical locations. All types of
shapefiles just store points. The metadata about the points determine how they
are handled by software.

You can get a list of the shapefile's geometry by calling the shapes()
method.


	>>> shapes = sf.shapes()

The shapes method returns a list of Shape objects describing the geometry of
each shape record.


	>>> len(shapes)
	663
	
To read a single shape by calling its index use the shape() method. The index
is the shape's count from 0. So to read the 8th shape record you would use its
index which is 7.


	>>> s = sf.shape(7)

	>>> # Read the bbox of the 8th shape to verify
	>>> # Round coordinates to 3 decimal places
	>>> ['%.3f' % coord for coord in s.bbox]
	['-122.450', '37.801', '-122.442', '37.808']

Each shape record (except Points) contains the following attributes. Records of
shapeType Point do not have a bounding box 'bbox'.


	>>> for name in dir(shapes[3]):
	...     if not name.startswith('_'):
	...         name
	'bbox'
	'parts'
	'points'
	'shapeType'
	'shapeTypeName'

  * shapeType: an integer representing the type of shape as defined by the
	  shapefile specification.


		>>> shapes[3].shapeType
		5

  * shapeTypeName: a string representation of the type of shape as defined by shapeType. Read-only. 


		>>> shapes[3].shapeTypeName
		'POLYGON'
		
  * bbox: If the shape type contains multiple points this tuple describes the
	  lower left (x,y) coordinate and upper right corner coordinate creating a
	  complete box around the points. If the shapeType is a
	  Null (shapeType == 0) then an AttributeError is raised.


		>>> # Get the bounding box of the 4th shape.
		>>> # Round coordinates to 3 decimal places
		>>> bbox = shapes[3].bbox
		>>> ['%.3f' % coord for coord in bbox]
		['-122.486', '37.787', '-122.446', '37.811']

  * parts: Parts simply group collections of points into shapes. If the shape
	  record has multiple parts this attribute contains the index of the first
	  point of each part. If there is only one part then a list containing 0 is
	  returned.


		>>> shapes[3].parts
		[0]

  * points: The points attribute contains a list of tuples containing an
	  (x,y) coordinate for each point in the shape.


		>>> len(shapes[3].points)
		173
		>>> # Get the 8th point of the fourth shape
		>>> # Truncate coordinates to 3 decimal places
		>>> shape = shapes[3].points[7]
		>>> ['%.3f' % coord for coord in shape]
		['-122.471', '37.787']

In most cases, however, if you need to do more than just type or bounds checking, you may want 
to convert the geometry to the more human-readable [GeoJSON format](http://geojson.org),
where lines and polygons are grouped for you:


	>>> s = sf.shape(0)
	>>> geoj = s.__geo_interface__
	>>> geoj["type"]
	'MultiPolygon'
	
The results from the shapes() method similiarly supports converting to GeoJSON:


	>>> shapes.__geo_interface__['type']
	'GeometryCollection'
	

### Reading Records

A record in a shapefile contains the attributes for each shape in the
collection of geometries. Records are stored in the dbf file. The link between
geometry and attributes is the foundation of all geographic information systems.
This critical link is implied by the order of shapes and corresponding records
in the shp geometry file and the dbf attribute file.

The field names of a shapefile are available as soon as you read a shapefile.
You can call the "fields" attribute of the shapefile as a Python list. Each
field is a Python list with the following information:

  * Field name: the name describing the data at this column index.
  * Field type: the type of data at this column index. Types can be: 
       * "C": Characters, text.
	   * "N": Numbers, with or without decimals.
	   * "F": Floats (same as "N").
	   * "L": Logical, for boolean True/False values. 
	   * "D": Dates. 
	   * "M": Memo, has no meaning within a GIS and is part of the xbase spec instead.
  * Field length: the length of the data found at this column index. Older GIS
	   software may truncate this length to 8 or 11 characters for "Character"
	   fields.
  * Decimal length: the number of decimal places found in "Number" fields.

To see the fields for the Reader object above (sf) call the "fields"
attribute:


	>>> fields = sf.fields

	>>> assert fields == [("DeletionFlag", "C", 1, 0), ["AREA", "N", 18, 5],
	... ["BKG_KEY", "C", 12, 0], ["POP1990", "N", 9, 0], ["POP90_SQMI", "N", 10, 1],
	... ["HOUSEHOLDS", "N", 9, 0],
	... ["MALES", "N", 9, 0], ["FEMALES", "N", 9, 0], ["WHITE", "N", 9, 0],
	... ["BLACK", "N", 8, 0], ["AMERI_ES", "N", 7, 0], ["ASIAN_PI", "N", 8, 0],
	... ["OTHER", "N", 8, 0], ["HISPANIC", "N", 8, 0], ["AGE_UNDER5", "N", 8, 0],
	... ["AGE_5_17", "N", 8, 0], ["AGE_18_29", "N", 8, 0], ["AGE_30_49", "N", 8, 0],
	... ["AGE_50_64", "N", 8, 0], ["AGE_65_UP", "N", 8, 0],
	... ["NEVERMARRY", "N", 8, 0], ["MARRIED", "N", 9, 0], ["SEPARATED", "N", 7, 0],
	... ["WIDOWED", "N", 8, 0], ["DIVORCED", "N", 8, 0], ["HSEHLD_1_M", "N", 8, 0],
	... ["HSEHLD_1_F", "N", 8, 0], ["MARHH_CHD", "N", 8, 0],
	... ["MARHH_NO_C", "N", 8, 0], ["MHH_CHILD", "N", 7, 0],
	... ["FHH_CHILD", "N", 7, 0], ["HSE_UNITS", "N", 9, 0], ["VACANT", "N", 7, 0],
	... ["OWNER_OCC", "N", 8, 0], ["RENTER_OCC", "N", 8, 0],
	... ["MEDIAN_VAL", "N", 7, 0], ["MEDIANRENT", "N", 4, 0],
	... ["UNITS_1DET", "N", 8, 0], ["UNITS_1ATT", "N", 7, 0], ["UNITS2", "N", 7, 0],
	... ["UNITS3_9", "N", 8, 0], ["UNITS10_49", "N", 8, 0],
	... ["UNITS50_UP", "N", 8, 0], ["MOBILEHOME", "N", 7, 0]]

You can get a list of the shapefile's records by calling the records() method:


	>>> records = sf.records()

	>>> len(records)
	663

To read a single record call the record() method with the record's index:


	>>> rec = sf.record(3)
	
Each record is a list-like Record object containing the values corresponding to each field in
the field list. A record's values can be accessed by positional indexing or slicing.
For example in the blockgroups shapefile the 2nd and 3rd fields are the blockgroup id 
and the 1990 population count of that San Francisco blockgroup:


	>>> rec[1:3]
	['060750601001', 4715]

For simpler access, the fields of a record can also accessed via the name of the field,
either as a key or as an attribute name. The blockgroup id (BKG_KEY) of the blockgroups shapefile 
can also be retrieved as:


    >>> rec['BKG_KEY']
    '060750601001'

    >>> rec.BKG_KEY
    '060750601001'
	
The record values can be easily integrated with other programs by converting it to a field-value dictionary:


	>>> dct = rec.as_dict()
	>>> sorted(dct.items())
	[('AGE_18_29', 1467), ('AGE_30_49', 1681), ('AGE_50_64', 92), ('AGE_5_17', 848), ('AGE_65_UP', 30), ('AGE_UNDER5', 597), ('AMERI_ES', 6), ('AREA', 2.34385), ('ASIAN_PI', 452), ('BKG_KEY', '060750601001'), ('BLACK', 1007), ('DIVORCED', 149), ('FEMALES', 2095), ('FHH_CHILD', 16), ('HISPANIC', 416), ('HOUSEHOLDS', 1195), ('HSEHLD_1_F', 40), ('HSEHLD_1_M', 22), ('HSE_UNITS', 1258), ('MALES', 2620), ('MARHH_CHD', 79), ('MARHH_NO_C', 958), ('MARRIED', 2021), ('MEDIANRENT', 739), ('MEDIAN_VAL', 337500), ('MHH_CHILD', 0), ('MOBILEHOME', 0), ('NEVERMARRY', 703), ('OTHER', 288), ('OWNER_OCC', 66), ('POP1990', 4715), ('POP90_SQMI', 2011.6), ('RENTER_OCC', 3733), ('SEPARATED', 49), ('UNITS10_49', 49), ('UNITS2', 160), ('UNITS3_9', 672), ('UNITS50_UP', 0), ('UNITS_1ATT', 302), ('UNITS_1DET', 43), ('VACANT', 93), ('WHITE', 2962), ('WIDOWED', 37)]

If at a later point you need to check the record's index position in the original 
shapefile, you can do this through the "oid" attribute:


	>>> rec.oid
	3
	
### Reading Geometry and Records Simultaneously

You may want to examine both the geometry and the attributes for a record at
the same time. The shapeRecord() and shapeRecords() method let you do just
that.

Calling the shapeRecords() method will return the geometry and attributes for
all shapes as a list of ShapeRecord objects. Each ShapeRecord instance has a
"shape" and "record" attribute. The shape attribute is a Shape object as
discussed in the first section "Reading Geometry". The record attribute is a
list-like object containing field values as demonstrated in the "Reading Records" section.


	>>> shapeRecs = sf.shapeRecords()

Let's read the blockgroup key and the population for the 4th blockgroup:


	>>> shapeRecs[3].record[1:3]
	['060750601001', 4715]

The results from the shapeRecords() method is a list-like object that can be easily converted
to GeoJSON through the _\_geo_interface\_\_:


	>>> shapeRecs.__geo_interface__['type']
	'FeatureCollection'

The shapeRecord() method reads a single shape/record pair at the specified index.
To get the 4th shape record from the blockgroups shapefile use the third index:


	>>> shapeRec = sf.shapeRecord(3)
	
Each individual shape record also supports the _\_geo_interface\_\_ to convert it to a GeoJSON:


	>>> shapeRec.__geo_interface__['type']
	'Feature'

The blockgroup key and population count:


	>>> shapeRec.record[1:3]
	['060750601001', 4715]
	

## Writing Shapefiles

### The Writer Class

PyShp tries to be as flexible as possible when writing shapefiles while
maintaining some degree of automatic validation to make sure you don't
accidentally write an invalid file.

PyShp can write just one of the component files such as the shp or dbf file
without writing the others. So in addition to being a complete shapefile
library, it can also be used as a basic dbf (xbase) library. Dbf files are a
common database format which are often useful as a standalone simple database
format. And even shp files occasionally have uses as a standalone format. Some
web-based GIS systems use an user-uploaded shp file to specify an area of
interest. Many precision agriculture chemical field sprayers also use the shp
format as a control file for the sprayer system (usually in combination with
custom database file formats).

To create a shapefile you begin by initiating a new Writer instance, passing it
the file path and name to save to:


	>>> w = shapefile.Writer('shapefiles/test/testfile')
	
File extensions are optional when reading or writing shapefiles. If you specify
them PyShp ignores them anyway. When you save files you can specify a base
file name that is used for all three file types. Or you can specify a name for
one or more file types:


	>>> w = shapefile.Writer(dbf='shapefiles/test/onlydbf.dbf')
	
In that case, any file types not assigned will not
save and only file types with file names will be saved. 

#### Writing Shapefiles Using the Context Manager

The "Writer" class automatically closes the open files and writes the final headers once it is garbage collected.
In case of a crash and to make the code more readable, it is nevertheless recommended 
you do this manually by calling the "close()" method: 


	>>> w.close()

Alternatively, you can also use the "Writer" class as a context manager, to ensure open file
objects are properly closed and final headers written once you exit the with-clause:


	>>> with shapefile.Writer("shapefiles/test/contextwriter") as shp:
	...		pass

#### Writing Shapefiles to File-Like Objects

Just as you can read shapefiles from python file-like objects you can also
write to them:


	>>> try:
	...     from StringIO import StringIO
	... except ImportError:
	...     from io import BytesIO as StringIO
	>>> shp = StringIO()
	>>> shx = StringIO()
	>>> dbf = StringIO()
	>>> w = shapefile.Writer(shp=shp, shx=shx, dbf=dbf)
	>>> w.field('field1', 'C')
	>>> w.record()
	>>> w.null()
	>>> w.close()
	>>> # To read back the files you could call the "StringIO.getvalue()" method later.
	
#### Setting the Shape Type

The shape type defines the type of geometry contained in the shapefile. All of
the shapes must match the shape type setting.

There are three ways to set the shape type: 
  * Set it when creating the class instance. 
  * Set it by assigning a value to an existing class instance. 
  * Set it automatically to the type of the first non-null shape by saving the shapefile.

To manually set the shape type for a Writer object when creating the Writer:


	>>> w = shapefile.Writer('shapefiles/test/shapetype', shapeType=3)

	>>> w.shapeType
	3

OR you can set it after the Writer is created:


	>>> w.shapeType = 1

	>>> w.shapeType
	1
	

### Adding Records

Before you can add records you must first create the fields that define what types of 
values will go into each attribute. 

There are several different field types, all of which support storing None values as NULL. 

Text fields are created using the 'C' type, and the third 'size' argument can be customized to the expected
length of text values to save space:


	>>> w = shapefile.Writer('shapefiles/test/dtype')
	>>> w.field('TEXT', 'C')
	>>> w.field('SHORT_TEXT', 'C', size=5)
	>>> w.field('LONG_TEXT', 'C', size=250)
	>>> w.null()
	>>> w.record('Hello', 'World', 'World'*50)
	>>> w.close()
	
	>>> r = shapefile.Reader('shapefiles/test/dtype')
	>>> assert r.record(0) == ['Hello', 'World', 'World'*50]

Date fields are created using the 'D' type, and can be created using either 
date objects, lists, or a YYYYMMDD formatted string. 
Field length or decimal have no impact on this type:


	>>> from datetime import date
	>>> w = shapefile.Writer('shapefiles/test/dtype')
	>>> w.field('DATE', 'D')
	>>> w.null()
	>>> w.null()
	>>> w.null()
	>>> w.null()
	>>> w.record(date(1898,1,30))
	>>> w.record([1998,1,30])
	>>> w.record('19980130')
	>>> w.record(None)
	>>> w.close()
	
	>>> r = shapefile.Reader('shapefiles/test/dtype')
	>>> assert r.record(0) == [date(1898,1,30)]
	>>> assert r.record(1) == [date(1998,1,30)]
	>>> assert r.record(2) == [date(1998,1,30)]
	>>> assert r.record(3) == [None]

Numeric fields are created using the 'N' type (or the 'F' type, which is exactly the same). 
By default the fourth decimal argument is set to zero, essentially creating an integer field. 
To store floats you must set the decimal argument to the precision of your choice. 
To store very large numbers you must increase the field length size to the total number of digits 
(including comma and minus). 


	>>> w = shapefile.Writer('shapefiles/test/dtype')
	>>> w.field('INT', 'N')
	>>> w.field('LOWPREC', 'N', decimal=2)
	>>> w.field('MEDPREC', 'N', decimal=10)
	>>> w.field('HIGHPREC', 'N', decimal=30)
	>>> w.field('FTYPE', 'F', decimal=10)
	>>> w.field('LARGENR', 'N', 101)
	>>> nr = 1.3217328
	>>> w.null()
	>>> w.null()
	>>> w.record(INT=nr, LOWPREC=nr, MEDPREC=nr, HIGHPREC=-3.2302e-25, FTYPE=nr, LARGENR=int(nr)*10**100)
	>>> w.record(None, None, None, None, None, None)
	>>> w.close()
	
	>>> r = shapefile.Reader('shapefiles/test/dtype')
	>>> assert r.record(0) == [1, 1.32, 1.3217328, -3.2302e-25, 1.3217328, 10000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000]
	>>> assert r.record(1) == [None, None, None, None, None, None]

	
Finally, we can create boolean fields by setting the type to 'L'. 
This field can take True or False values, or 1 (True) or 0 (False). 
None is interpreted as missing. 


	>>> w = shapefile.Writer('shapefiles/test/dtype')
	>>> w.field('BOOLEAN', 'L')
	>>> w.null()
	>>> w.null()
	>>> w.null()
	>>> w.null()
	>>> w.null()
	>>> w.null()
	>>> w.record(True)
	>>> w.record(1)
	>>> w.record(False)
	>>> w.record(0)
	>>> w.record(None)
	>>> w.record("Nonesense")
	>>> w.close()
	
	>>> r = shapefile.Reader('shapefiles/test/dtype')
	>>> r.record(0)
	Record #0: [True]
	>>> r.record(1)
	Record #1: [True]
	>>> r.record(2)
	Record #2: [False]
	>>> r.record(3)
	Record #3: [False]
	>>> r.record(4)
	Record #4: [None]
	>>> r.record(5)
	Record #5: [None]
	
You can also add attributes using keyword arguments where the keys are field names.


	>>> w = shapefile.Writer('shapefiles/test/dtype')
	>>> w.field('FIRST_FLD','C','40')
	>>> w.field('SECOND_FLD','C','40')
	>>> w.null()
	>>> w.null()
	>>> w.record('First', 'Line')
	>>> w.record(FIRST_FLD='First', SECOND_FLD='Line')
	>>> w.close()

### Adding Geometry

Geometry is added using one of several convenience methods. The "null" method is used
for null shapes, "point" is used for point shapes, "multipoint" is used for multipoint shapes, "line" for lines,
"poly" for polygons. 

**Adding a Null shape**

A shapefile may contain some records for which geometry is not available, and may be set using the "null" method. 
Because Null shape types (shape type 0) have no geometry the "null" method is called without any arguments. 


	>>> w = shapefile.Writer('shapefiles/test/null')
	>>> w.field('name', 'C')

	>>> w.null()
	>>> w.record('nullgeom')

	>>> w.close()

**Adding a Point shape**

Point shapes are added using the "point" method. A point is specified by an x and
y value. 


	>>> w = shapefile.Writer('shapefiles/test/point')
	>>> w.field('name', 'C')
	
	>>> w.point(122, 37) 
	>>> w.record('point1')
	
	>>> w.close()

**Adding a MultiPoint shape**

If your point data allows for the possibility of multiple points per feature, use "multipoint" instead. 
These are specified as a list of xy point coordinates. 


	>>> w = shapefile.Writer('shapefiles/test/multipoint')
	>>> w.field('name', 'C')
	
	>>> w.multipoint([[122,37], [124,32]]) 
	>>> w.record('multipoint1')
	
	>>> w.close()
	
**Adding a LineString shape**

For LineString shapefiles, each shape is given as a list of one or more linear features. 
Each of the linear features must have at least two points. 
	
	
	>>> w = shapefile.Writer('shapefiles/test/line')
	>>> w.field('name', 'C')
	
	>>> w.line([
	...			[[1,5],[5,5],[5,1],[3,3],[1,1]], # line 1
	...			[[3,2],[2,6]] # line 2
	...			])
	
	>>> w.record('linestring1')
	
	>>> w.close()
	
**Adding a Polygon shape**

Similarly to LineString, Polygon shapes consist of multiple polygons, and must be given as a list of polygons.
The main difference is that polygons must have at least 4 points and the last point must be the same as the first. 
It's also okay if you forget to repeat the first point at the end; PyShp automatically checks and closes the polygons
if you don't.

It's important to note that for Polygon shapefiles, your polygon coordinates must be ordered in a clockwise direction.
If any of the polygons have holes, then the hole polygon coordinates must be ordered in a counterclockwise direction.
The direction of your polygons determines how shapefile readers will distinguish between polygon outlines and holes. 


	>>> w = shapefile.Writer('shapefiles/test/polygon')
	>>> w.field('name', 'C')

	>>> w.poly([
	...	        [[122,37], [117,36], [115,32], [118,20], [113,24]], # poly 1
	...	        [[15,2], [17,6], [22,7]], # hole 1
	...         [[122,37], [117,36], [115,32]] # poly 2
	...        ])
	>>> w.record('polygon1')
	
	>>> w.close()
		
**Adding from an existing Shape object**

Finally, geometry can be added by passing an existing "Shape" object to the "shape" method.
You can also pass it any GeoJSON dictionary or _\_geo_interface\_\_ compatible object. 
This can be particularly useful for copying from one file to another:


	>>> r = shapefile.Reader('shapefiles/test/polygon')

	>>> w = shapefile.Writer('shapefiles/test/copy')
	>>> w.fields = r.fields[1:] # skip first deletion field

	>>> # adding existing Shape objects
	>>> for shaperec in r.iterShapeRecords():
	...     w.record(*shaperec.record)
	...     w.shape(shaperec.shape)
	
	>>> # or GeoJSON dicts
	>>> for shaperec in r.iterShapeRecords():
	...     w.record(*shaperec.record)
	...     w.shape(shaperec.shape.__geo_interface__)
	
	>>> w.close()	
	

### Geometry and Record Balancing

Because every shape must have a corresponding record it is critical that the
number of records equals the number of shapes to create a valid shapefile. You
must take care to add records and shapes in the same order so that the record
data lines up with the geometry data. For example:

	
	>>> w = shapefile.Writer('shapefiles/test/balancing', shapeType=shapefile.POINT)
	>>> w.field("field1", "C")
	>>> w.field("field2", "C")
	
	>>> w.record("row", "one")
	>>> w.point(1, 1)
	
	>>> w.record("row", "two")
	>>> w.point(2, 2)
	
To help prevent accidental misalignment PyShp has an "auto balance" feature to
make sure when you add either a shape or a record the two sides of the
equation line up. This way if you forget to update an entry the
shapefile will still be valid and handled correctly by most shapefile
software. Autobalancing is NOT turned on by default. To activate it set
the attribute autoBalance to 1 or True:


    >>> w.autoBalance = 1
	>>> w.record("row", "three")
	>>> w.record("row", "four")
	>>> w.point(4, 4)
	
	>>> w.recNum == w.shpNum
	True

You also have the option of manually calling the balance() method at any time
to ensure the other side is up to date. When balancing is used
null shapes are created on the geometry side or records
with a value of "NULL" for each field is created on the attribute side.
This gives you flexibility in how you build the shapefile.
You can create all of the shapes and then create all of the records or vice versa. 


    >>> w.autoBalance = 0
	>>> w.record("row", "five")
	>>> w.record("row", "six")
	>>> w.record("row", "seven")
	>>> w.point(5, 5)
	>>> w.point(6, 6)
	>>> w.balance()
	
	>>> w.recNum == w.shpNum
	True

If you do not use the autoBalance() or balance() method and forget to manually
balance the geometry and attributes the shapefile will be viewed as corrupt by
most shapefile software.
	


# How To's

## 3D and Other Geometry Types

Most shapefiles store conventional 2D points, lines, or polygons. But the shapefile format is also capable
of storing various other types of geometries as well, including complex 3D surfaces and objects. 

**Shapefiles with measurement (M) values**

Measured shape types are shapes that include a measurement value at each vertex, for instance
speed measurements from a GPS device. Shapes with measurement (M) values are added with the following
methods: "pointm", "multipointm", "linem", and "polygonm". The M-values are specified by adding a
third M value to each XY coordinate. Missing or unobserved M-values are specified with a None value,
or by simply omitting the third M-coordinate.


	>>> w = shapefile.Writer('shapefiles/test/linem')
	>>> w.field('name', 'C')
	
	>>> w.linem([
	...			[[1,5,0],[5,5],[5,1,3],[3,3,None],[1,1,0]], # line with one omitted and one missing M-value
	...			[[3,2],[2,6]] # line without any M-values
	...			])
	
	>>> w.record('linem1')
	
	>>> w.close()
	
Shapefiles containing M-values can be examined in several ways:

	>>> r = shapefile.Reader('shapefiles/test/linem')
	
	>>> r.mbox # the lower and upper bound of M-values in the shapefile
	[0.0, 3.0]
	
	>>> r.shape(0).m # flat list of M-values
	[0.0, None, 3.0, None, 0.0, None, None]

	
**Shapefiles with elevation (Z) values**

Elevation shape types are shapes that include an elevation value at each vertex, for instance elevation from a GPS device. 
Shapes with elevation (Z) values are added with the following methods: "pointz", "multipointz", "linez", and "polygonz". 
The Z-values are specified by adding a third Z value to each XY coordinate. Z-values do not support the concept of missing data,
but if you omit the third Z-coordinate it will default to 0. Note that Z-type shapes also support measurement (M) values added
as a fourth M-coordinate. This too is optional. 
	
	
	>>> w = shapefile.Writer('shapefiles/test/linez')
	>>> w.field('name', 'C')
	
	>>> w.linez([
	...			[[1,5,18],[5,5,20],[5,1,22],[3,3],[1,1]], # line with some omitted Z-values
	...			[[3,2],[2,6]], # line without any Z-values
	...			[[3,2,15,0],[2,6,13,3],[1,9,14,2]] # line with both Z- and M-values
	...			])
	
	>>> w.record('linez1')
	
	>>> w.close()
	
To examine a Z-type shapefile you can do:

	>>> r = shapefile.Reader('shapefiles/test/linez')
	
	>>> r.zbox # the lower and upper bound of Z-values in the shapefile
	[0.0, 22.0]
	
	>>> r.shape(0).z # flat list of Z-values
	[18.0, 20.0, 22.0, 0.0, 0.0, 0.0, 0.0, 15.0, 13.0, 14.0]

**3D MultiPatch Shapefiles**

Multipatch shapes are useful for storing composite 3-Dimensional objects. 
A MultiPatch shape represents a 3D object made up of one or more surface parts.
Each surface in "parts" is defined by a list of XYZM values (Z and M values optional), and its corresponding type is
given in the "partTypes" argument. The part type decides how the coordinate sequence is to be interpreted, and can be one 
of the following module constants: TRIANGLE_STRIP, TRIANGLE_FAN, OUTER_RING, INNER_RING, FIRST_RING, or RING.
For instance, a TRIANGLE_STRIP may be used to represent the walls of a building, combined with a TRIANGLE_FAN to represent 
its roof: 

	>>> from shapefile import TRIANGLE_STRIP, TRIANGLE_FAN
	
	>>> w = shapefile.Writer('shapefiles/test/multipatch')
	>>> w.field('name', 'C')
	
	>>> w.multipatch([
	...				 [[0,0,0],[0,0,3],[5,0,0],[5,0,3],[5,5,0],[5,5,3],[0,5,0],[0,5,3],[0,0,0],[0,0,3]], # TRIANGLE_STRIP for house walls
	...				 [[2.5,2.5,5],[0,0,3],[5,0,3],[5,5,3],[0,5,3],[0,0,3]], # TRIANGLE_FAN for pointed house roof
	...				 ],
	...				 partTypes=[TRIANGLE_STRIP, TRIANGLE_FAN]) # one type for each part
	
	>>> w.record('house1')
	
	>>> w.close()
	
For an introduction to the various multipatch part types and examples of how to create 3D MultiPatch objects see [this
ESRI White Paper](http://downloads.esri.com/support/whitepapers/ao_/J9749_MultiPatch_Geometry_Type.pdf). 

## Working with Large Shapefiles

Despite being a lightweight library, PyShp is designed to be able to read and write 
shapefiles of any size, allowing you to work with hundreds of thousands or even millions 
of records and complex geometries. 

When first creating the Reader class, the library only reads the header information
and leaves the rest of the file contents alone. Once you call the records() and shapes() 
methods however, it will attempt to read the entire file into memory at once. 
For very large files this can result in MemoryError. So when working with large files
it is recommended to use instead the iterShapes(), iterRecords(), or iterShapeRecords()
methods instead. These iterate through the file contents one at a time, enabling you to loop 
through them while keeping memory usage at a minimum. 


	>>> for shape in sf.iterShapes():
	...     # do something here
	...     pass
	
	>>> for rec in sf.iterRecords():
	...     # do something here
	...     pass
	
	>>> for shapeRec in sf.iterShapeRecords():
	...     # do something here
	...     pass

	>>> for shapeRec in sf: # same as iterShapeRecords()
	...     # do something here
	...     pass
	
The shapefile Writer class uses a similar streaming approach to keep memory 
usage at a minimum. The library takes care of this under-the-hood by immediately 
writing each geometry and record to disk the moment they 
are added using shape() or record(). Once the writer is closed, exited, or garbage 
collected, the final header information is calculated and written to the beginning of 
the file. 

This means that as long as you are able to iterate through a source file without having
to load everything into memory, such as a large CSV table or a large shapefile, you can 
process and write any number of items, and even merge many different source files into a single 
large shapefile. If you need to edit or undo any of your writing you would have to read the 
file back in, one record at a time, make your changes, and write it back out. 

## Unicode and Shapefile Encodings

PyShp has full support for unicode and shapefile encodings, so you can always expect to be working
with unicode strings in shapefiles that have text fields. 
Most shapefiles are written in UTF-8 encoding, PyShp's default encoding, so in most cases you don't 
have to specify the encoding. For reading shapefiles in any other encoding, such as Latin-1, just 
supply the encoding option when creating the Reader class. 


	>>> r = shapefile.Reader("shapefiles/test/latin1.shp", encoding="latin1")
	>>> r.record(0) == [2, u'Ñandú']
	True
	
Once you have loaded the shapefile, you may choose to save it using another more supportive encoding such 
as UTF-8. Provided the new encoding supports the characters you are trying to write, reading it back in 
should give you the same unicode string you started with. 


	>>> w = shapefile.Writer("shapefiles/test/latin_as_utf8.shp", encoding="utf8")
	>>> w.fields = r.fields[1:]
	>>> w.record(*r.record(0))
	>>> w.null()
	>>> w.close()
	
	>>> r = shapefile.Reader("shapefiles/test/latin_as_utf8.shp", encoding="utf8")
	>>> r.record(0) == [2, u'Ñandú']
	True
	
If you supply the wrong encoding and the string is unable to be decoded, PyShp will by default raise an
exception. If however, on rare occasion, you are unable to find the correct encoding and want to ignore
or replace encoding errors, you can specify the "encodingErrors" to be used by the decode method. This
applies to both reading and writing. 


	>>> r = shapefile.Reader("shapefiles/test/latin1.shp", encoding="ascii", encodingErrors="replace")
	>>> r.record(0) == [2, u'�and�']
	True

	
# Testing

The testing framework is doctest, which are located in this file README.md.
In the same folder as README.md and shapefile.py, from the command line run 
```
$ python shapefile.py
``` 

Linux/Mac and similar platforms will need to run `$ dos2unix README.md` in order
correct line endings in README.md.

# Contributors

```
Atle Frenvik Sveen
Bas Couwenberg
Casey Meisenzahl
Charles Arnold
David A. Riggs
davidh-ssec
Evan Heidtmann
ezcitron
geospatialpython
Hannes
Ignacio Martinez Vazquez
Jason Moujaes
Karim Bahgat
Kyle Kelley
Louis Tiao
Marcin Cuprjak
Micah Cochran
Michael Davis
Michal Čihař
Mike Toews
Nilo
pakoun
Paulo Ernesto
Raynor Vliegendhart
Razzi Abuissa
Ross Rogers
Ryan Brideau
Tobias Megies
Tommi Penttinen
Uli Köhler
Zac Miller
```
