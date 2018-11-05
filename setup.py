import codecs
import sys

from setuptools import setup


PYTHON3 = sys.version_info[0] == 3

def read_file(file):
    if PYTHON3:
        return open(file, encoding='utf-8').read()
    else:
        return codecs.open(file, encoding='utf-8').read()

setup(name='pyshp',
      version='2.0.0',
      description='Pure Python read/write support for ESRI Shapefile format',
      long_description=read_file('README.md'),
      author='Joel Lawhead',
      author_email='jlawhead@geospatialpython.com',
      url='https://github.com/GeospatialPython/pyshp',
      download_url='https://github.com/GeospatialPython/pyshp/archive/2.0.0.tar.gz',
      py_modules=['shapefile'],
      license='MIT',
      zip_safe=False,
      keywords='gis geospatial geographic shapefile shapefiles',
      classifiers=['Programming Language :: Python',
                   'Topic :: Scientific/Engineering :: GIS',
                   'Topic :: Software Development :: Libraries',
                   'Topic :: Software Development :: Libraries :: Python Modules'])
