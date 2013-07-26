#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='receiver',
    version='1.0.0',
    description='Dimagi XForm Receiver (an installable Django app)',
    author='Dimagi',
    author_email='dev@dimagi.com',
    url='http://www.dimagi.com/',
    install_requires = [
        "couchdbkit",
        "couchexport",
        "couchforms>=1.0.0",
        "dimagi-utils>=1.0.0",
        "django",
        "lxml",
        "pytz",
        "requests",
        "restkit",
        "simplejson",
        "unittest2"  # required by dimagi-utils
    ],
    tests_require = [
        'coverage',
        'django-coverage',    
    ],
    packages = find_packages(exclude=['*.pyc']),
    include_package_data=True
)

