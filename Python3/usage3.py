"""

Python Shapefile Library
========================
:Author: Joel Lawhead <jlawhead@geospatialpython.com>
:Revised: January 31, 2011

Overview
--------

The Python Shapefile Library (PSL) 3 provides read and write support for the ESRI
Shapefile format in Python 3. The Shapefile format is a popular Geographic Information
System vector data format.

The library was originally developed in Python 2.  This library is a "hasty" port to
Python 3.  The major difference is the convienience "Editor" class is not available
in the Python 3 compatible version.  This difference is a minor issue as the Reader
and Writer class are functional.  The Python 3 version of the library passes the 
doctests but has not been tested much beyond that.  Bug reports are welcome.

This document provides usage examples for using the Python Shapefile Library.

Examples
--------

Before doing anything you must import PSL.

>>> import shapefile

The examples below will use a shapefile created from the U.S. Census Bureau
Blockgroups data set near San Francisco, CA.

Reading Shapefiles
..................

To read a shapefile create a new "Reader" object and pass it the name of an 
existing shapefile. The shapefile format is acutally a collection of three
files. You specify the base filename of the shapefile or the complete filename 
of any of the shapefile component files.

>>> sf = shapefile.Reader("shapefiles/blockgroups")


OR

>>> sf = shapefile.Reader("shapefiles/blockgroups.shp")


OR

>>> sf = shapefile.Reader("shapefiles/blockgroups.dbf")


OR any of the other 5+ formats which are potentially part of a shapefile.

Reading Geometry
++++++++++++++++

A shapefile's geometry is the collection of points or shapes made from verticies 
and implied arcs representing physical locations.  All types of shapefiles
just store points.  The metadata about the points determine how they are handled by
software.

You can get the a list of the shapefile's geometry by calling the shapes()
method. 

>>> shapes = sf.shapes()

The shapes method returns a list of Shape objects describing the 
geometry of each shape record.

>>> len(shapes)
663

Each shape record contains the following attributes:

>>> dir(shapes[3]) #doctest: +NORMALIZE_WHITESPACE
['__class__', '__delattr__', '__dict__', '__doc__', '__eq__', '__format__', '__ge__', '__getattribute__', '__gt__', '__hash__', '__init__', '__le__', '__lt__', '__module__', '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', '__str__', '__subclasshook__', '__weakref__', 'bbox', 'parts', 'points', 'shapeType']

 - shapeType: an integer representing the type of shape as defined by the
   shapefile specification.

>>> shapes[3].shapeType
5

 - bbox: If the shape type contains multiple points this tuple describes the 
   upper left (x,y) coordinate and lower right corner coordinate creating a 
   complete box around the points. If the shapeType is a Null 
   (shapeType == 0) then an AttributeError is raised.
 
>>> shapes[3].bbox
[-122.485792, 37.786931, -122.446285, 37.811019]
 
 - parts: Parts simply group collections of points into shapes. If the shape record 
   has multiple parts this attribute contains the index of the first point of each part. 
   If there is only one part then a list containing 0 is returned.  
 
>>> shapes[3].parts
[0]
  
 - points: The points attribute contains a list of tuples containing an (x,y)
   coordinate for each point in the shape.
 
>>> len(shapes[3].points)
173
>>> shapes[3].points[7]
[-122.471063, 37.787403]

To read a single shape by calling its index use the shape() method. The index
is the shape's count from 0. So to read the 8th shape record you would
use its index which is 7.

>>> s = sf.shape(7)

>>> s.bbox
[-122.449637, 37.80149, -122.442109, 37.807958]

Reading Records
................

A record in a shapefile contains the attributes for each shape in the 
collection of geometry. Records are stored in the dbf file. The link
between geometry and attributes is the foundation of Geographic Information
Systems. This critical link is implied by the order of shapes and 
corresponding records in the shp geometry file and the dbf attribute file.

The field names of a shapefile are available as soon as you read a shapefile. 
You can call the "fields" attribute of the shapefile as a Python list. Each 
field is a Python list with the following information:

- Field name: the name describing the data at this column index.
	
- Field type: the type of data at this column index. Types can be: Character, Numbers, Longs, Dates, or Memo.
  The "Memo" type has no meaning within a GIS and is part of the xbase spec instead.
	
- Field length: the length of the data found at this column index.  Older GIS software may truncate this
  length to 8 or 11 characters for "Character" fields.
	
- Decimal length: the number of decimal places found in "Number" fields.
	
To see the fields for the Reader object above (sf) call the "fields" attribute:

>>> fields = sf.fields

>>> assert fields == [('DeletionFlag', 'C', 1, 0), [b'AREA', b'N', 18, 5],
... [b'BKG_KEY', b'C', 12, 0],
... [b'POP1990', b'N', 9, 0], [b'POP90_SQMI', b'N', 10, 1], [b'HOUSEHOLDS', b'N', 9, 0],
... [b'MALES', b'N', 9, 0], [b'FEMALES', b'N', 9, 0], [b'WHITE', b'N', 9, 0],
... [b'BLACK', b'N', 8, 0], [b'AMERI_ES', b'N', 7, 0], [b'ASIAN_PI', b'N', 8, 0], 
... [b'OTHER', b'N', 8, 0], [b'HISPANIC', b'N', 8, 0], [b'AGE_UNDER5', b'N', 8, 0], 
... [b'AGE_5_17', b'N', 8, 0], [b'AGE_18_29', b'N', 8, 0], [b'AGE_30_49', b'N', 8, 0],
... [b'AGE_50_64', b'N', 8, 0], [b'AGE_65_UP', b'N', 8, 0], [b'NEVERMARRY', b'N', 8, 0],
... [b'MARRIED', b'N', 9, 0], [b'SEPARATED', b'N', 7, 0], [b'WIDOWED', b'N', 8, 0],
... [b'DIVORCED', b'N', 8, 0], [b'HSEHLD_1_M', b'N', 8, 0], [b'HSEHLD_1_F', b'N', 8, 0],
... [b'MARHH_CHD', b'N', 8, 0], [b'MARHH_NO_C', b'N', 8, 0], [b'MHH_CHILD', b'N', 7, 0],
... [b'FHH_CHILD', b'N', 7, 0], [b'HSE_UNITS', b'N', 9, 0], [b'VACANT', b'N', 7, 0],
... [b'OWNER_OCC', b'N', 8, 0], [b'RENTER_OCC', b'N', 8, 0], [b'MEDIAN_VAL', b'N', 7, 0],
... [b'MEDIANRENT', b'N', 4, 0], [b'UNITS_1DET', b'N', 8, 0],
... [b'UNITS_1ATT', b'N', 7, 0], [b'UNITS2', b'N', 7, 0], [b'UNITS3_9', b'N', 8, 0],
... [b'UNITS10_49', b'N', 8, 0], [b'UNITS50_UP', b'N', 8, 0], [b'MOBILEHOME', b'N', 7, 0]]

You can get a list of the shapefile's records by calling the records() method:

>>> records = sf.records()

>>> len(records)
663

Each record is a list containing an attribute corresponding to each field in the
field list.

For example in the 4th record of the blockgroups shapefile the 2nd and 3rd 
fields are the blockgroup id and the 1990 population count of 
that San Francisco blockgroup:

>>> records[3][1:3]
[b'060750601001', 4715]

To read a single record call the record() method with the record's index:

>>> rec = sf.record(3)

>>> rec[1:3]
[b'060750601001', 4715]

Reading Geometry and Records Simultaneously
...........................................

You way want to examine both the geometry and the attributes for a record at the
same time. The shapeRecord() and shapeRecords() method let you do just that.

Calling the shapeRecords() method will return the geometry and attributes for
all shapes as a list of ShapeRecord objects. Each ShapeRecord instance has a
"shape" and "record" attribute. The shape attribute is a ShapeRecord object as
dicussed in the first section "Reading Geometry". The record attribute is a
list of field values as demonstrated in the "Reading Records" section.

>>> shapeRecs = sf.shapeRecords()

Let's read the blockgroup key and the population for the 4th blockgroup:
>>> shapeRecs[3].record[1:3]
[b'060750601001', 4715]

Now let's read the first two points for that same record:

>>> points = shapeRecs[3].shape.points[0:2]

>>> len(points)
2

The shapeRec() method reads a single shape/record pair at the specified index.
To get the 4th shape record from the blockgroups shapfile use the third index:

>>> shapeRec = sf.shapeRecord(3)

The blockgroup key and population count:

>>> shapeRec.record[1:3]
[b'060750601001', 4715]

>>> points = shapeRec.shape.points[0:2]

>>> len(points)
2

Writing Shapefiles
------------------

The PSL tries to be as flexible as possible when writing shapefiles while 
maintaining some degree of automatic validation to make sure you don't 
accidentally write an invalid file.

The PSL can write just one of the component files such as the shp or dbf file
without writing the others. So in addition to being a complete 
shapefile library, it can also be used as a basic dbf (xbase) library. Dbf files are
a common database format which are often useful as a standalone simple 
database format. And even shp files occasionaly have uses as a standalone 
format. Some web-based GIS systems use an user-uploaded shp file to specify
an area of interest. Many precision agriculture chemical field sprayers also
use the shp format as a control file for the sprayer system (usually in 
combination with custom database file formats).

To create a shapefile you add geometry and/or attributes using methods in the 
Writer class until you are ready to save the file.

Create an instance of the Writer class to begin creating a shapefile:

>>> w = shapefile.Writer()


Setting the Shape Type
......................

The shape type defines the type of geometry contained in the shapefile. All of
the shapes must match the shape type setting. 

Shape types are represented by numbers between 0 and 31 as defined by the 
shapefile specification. It is important to note that numbering system has 
several reserved numbers which have not been used yet therefore the numbers of 
the existing shape types are not sequential.

There are three ways to set the shape type: 
- Set it when creating the class instance.
- Set it by assigning a value to an existing class instance.
- Set it automatically to the type of the first shape by saving the shapefile.
	  
To manually set the shape type for a Writer object when creating the Writer:

>>> w = shapefile.Writer(shapeType=1)

>>> w.shapeType
1

OR you can set it after the Writer is created:

>>> w.shapeType = 3

>>> w.shapeType
3

Geometry and Record Balancing
.............................

Because every shape must have a corresponding record it is critical that the
number of records equals the number of shapes to create a valid shapefile. To
help prevent accidental misalignment the PSL has an "auto balance" feature to
make sure when you add either a shape or a record the two sides of the 
equation line up. This feature is NOT turned on by default. To activate it
set the attribute autoBalance to 1 (True):

>>> w.autoBalance = 1

You also have the option of manually calling the balance() method each time you
add a shape or a record to ensure the other side is up to date.  When balancing
is used null shapes are created on the geometry side or a record with a value of
"NULL" for each field is created on the attribute side.

The balancing option gives you flexibility in how you build the shapefile. 

Without auto balancing you can add geometry or records at anytime. You can
create all of the shapes and then create all of the records or vice versa. You
can use the balance method after creating a shape or record each time and make 
updates later. If you do not use the balance method and forget to manually
balance the geometry and attributes the shapefile will be viewed as corrupt by
most shapefile software.

With auto balanacing you can add either shapes or geometry and update blank
entries on either side as needed. Even if you forget to update an entry the
shapefile will still be valid and handled correctly by most shapefile software.

Adding Geometry
...............

Geometry is added using one of three methods: "null", "point", or "poly". The "null" 
method is used for null shapes, "point" is used for point shapes, and "poly" is
used for everything else.

**Adding a Null shape**

Because Null shape types (shape type 0) have no geometry the "null" method is
called without any arguments. 

>>> w = shapefile.Writer()

>>> w.null()

The writer object's shapes list will now have one null shape:

>>> assert w.shapes()[0].shapeType == shapefile.NULL

**Adding a Point shape**

Point shapes are added using the "point" method. A point is specified by an 
x, y, and optional z (elevation) and m (measure) value.

>>> w = shapefile.Writer()

>>> w.point(122, 37) # No elevation or measure values

>>> w.shapes()[0].points
[[122, 37, 0, 0]]

>>> w.point(118, 36, 4, 8)

>>> w.shapes()[1].points
[[118, 36, 4, 8]]

**Adding a Poly shape**

"Poly" shapes can be either polygons or lines.  Shapefile polygons must have at
least 5 points and the last point must be the same as the first (i.e. you can't
have a triangle accoring to the shapefile specification even though many popular
GIS programs support such shapefiles.) A line must have at least two points.
Because of the similarities between these two shape types they are created using
a single method called "poly".

>>> w = shapefile.Writer()

>>> w.poly(shapeType=3, parts=[[[122,37,4,9], [117,36,3,4]], [[115,32,8,8], 
... [118,20,6,4], [113,24]]])

Creating Attributes
...................

Creating attributes involves two steps. Step 1 is to create fields to contain
attribute values and step 2 is to populate the fields with values for each
shape record.

The following attempts to create a complete shapefile:
    
>>> w = shapefile.Writer(shapefile.POINT)
>>> w.point(1,1)
>>> w.point(3,1)
>>> w.point(4,3)
>>> w.point(2,2)
>>> w.field('FIRST_FLD')
>>> w.field('SECOND_FLD','C','40')
>>> w.record('First','Point')
>>> w.record('Second','Point')
>>> w.record('Third','Point')
>>> w.record('Fourth','Point')
>>> w.save('shapefiles/test/point')

>>> w = shapefile.Writer(shapefile.POLYGON)
>>> w.poly(parts=[[[1,5],[5,5],[5,1],[3,3],[1,1]]])
>>> w.field('FIRST_FLD','C','40')
>>> w.field('SECOND_FLD','C','40')
>>> w.record('First','Polygon')
>>> w.save('shapefiles/test/polygon')

>>> w = shapefile.Writer(shapefile.POLYLINE)
>>> w.line(parts=[[[1,5],[5,5],[5,1],[3,3],[1,1]]])
>>> w.poly(parts=[[[1,3],[5,3]]], shapeType=shapefile.POLYLINE)
>>> w.field('FIRST_FLD','C','40')
>>> w.field('SECOND_FLD','C','40')
>>> w.record('First','Line')
>>> w.record('Second','Line')
>>> w.save('shapefiles/test/line')

You can also add attributes using keyword arguments where the keys are field names.

>>> w = shapefile.Writer(shapefile.POLYLINE)
>>> w.line(parts=[[[1,5],[5,5],[5,1],[3,3],[1,1]]])
>>> w.field('FIRST_FLD','C','40')
>>> w.field('SECOND_FLD','C','40')
>>> w.record(FIRST_FLD='First', SECOND_FLD='Line')
>>> w.save('shapefiles/test/line')

"""