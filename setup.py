#!/usr/bin/env python
from setuptools import setup, find_packages

import sys

setup(
    name='fluff',
    version='0.0.1',
    description='Map over CouchDB changes feed',
    author='Dimagi',
    author_email='information@dimagi.com',
    url='http://www.dimagi.com/',
    packages=['fluff', 'tests'],
    test_suite='tests',
    test_loader='unittest2:TestLoader',
    install_requires=[
        'couchdbkit',
        'pillowtop==0.0.1',
        'dimagi-utils==0.0.2'
    ],
    dependency_links=[
        'http://github.com/dimagi/dimagi-utils/tarball/master#egg=dimagi-utils-0.0.2',
        'http://github.com/dimagi/pillowtop/tarball/master#egg=pillowtop-0.0.1',
    ],
    tests_require=[
        'django',
        'unittest2'
    ]
)
