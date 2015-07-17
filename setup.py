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
        "django<1.8",
        "jsonobject-couchdbkit",
        "dimagi-utils>=1.2.2",
        'django-soil',
        'django-transfer',
        "openpyxl",
        "unidecode",
        "xlwt",
    ],
    packages=find_packages(exclude=['*.pyc']),
    include_package_data=True,
    dependency_links=[
        'git+git://github.com/dimagi/dimagi-utils.git@72f58d63e47a6c873a1d5a0a60462be772542216#egg=dimagi-utils-1.2.2',
        'git+git://github.com/dimagi/django-soil.git@74791d1bf1f9b24d52d5f9c107ab368a7832cf34#egg=django-soil',
    ]
)
