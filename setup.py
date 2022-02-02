from setuptools import setup


def read_file(file):
    with open(file, 'rb') as fh:
        data = fh.read()
    return data.decode('utf-8')

setup(name='pyshp',
      version='2.2.0',
      description='Pure Python read/write support for ESRI Shapefile format',
      long_description=read_file('README.md'),
      long_description_content_type='text/markdown',
      author='Joel Lawhead, Karim Bahgat',
      author_email='jlawhead@geospatialpython.com',
      url='https://github.com/GeospatialPython/pyshp',
      py_modules=['shapefile'],
      license='MIT',
      zip_safe=False,
      keywords='gis geospatial geographic shapefile shapefiles',
      python_requires='>= 2.7',
      classifiers=['Programming Language :: Python',
                   'Programming Language :: Python :: 2.7',
                   'Programming Language :: Python :: 3',
                   'Programming Language :: Python :: 3.5',
                   'Programming Language :: Python :: 3.6',
                   'Programming Language :: Python :: 3.7',
                   'Programming Language :: Python :: 3.8',
                   'Programming Language :: Python :: 3.9',
                   'Topic :: Scientific/Engineering :: GIS',
                   'Topic :: Software Development :: Libraries',
                   'Topic :: Software Development :: Libraries :: Python Modules'])
