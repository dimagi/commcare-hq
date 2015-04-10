#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='couchexport',
    version='0.0.2',
    description='Dimagi Couch Exporter for Django',
    author='Dimagi',
    author_email='information@dimagi.com',
    url='http://www.dimagi.com/',
    install_requires = [
        "django<1.7",
        "jsonobject-couchdbkit",
        "dimagi-utils",
        'django-soil',
        "openpyxl",
        "unidecode",
        "xlwt",
    ],
    packages = find_packages(exclude=['*.pyc']),
    include_package_data=True
)

