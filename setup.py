#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='couchforms',
    version='3.0.2',
    description='Dimagi Couch Forms for Django',
    author='Dimagi',
    author_email='dev@dimagi.com',
    url='http://www.dimagi.com/',
    install_requires=[
        "jsonobject-couchdbkit",
        "couchexport",
        "dimagi-utils>=1.0.11",
        "django",
        "lxml",
        "restkit",
    ],
    tests_require=[
        'coverage',
        'django-coverage',
    ],
    packages=find_packages(exclude=['*.pyc']),
    include_package_data=True,
)
