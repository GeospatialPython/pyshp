from setuptools import setup

with open('README.txt') as file:
    long_description = file.read()

setup(name='pyshp',
      version='1.1.3',
      description='Pure Python read/write support for ESRI Shapefile format',
      long_description=long_description,
      author='Joel Lawhead',
      author_email='jlawhead@geospatialpython.com',
      url='http://code.google.com/p/pyshp',
      py_modules=['shapefile'],
      license='MIT',
      zip_safe=False,
      keywords='gis geospatial geographic shapefile shapefiles',
      classifiers=['Programming Language :: Python',
                   'Topic :: Scientific/Engineering :: GIS',
                   'Topic :: Software Development :: Libraries',
                   'Topic :: Software Development :: Libraries :: Python Modules'])
