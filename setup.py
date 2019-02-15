from setuptools import setup


def read_file(file):
    with open(file, 'rb') as fh:
        data = fh.read()
    return data.decode('utf-8')

setup(name='pyshp',
      version='2.1.0',
      description='Pure Python read/write support for ESRI Shapefile format',
      long_description=read_file('README.md'),
      long_description_content_type='text/markdown',
      author='Joel Lawhead',
      author_email='jlawhead@geospatialpython.com',
      url='https://github.com/GeospatialPython/pyshp',
      download_url='https://github.com/GeospatialPython/pyshp/archive/2.1.0.tar.gz',
      py_modules=['shapefile'],
      license='MIT',
      zip_safe=False,
      keywords='gis geospatial geographic shapefile shapefiles',
      python_requires='>= 2.7',
      classifiers=['Programming Language :: Python',
                   'Programming Language :: Python :: 2.7',
                   'Programming Language :: Python :: 3',
                   'Topic :: Scientific/Engineering :: GIS',
                   'Topic :: Software Development :: Libraries',
                   'Topic :: Software Development :: Libraries :: Python Modules'])
