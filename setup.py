#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='couchforms',
    version='2.1.0',
    description='Dimagi Couch Forms for Django',
    author='Dimagi',
    author_email='dev@dimagi.com',
    url='http://www.dimagi.com/',
    install_requires = [
        "couchdbkit",
        "couchexport",
        "dimagi-utils>=1.0.0",
        "django",
        "lxml",
        "restkit",
    ],
    tests_require = [
        'coverage',
        'django-coverage',    
    ],
    packages = find_packages(exclude=['*.pyc']),
    include_package_data=True
)

