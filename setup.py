#!/usr/bin/env python
from setuptools import setup

setup(
    name='pillowfluff',
    version='0.0.3',
    description='Map over CouchDB changes feed built to run on Pillowtop',
    author='Dimagi',
    author_email='information@dimagi.com',
    url='http://www.dimagi.com/',
    packages=['fluff','fluff.fluff_filter'],
    include_package_data=True,
    test_suite='tests',
    test_loader='unittest2:TestLoader',
    install_requires=[
        'jsonobject-couchdbkit>=0.6.5.2',
        'pillowtop>=0.1.2',
        'dimagi-utils>=1.0.2',
        'pytz',
    ],
    tests_require=[
        'django',
        'unittest2',
        'fakecouch>=0.0.3'
    ]
)
