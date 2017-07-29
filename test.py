import shapefile
import unittest
import os
import doctest

class TestEncoding(unittest.TestCase):
    def test_latin1(self):
        filename = os.path.join(os.path.dirname(__file__), 'shapefiles',
                                'test', 'latin1')
        with open(filename + '.shp', 'rb') as shp:
            with open(filename + '.dbf', 'rb') as dbf:
                reader = shapefile.Reader(shp=shp, dbf=dbf, encoding='latin-1')
                self.assertEqual(reader.records(), [[2, 'Ñandú']])

def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocFileSuite('README.md'))
    return tests
