#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='auditcare',
    version='0.0.1',
    description='Dimagi Auditor for Django using CouchDB',
    author='Dimagi',
    author_email='information@dimagi.com',
    url='http://www.dimagi.com/',
    install_requires = [
        "couchdbkit"
    ],
    packages = find_packages(exclude=['*.pyc']),
    include_package_data=True
)

