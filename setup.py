#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='dimagi-utils',
    version='1.2.3',
    description='Dimagi Shared Utilities',
    author='Dimagi',
    author_email='dev@dimagi.com',
    url='http://www.dimagi.com/',
    packages=find_packages(exclude=['*.pyc']),
    test_suite='dimagi.test_utils',
    test_loader='unittest2:TestLoader',
    install_requires=[
        'jsonobject-couchdbkit>=0.7.0.1',
        'django==1.7.10',
        'django-redis<=3.8',
        'mock>=0.8.0',
        'openpyxl',
        'Pillow',
        'python-dateutil',
        'pytz',
        'simplejson',
        'unittest2',
        "celery",
        "django-devserver"
    ],
)
