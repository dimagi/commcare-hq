#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='casexml',
    version='0.1.0',
    description='Dimagi CaseXML for Django',
    author='Dimagi',
    author_email='dev@dimagi.com',
    url='http://www.dimagi.com/',
    install_requires = [
        "couchdbkit",
        "couchforms>=0.1.0",
        "couchexport",
        "dimagi-utils>=1.0.0",
        "django",
        "lxml",
        "restkit",
        "pytz",
        "simplejson",
    ],
    tests_require = [
        'coverage',
        'django-coverage',    
    ],
    packages = find_packages(exclude=['*.pyc']),
    include_package_data=True
)

