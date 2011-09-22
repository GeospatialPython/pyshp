from setuptools import setup
import usage

setup(name='pyshp',
      version='1.1.0',
      description='Pure Python read/write support for ESRI Shapefile format',
      long_description=usage.__doc__.strip(),
      author='Joel Lawhead',
      author_email='jlawhead@geospatialpython.com',
      url='http://code.google.com/p/pyshp',
      py_modules=['shapefile','usage'],
      license='MIT',
      zip_safe=False,
      keywords='gis geospatial geographic shapefile shapefiles',
      classifiers=['Programming Language :: Python',
                   'Topic :: Scientific/Engineering :: GIS',
                   'Topic :: Software Development :: Libraries',
                   'Topic :: Software Development :: Libraries :: Python Modules'])
