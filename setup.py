#!/usr/bin/env python
from setuptools import setup

setup(
    name='pillowfluff',
    version='0.0.5',
    description='Map over CouchDB changes feed built to run on Pillowtop',
    author='Dimagi',
    author_email='information@dimagi.com',
    url='http://www.dimagi.com/',
    packages=['fluff','fluff.fluff_filter'],
    include_package_data=True,
    test_suite='tests',
    test_loader='unittest2:TestLoader',
    install_requires=[
        'jsonobject-couchdbkit>=0.7.0.1',
        'pillowtop>=0.1.8',
        'dimagi-utils>=1.2.3',
        'pytz',
        'SQLAlchemy==1.0.9',
        'alembic==0.6.0'
    ],
    tests_require=[
        'django==1.7.10',
        'unittest2',
        'fakecouch>=0.0.6',
        'psycopg2>=2.4.1',
    ]
)
