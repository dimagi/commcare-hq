#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='pillowtop',
    version='0.1.0',
    description='A couchdbkit changes listener for doing backend processing',
    author='Dimagi',
    author_email='dev@dimagi.com',
    url='http://www.dimagi.com/',
    packages = find_packages(exclude=['*.pyc']),
    include_package_data = True,
    install_requires = [
        "restkit", 
        "couchdbkit",
        "simplejson",
        "requests",
        "gevent",
        "greenlet",
        "rawes",
    ],
)

