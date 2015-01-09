"""
Unit tests for Pythonic `datetime.date` object handling.
"""

import unittest
import datetime
try:
    from StringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO

import shapefile


class TestDateHandling(unittest.TestCase):

    def testDateReadWrite(self):
        """Round-trip read and write Python `date` as value for 'D' field"""
        today = datetime.date.today()

        # Write a one-field, one-record shp to memory; use `date` obj as value
        writer = shapefile.Writer()
        writer.field('DATEFIELD', 'D', 8)
        writer.null()
        writer.record(today)
        shp, shx, dbf = StringIO(), StringIO(), StringIO()
        writer.save(shp=shp, shx=shx, dbf=dbf)

        # Read our in-memory shp to verify that Reader gives us a `date` obj
        reader = shapefile.Reader(shp=shp, shx=shx, dbf=dbf)
        self.assertEqual(reader.fields[-1][1], 'D')
        self.assertEqual(len(reader.records()), 1)
        record = reader.record(0)
        d = record[0]
        self.assertTrue(isinstance(d, datetime.date),
                        "Expected a `date` object back from Reader (we got a %s)" % type(d))
        self.assertEqual(d, today)


if __name__ == '__main__':
    unittest.main()
