# PyShp

Python Shapefile库（pyshp）在纯Python中读取和写入ESRI Shapefile。

[![pyshp标志](https://camo.githubusercontent.com/25258962964f6cdda9cf1d702a0780f88315970c/687474703a2f2f342e62702e626c6f6773706f742e636f6d2f5f53426933375145734376672f545051754f686c485178492f41414141414141414145302f516a466c57664d783074512f533335302f4753505f4c6f676f2e706e67)](https://camo.githubusercontent.com/25258962964f6cdda9cf1d702a0780f88315970c/687474703a2f2f342e62702e626c6f6773706f742e636f6d2f5f53426933375145734376672f545051754f686c485178492f41414141414141414145302f516a466c57664d783074512f533335302f4753505f4c6f676f2e706e67)

[![建立状态](https://camo.githubusercontent.com/88958adbeaf9694e1305529af3505a71bb3b85ac/68747470733a2f2f7472617669732d63692e6f72672f47656f7370617469616c507974686f6e2f70797368702e7376673f6272616e63683d6d6173746572)](https://travis-ci.org/GeospatialPython/pyshp)

## 内容

[概观](https://github.com/GeospatialPython/pyshp#overview)

[例子](https://github.com/GeospatialPython/pyshp#examples)

- 阅读Shapefiles
  - [从文件对象读取Shapefile](https://github.com/GeospatialPython/pyshp#reading-shapefiles-from-file-like-objects)
  - [读取Shapefile元数据](https://github.com/GeospatialPython/pyshp#reading-shapefile-meta-data)
  - [阅读几何](https://github.com/GeospatialPython/pyshp#reading-geometry)
  - [阅读记录](https://github.com/GeospatialPython/pyshp#reading-records)
  - [同时阅读几何和记录](https://github.com/GeospatialPython/pyshp#reading-geometry-and-records-simultaneously)
- 写形状文件
  - [设置形状类型](https://github.com/GeospatialPython/pyshp#setting-the-shape-type)
  - [几何和记录平衡](https://github.com/GeospatialPython/pyshp#geometry-and-record-balancing)
  - [添加几何](https://github.com/GeospatialPython/pyshp#adding-geometry)
  - [添加记录](https://github.com/GeospatialPython/pyshp#adding-records)
  - [文件名](https://github.com/GeospatialPython/pyshp#file-names)
  - [保存到类文件对象](https://github.com/GeospatialPython/pyshp#saving-to-file-like-objects)
- [Python Geo界面](https://github.com/GeospatialPython/pyshp#python-geo-interface)
- [使用大的Shapefile](https://github.com/GeospatialPython/pyshp#working-with-large-shapefiles)
- [Unicode和Shapefile编码](https://github.com/GeospatialPython/pyshp#unicode-and-shapefile-encodings)

[测试](https://github.com/GeospatialPython/pyshp#testing)

# 概观

Python Shapefile库（pyshp）为Esri Shapefile格式提供读写支持。Shapefile格式是Esri创建的受欢迎的地理信息系统向量数据格式。有关此格式的更多信息，请阅读位于[http://www.esri.com/library/whitepapers/p dfs / shapefile.pdf](http://www.esri.com/library/whitepapers/pdfs/shapefile.pdf)的精心编写的“ESRI Shapefile技术描述 - 1998年7月” 。Esri文档描述了shp和shx文件格式。但是也需要第三种称为dbf的文件格式。这种格式在Web上记录为“XBase文件格式描述”，是一种在20世纪60年代创建的一种简单的基于文件的数据库格式。有关本规范的更多信息，请参阅：[ [http://www.clicketyclick.dk/databases/xbase/format/index.html\]（](http://www.clicketyclick.dk/databases/xbase/format/index.html]()[http：//www.clicketyclick.d](http://www.clicketyclick.d/) K /数据库/ XBASE /格式/ index.html中）

Esri和XBase文件格式在设计和内存有效性方面都非常简单，这是造型文件格式仍然流行的原因之一，尽管目前存在和交换GIS数据的方法很多。

Pyshp与Python 2.7-3.x兼容。

本文档提供了使用pyshp读写shapefile的示例。然而，更多的例子不断添加到GitHub，博客[http://GeospatialPython.com](http://geospatialpython.com/)上的pyshp wiki中，并在[https://gis.stackexchange.com](https://gis.stackexchange.com/)上搜索pyshp 。

目前，示例中引用的示例普查块组shapefile可以在GitHub项目站点 [https://github.com/GeospatialPython/pyshp上找到](https://github.com/GeospatialPython/pyshp)。这些例子是直截了当的，您也可以轻松地对自己的shapefile进行最小修改。

重要提示：如果您是GIS的新手，请阅读有关地图预测的信息。请访问：[https](https://github.com/GeospatialPython/pyshp/wiki/Map-Projections)：[//github.com/GeospatialPython/pyshp/wiki/Map-Projections](https://github.com/GeospatialPython/pyshp/wiki/Map-Projections)

我真诚地希望这个图书馆消除了简单的阅读和写入数据的平凡分心，让您专注于地理空间项目的挑战性和FUN部分。

# 例子

在做任何事情之前，你必须导入库。

```
>>> import shapefile

```

以下示例将使用由美国旧金山附近的美国人口普查局Blockgroups数据集创建的shapefile，并可在pyshp GitHub站点的git仓库中使用。

## 阅读Shapefiles

要读取shapefile，创建一个新的“Reader”对象，并传递一个现有shapefile的名称。shapefile格式实际上是三个文件的集合。指定shapefile的基本文件名或任何shapefile组件文件的完整文件名。

```
>>> sf = shapefile.Reader("shapefiles/blockgroups")

```

要么

```
>>> sf = shapefile.Reader("shapefiles/blockgroups.shp")

```

要么

```
>>> sf = shapefile.Reader("shapefiles/blockgroups.dbf")

```

或任何其他可能是shapefile的一部分的5种格式。该库不关心文件扩展名。

### 从文件对象读取Shapefile

您还可以使用关键字参数从任何类似Python文件的对象加载shapefile，以指定三个文件中的任何一个。此功能非常强大，允许您从URL，zip文件，序列化对象或某些情况下加载数据库中的shapefile。

```
>>> myshp = open("shapefiles/blockgroups.shp", "rb")
>>> mydbf = open("shapefiles/blockgroups.dbf", "rb")
>>> r = shapefile.Reader(shp=myshp, dbf=mydbf)

```

注意在上面的例子中，从不使用shx文件。shx文件是shp文件中可变长度记录的非常简单的固定记录索引。此文件是可选的阅读。如果可用，pyshp将使用shx文件访问形状记录一点点，但如果没有它，它会做得很好。

### 读取Shapefile元数据

Shapefile具有检查文件内容的许多属性。shapefile是特定类型的几何体的容器，可以使用shapeType属性来检查它。

```
>>> sf.shapeType
5

```

形状类型由0到31之间的数字表示，由shapefile规范定义并列在下面。重要的是要注意，编号系统有几个保留号码尚未使用，因此现有形状类型的编号不是顺序的：

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

基于此，我们可以看到我们的blockgroups shapefile包含多边形类型形状。形状类型也被定义为shapefile模块中的常量，因此我们可以更直观地比较类型：

```
>>> sf.shapeType == shapefile.POLYGON
True

```

我们可以检查的其他元数据片段包括特征数量，或shapefile涵盖的边界区域：

```
>>> len(sf)
663
>>> sf.bbox
[-122.515048, 37.652916, -122.327622, 37.863433]

```

### 阅读几何

shapefile的几何是由顶点和表示物理位置的隐含弧形成的点或形状的集合。所有类型的形状文件只存储点数。关于点的元数据决定了它们如何被软件处理。

您可以通过调用shapes（）方法获取shapefile几何的列表。

```
>>> shapes = sf.shapes()

```

Shape方法返回描述每个形状记录几何的Shape对象列表。

```
>>> len(shapes)
663

```

每个形状记录包含以下属性：

```
>>> for name in dir(shapes[3]):
...     if not name.startswith('__'):
...         name
'bbox'
'parts'
'points'
'shapeType'
```

- shapeType：表示shapefile规范定义的形状类型的整数。

  ```
  >>> shapes[3].shapeType
  5

  ```

- bbox：如果形状类型包含多个点，则该元组描述左下角（x，y）坐标和右上角坐标，围绕点创建一个完整的框。如果shapeType为Null（shapeType == 0），则引发AttributeError。

  ```
  >>> # Get the bounding box of the 4th shape.
  >>> # Round coordinates to 3 decimal places
  >>> bbox = shapes[3].bbox
  >>> ['%.3f' % coord for coord in bbox]
  ['-122.486', '37.787', '-122.446', '37.811']

  ```

- parts：零件简单地将点集合成形。如果形状记录具有多个部分，则此属性包含每个部分的第一个点的索引。如果只有一部分，则返回包含0的列表。

  ```
  >>> shapes[3].parts
  [0]
  ```

- points：点属性包含一个元组列表，其中包含形状中每个点的（x，y）坐标。

  ```
  >>> len(shapes[3].points)
  173
  >>> # Get the 8th point of the fourth shape
  >>> # Truncate coordinates to 3 decimal places
  >>> shape = shapes[3].points[7]
  >>> ['%.3f' % coord for coord in shape]
  ['-122.471', '37.787']

  ```

要通过调用其索引来读取单个形状，请使用shape（）方法。索引是从0的形状计数。因此，要读取第8个形状记录，您将使用其索引为7。

```
>>> s = sf.shape(7)

>>> # Read the bbox of the 8th shape to verify
>>> # Round coordinates to 3 decimal places
>>> ['%.3f' % coord for coord in s.bbox]
['-122.450', '37.801', '-122.442', '37.808']

```

### 阅读记录

shapefile中的记录包含几何集合中每个形状的属性。记录存储在dbf文件中。几何和属性之间的联系是所有地理信息系统的基础。该关键链接由shp几何文件和dbf属性文件中的形状和相应记录的顺序所暗示。

只要您读取shapefile，shapefile的字段名称就可用。您可以将shapefile的“fields”属性称为Python列表。每个字段都是一个包含以下信息的Python列表：

- Field name：描述此列索引处的数据的名称。
- Field type：此列索引处的数据类型。类型可以是：字符，数字，长号，日期或备忘录。“备忘录”类型在GIS中没有意义，而是xbase规范的一部分。
- Field length：在此列索引处找到的数据的长度。较旧的GIS软件可能将此长度缩短为“Character”字段的8或11个字符。
- 十进制长度：在“数字”字段中找到的小数位数。

要查看上面的Reader对象的字段（sf），请调用“fields”属性：

```
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

```

您可以通过调用records（）方法获取shapefile记录的列表：

```
>>> records = sf.records()

>>> len(records)
663

```

每个记录是包含与字段列表中每个字段相对应的属性的列表。

例如在blockgroups shapefile的第四个记录中，第二和第三个字段是该旧金山块组的块组ID和1990年的人口数：

```
>>> records[3][1:3]
['060750601001', 4715]
```

要使用记录的索引读取单个记录调用record（）方法：

```
>>> rec = sf.record(3)

>>> rec[1:3]
['060750601001', 4715]

```

### 同时阅读几何和记录

您可能需要同时检查记录的几何和属性。shapeRecord（）和shapeRecords（）方法可以让你做到这一点。

调用shapeRecords（）方法将返回所有形状的几何和属性作为ShapeRecord对象的列表。每个ShapeRecord实例都有一个“形状”和“记录”属性。shape属性是ShapeRecord对象，如第一节“阅读几何”中所述。记录属性是字段值的列表，如“读取记录”部分所示。

```
>>> shapeRecs = sf.shapeRecords()

```

我们来看看Blockgroup的密钥和第4个blockgroup的群体：

```
>>> shapeRecs[3].record[1:3]
['060750601001', 4715]

```

现在让我们看看同一条记录的前两点：

```
>>> points = shapeRecs[3].shape.points[0:2]

>>> len(points)
2

```

shapeRecord（）方法在指定的索引处读取单个形状/记录对。要从blockgroups shapefile获取第四个形状记录，请使用第三个索引：

```
>>> shapeRec = sf.shapeRecord(3)

```

块组密钥和人口数：

```
>>> shapeRec.record[1:3]
['060750601001', 4715]

>>> points = shapeRec.shape.points[0:2]

>>> len(points)
2

```

## 写形状文件

PyShp尝试在编写shapefile时尽可能灵活，同时保持一定程度的自动验证，以确保不会意外写入无效文件。

PyShp只能编写其中一个组件文件，如shp或dbf文件，而无需编写其他文件。所以除了是一个完整的shapefile库外，它也可以用作一个基本的dbf（xbase）库。Dbf文件是一种常见的数据库格式，通常用作独立的简单数据库格式。甚至shp文件偶尔也可以用作独立的格式。一些基于Web的GIS系统使用用户上传的shp文件来指定感兴趣的区域。许多精密农业化学喷雾器也使用shp格式作为喷雾器系统的控制文件（通常与定制的数据库文件格式组合）。

要创建一个shapefile，您可以使用Writer类中的方法添加几何体和/或属性，直到您准备好保存文件。

创建Writer类的实例以开始创建shapefile：

```
>>> w = shapefile.Writer()

```

### 设置形状类型

形状类型定义shapefile中包含的几何类型。所有形状必须与形状类型设置相匹配。

设置形状类型有三种方式：

- 在创建类实例时设置它。
- 通过将值分配给现有的类实例来设置它。
- 通过保存shapefile将其自动设置为第一个非空形状的类型。

在创建Writer时手动设置Writer对象的形状类型：

```
>>> w = shapefile.Writer(shapeType=3)

>>> w.shapeType
3

```

或者您可以在创建Writer后设置它：

```
>>> w.shapeType = 1

>>> w.shapeType
1

```

### 几何和记录平衡

因为每个形状都必须有一个对应的记录，记录数等于创建一个有效的形状文件的形状数量是至关重要的。您必须注意以相同的顺序添加记录和形状，以便记录数据与几何数据对齐。例如：

```
>>> w = shapefile.Writer(shapeType=shapefile.POINT)
>>> w.field("field1", "C")
>>> w.field("field2", "C")

>>> w.record("row", "one")
>>> w.point(1, 1)

>>> w.record("row", "two")
>>> w.point(2, 2)

```

为了防止意外的错位，pyshp有一个“自动平衡”功能，以确保当您添加形状或记录时，方程式的两边排列。这样，如果您忘记更新条目，shapefile将仍然是有效的，并被大多数shapefile软件正确处理。默认情况下，Autobalancing尚未打开。要激活它，将属性autoBalance设置为1或True：

```
>>> w.autoBalance = 1
>>> w.record("row", "three")
>>> w.record("row", "four")
>>> w.point(4, 4)

>>> w.recNum == w.shpNum
True

```

您还可以随时手动调用balance（）方法，以确保对方是最新的。当使用平衡时，在几何面上创建零形状，或者在属性侧创建每个字段的值为“NULL”的记录。这使您可以灵活地构建shapefile。您可以创建所有形状，然后创建所有记录，反之亦然。

```
>>> w.autoBalance = 0
>>> w.record("row", "five")
>>> w.record("row", "six")
>>> w.record("row", "seven")
>>> w.point(5, 5)
>>> w.point(6, 6)
>>> w.balance()

>>> w.recNum == w.shpNum
True

```

如果您不使用自动平衡或平衡方法，并忘记手动平衡几何和属性，shapefile将被大多数shapefile软件视为损坏。

### 添加几何

使用几种方便方法之一添加几何。“null”方法用于零形状，“point”用于点形状，“line”用于线，“poly”用于多边形等。

**添加点形状**

点形状使用“点”方法添加。一个点由x，y值指定。如果shapeType为PointZ或PointM，则可以设置可选的z（高程）和m（度量）值。

```
>>> w = shapefile.Writer()
>>> w.field('name', 'C')

>>> w.point(122, 37) 
>>> w.record('point1')

>>> w.save('shapefiles/test/point')

```

**添加多边形形状**

Shapefile多边形必须至少有4个点，最后一个点必须与第一个点相同。PyShp自动执行封闭的多边形。

```
>>> w = shapefile.Writer()
>>> w.field('name', 'C')

>>> w.poly(parts=[[[122,37,4,9], [117,36,3,4]], [[115,32,8,8],
... [118,20,6,4], [113,24]]])
>>> w.record('polygon1')

>>> w.save('shapefiles/test/polygon')
```

**添加线条形状**

一条线必须至少有两点。由于多边形和线型之间的相似性，可以使用“线”或“聚”方法创建线形。

```
>>> w = shapefile.Writer()
>>> w.field('name', 'C')

>>> w.line(parts=[[[1,5],[5,5],[5,1],[3,3],[1,1]]])
>>> w.poly(parts=[[[1,3],[5,3]]], shapeType=shapefile.POLYLINE)

>>> w.record('line1')
>>> w.record('line2')

>>> w.save('shapefiles/test/line')

```

**添加一个空的形状**

因为Null形状类型（形状类型0）没有几何，所以没有任何参数调用“null”方法。这种形状文件很少使用，但它是有效的。

```
>>> w = shapefile.Writer()
>>> w.field('name', 'C')

>>> w.null()
>>> w.record('nullgeom')

>>> w.save('shapefiles/test/null')

```

**从现有的Shape对象添加**

最后，可以通过将现有的“Shape”对象传递给“shape”方法来添加几何。这对于从一个文件复制到另一个文件可能特别有用：

```
>>> r = shapefile.Reader('shapefiles/test/polygon')

>>> w = shapefile.Writer()
>>> w.fields = r.fields[1:] # skip first deletion field

>>> for shaperec in r.iterShapeRecords():
...     w.record(*shaperec.record)
...     w.shape(shaperec.shape)

>>> w.save('shapefiles/test/copy')

```

### 添加记录

添加记录属性涉及两个步骤。步骤1是创建字段以包含属性值，步骤2是使用每个形状记录的值填充字段。

有几种不同的字段类型，它们都支持将None值存储为NULL。

使用“C”类型创建文本字段，第三个“size”参数可以自定义为文本值的预期长度以节省空间, 注意 中文字符在utf-8编码中占2到3个字节，这里的size 为字节码的大小。超过size字节部分，会被截断，在定义长度时候，请自行衡量：



```python
>>> w = shapefile.Writer()
>>> w.field('TEXT', 'C')
>>> w.field('SHORT_TEXT', 'C', size=5)
>>> w.field('LONG_TEXT', 'C', size=250)
>>> w.null()
# 添加记录，方法1
>>> w.record('Hello', 'World', 'World'*50)
# 添加记录，方法2 
>>> list1 = ['Hello1', 'World', 'World'*20]
>>> w.record(*list1)
# 添加记录，方法3 
>>> dict2 = {'TEXT':'Hello2', 'SHORT_TEXT':'2', 'LONG_TEXT':'World'*10}
>>> w.record(*dict2)
# 保存数据
>>> w.save('shapefiles/test/dtype')

>>> r = shapefile.Reader('shapefiles/test/dtype')
>>> assert r.record(0) == ['Hello', 'World', 'World'*50]

```

日期字段使用“D”类型创建，可以使用日期对象，列表或YYYYMMDD格式化的字符串创建。字段长度或小数点对此类型没有影响：

```
>>> from datetime import date
>>> w = shapefile.Writer()
>>> w.field('DATE', 'D')
>>> w.null()
>>> w.null()
>>> w.null()
>>> w.null()
>>> w.record(date(1998,1,30))
>>> w.record([1998,1,30])
>>> w.record('19980130')
>>> w.record(None)
>>> w.save('shapefiles/test/dtype')

>>> r = shapefile.Reader('shapefiles/test/dtype')
>>> assert r.record(0) == [date(1998,1,30)]
>>> assert r.record(1) == [date(1998,1,30)]
>>> assert r.record(2) == [date(1998,1,30)]
>>> assert r.record(3) == [None]
```

数字字段使用“N”类型（或“F”类型完全相同）创建。默认情况下，第四个十进制参数设置为零，基本上创建一个整数字段。要存储浮点数，您必须将十进制参数设置为您选择的精度。要存储非常大的数字，您必须将字段长度大小增加到总位数（包括逗号和减号）。

```
>>> w = shapefile.Writer()
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
>>> w.save('shapefiles/test/dtype')

>>> r = shapefile.Reader('shapefiles/test/dtype')
>>> assert r.record(0) == [1, 1.32, 1.3217328, -3.2302e-25, 1.3217328, 10000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000]
>>> assert r.record(1) == [None, None, None, None, None, None]

```

最后，我们可以通过将类型设置为'L'来创建布尔字段。该字段可以取True或False值，或1（True）或0（False）。没有被解释为缺失。

```
>>> w = shapefile.Writer()
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
>>> w.save('shapefiles/test/dtype')

>>> r = shapefile.Reader('shapefiles/test/dtype')
>>> r.record(0)
[True]
>>> r.record(1)
[True]
>>> r.record(2)
[False]
>>> r.record(3)
[False]
>>> r.record(4)
[None]
>>> r.record(5)
[None]

```

您还可以使用关键字参数添加属性，其中键是字段名称。

```
>>> w = shapefile.Writer()
>>> w.field('FIRST_FLD','C','40')
>>> w.field('SECOND_FLD','C','40')
>>> w.record('First', 'Line')
>>> w.record(FIRST_FLD='First', SECOND_FLD='Line')

```

### 文件名

读取或写入shapefile时，文件扩展名是可选的。如果你指定它们，PyShp忽略它们。保存文件时，可以指定用于所有三种文件类型的基本文件名。或者您可以指定一个或多个文件类型的名称。在这种情况下，未分配的任何文件类型将不会保存，只有文件名称的文件类型才能保存。如果不指定任何文件名（即save（）），则会生成唯一的文件名，前缀为“shapefile_”，后跟随机字符，用于所有三个文件。唯一的文件名作为字符串返回。

```
>>> targetName = w.save()
>>> assert("shapefile_" in targetName)

```

### 保存到类文件对象

就像您可以从python文件类对象读取shapefile一样，您也可以编写它们。

```
>>> try:
...     from StringIO import StringIO
... except ImportError:
...     from io import BytesIO as StringIO
>>> shp = StringIO()
>>> shx = StringIO()
>>> dbf = StringIO()
>>> w.saveShp(shp)
>>> w.saveShx(shx)
>>> w.saveDbf(dbf)
>>> # Normally you would call the "StringIO.getvalue()" method on these objects.
>>> shp = shx = dbf = None

```

## Python Geo界面

Python __geo_interface__约定提供了地理空间Python库之间的数据交换界面。该接口返回数据GeoJSON，它可以让您与其他库和工具（包括Shapely，Fiona和PostGIS）的兼容性很好。有关__geo_interface__协议的更多信息，请访问：[https](https://gist.github.com/sgillies/2217756)：//gist.github.com/sgillies/2217756 。有关GeoJSON的更多信息，请访问[http://geojson.org](http://geojson.org/)。

```
>>> s = sf.shape(0)
>>> s.__geo_interface__["type"]
'MultiPolygon'

```

正如库可以通过geo界面将其对象暴露给其他应用程序一样，它还支持使用其他应用程序的地理接口接收对象。要根据GeoJSON对象编写形状，只需将具有geo界面或GeoJSON字典的对象发送到shape（）方法而不是Shape对象。或者，您可以使用“geojson_as_shape（）”函数从GeoJSON构造Shape对象。

```
>>> w = shapefile.Writer()
>>> w.field('name', 'C')

>>> w.shape( {"type":"Point", "coordinates":[1,1]} )
>>> w.record('two')

>>> w.save('shapefiles/test/geojson')

```

## 使用大的Shapefile

尽管是一个轻量级库，PyShp旨在能够读取和写入任何大小的shapefile，从而允许您使用数十万甚至数百万条记录和复杂的几何体。

当首次创建Reader类时，库仅读取头信息，并单独留下其余的文件内容。一旦你调用了records（）和shapes（）方法，它将尝试一次将整个文件读入内存。对于非常大的文件，这可能会导致MemoryError。所以当使用大文件时，建议使用iterShapes（），iterRecords（）或iterShapeRecords（）方法。它们一次迭代一个文件内容，使您能够循环遍历它们，同时将内存使用率保持在最低限度。

```
>>> for shape in sf.iterShapes():
...     # do something here
...     pass

>>> for rec in sf.iterRecords():
...     # do something here
...     pass

>>> for shapeRec in sf.iterShapeRecords():
...     # do something here
...     pass

```

shapefile Writer类使用类似的流方式将内存使用率保持在最低限度，除非您没有更改任何代码。图书馆通过创建一组临时文件并立即编写每个几何图形，并使用shape（）或record（）添加到磁盘时记录到磁盘）。您仍然必须像往常一样调用save（），以便指定输出文件的最终位置，以便计算头文件信息并将其写入文件的开头。

这意味着只要您能够遍历源文件，而无需将所有内容加载到内存中，例如大型CSV表或大型shapefile，则可以处理和写入任意数量的项目，甚至合并许多不同的源代码文件变成一个大的shapefile。如果您需要编辑或撤消任何您的写作，您将不得不读取文件，一次一个记录，进行更改，并将其写回来。

## Unicode和Shapefile编码

PyShp完全支持unicode和shapefile编码，所以你总是可以期待在具有文本字段的shape文件中使用unicode字符串。大多数形状文件都以UTF-8编码，PyShp的默认编码编写，因此在大多数情况下，您不必指定编码。对于以任何其他编码（如Latin-1）读取shapefile，只需在创建Reader类时提供编码选项即可。

```
>>> r = shapefile.Reader("shapefiles/test/latin1.shp", encoding="latin1")
>>> r.record(0) == [2, u'Ñandú']
True

```

加载shapefile后，您可以选择使用另一种更为支持的编码（如UTF-8）进行保存。如果新的编码支持你想要写入的字符，那么读回来应该会提供你开始使用的相同的Unicode字符串。

```
>>> w = shapefile.Writer(encoding="utf8")
>>> w.fields = r.fields[1:]
>>> w.record(*r.record(0))
>>> w.null()
>>> w.save("shapefiles/test/latin_as_utf8.shp")

>>> r = shapefile.Reader("shapefiles/test/latin_as_utf8.shp", encoding="utf8")
>>> r.record(0) == [2, u'Ñandú']
True
```

如果提供错误的编码，并且字符串无法解码，PyShp将默认引发异常。然而，如果在罕见的情况下，您无法找到正确的编码，并且想要忽略或替换编码错误，则可以指定decode方法使用的“encodingErrors”。这适用于阅读和写作。

```
>>> r = shapefile.Reader("shapefiles/test/latin1.shp", encoding="ascii", encodingErrors="replace")
>>> r.record(0) == [2, u'�and�']
True

```

# 测试

测试框架是doctest，它们位于此文件README.md中。在与README.md和shapefile.py相同的文件夹中，从命令行运行

```
$ python shapefile.py

```

Linux / Mac和类似平台将需要运行`$ dos2unix README.md`，以便在README.md中正确的行尾。
