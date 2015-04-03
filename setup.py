#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='pillowtop',
    version='0.1.6',
    description='A couchdbkit changes listener for doing backend processing',
    author='Dimagi',
    author_email='dev@dimagi.com',
    url='http://www.dimagi.com/',
    packages=find_packages(exclude=['*.pyc']),
    include_package_data=True,
    test_suite='pillowtop.tests',
    test_loader='unittest2:TestLoader',
    install_requires=[
        "restkit",
        "jsonobject-couchdbkit>=0.6.5.2",
        "simplejson",
        "requests",
        "gevent",
        "greenlet",
        "rawes",
        "elastic==0.4.4",
        'django>=1.3.1,<1.7',
        'dimagi-utils>=1.0.10',
        'psycopg2==2.5.2',
        'south==0.7.3',
    ],
    tests_require=[
        'unittest2',
    ]
)
