#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='tap-ringcentral',
      version='1.2.0',
      description='Singer.io tap for extracting data from the RingCentral API',
      author='Fishtown Analytics',
      url='http://fishtownanalytics.com',
      classifiers=['Programming Language :: Python :: 3 :: Only'],
      py_modules=['tap_ringcentral'],
      install_requires=[
          'singer-python==6.8.0',
          'requests==2.32.5',
          'backoff==2.2.1',
      ],
      entry_points='''
          [console_scripts]
          tap-ringcentral=tap_ringcentral:main
      ''',
      packages=find_packages(),
      package_data={
          'tap_ringcentral': [
              'schemas/*.json'
          ]
      })
