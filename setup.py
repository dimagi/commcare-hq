#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='dimagi-utils',
    version='1.0.4',
    description='Dimagi Shared Utilities',
    author='Dimagi',
    author_email='dev@dimagi.com',
    url='http://www.dimagi.com/',
    packages=find_packages(exclude=['*.pyc']),
    test_suite='dimagi.test_utils',
    test_loader='unittest2:TestLoader',
    install_requires=[
        'django',
        'openpyxl',
        'python-dateutil',
        'pytz',
        'couchdbkit',
        'django_redis',
        'simplejson',
        'Pillow'
    ],
    tests_require=[
        'unittest2',
        'mock>=0.8.0',
    ],
)
