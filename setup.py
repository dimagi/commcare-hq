#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='couchforms',
    version='0.0.2',
    description='Dimagi Couch Forms for Django',
    author='Dimagi',
    author_email='information@dimagi.com',
    url='http://www.dimagi.com/',
    install_requires = [
        "couchexport"
    ],
    packages = find_packages(exclude=['*.pyc']),
    include_package_data=True
)

