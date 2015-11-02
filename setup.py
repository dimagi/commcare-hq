#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='pillowtop',
    version='0.1.8',
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
        "jsonobject-couchdbkit==0.7.0.1",
        "simplejson",
        "requests",
        "gevent",
        "greenlet",
        "rawes==0.5.5",
        "elasticsearch==0.4.4",
        'django==1.7.10',
        'dimagi-utils>=1.2.3',
        'psycopg2==2.5.2',
        'fakecouch',
    ],
    tests_require=[
        'unittest2',
    ],
    dependency_links=[
    ]
)
