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
        "jsonobject-couchdbkit==0.6.5.7",
        "dimagi-utils>=1.2.2",
        'django-soil==0.10.0',
        'django-transfer==dev',
        "openpyxl",
        "unidecode",
        "xlwt",
    ],
    packages=find_packages(exclude=['*.pyc']),
    include_package_data=True,
    dependency_links=[
        'git+git://github.com/dimagi/dimagi-utils.git@72f58d63e47a6c873a1d5a0a60462be772542216#egg=dimagi-utils-1.2.2',
        'git+git://github.com/dimagi/django-soil.git@3efc0878c87f2e6d91fa0eeb0008174f195e6d23#egg=django-soil-0.10.0',
        'git+git://github.com/smartfile/django-transfer.git@6e0dc94c3341c358fca8eb2bf74e23aee3983ec4#egg=django-transfer-dev',
    ]
)
