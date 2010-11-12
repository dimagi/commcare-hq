#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='dimagi-utils',
    version='0.0.2',
    description='Dimagi Shared Utilities',
    author='Dimagi',
    author_email='information@dimagi.com',
    url='http://www.dimagi.com/',
    packages=['dimagi', 'dimagi.utils'],
    install_requires = [
        "python-dateutil"
    ],
)
