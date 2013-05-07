#!/usr/bin/env python
from setuptools import setup, find_packages

import sys

setup(
    name='dimagi-utils',
    version='0.0.2',
    description='Dimagi Shared Utilities',
    author='Dimagi',
    author_email='information@dimagi.com',
    url='http://www.dimagi.com/',
    packages = find_packages(exclude=['*.pyc']),
    test_suite = 'dimagi.test_utils',
    test_loader = 'unittest2:TestLoader',
    install_requires = [
        'python-dateutil',
    ],
    tests_require = [
        'django',
        'openpyxl',
        'pytz',
        'unittest2',
    ],
)
