#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='casexml',
    version='1.0.0',
    description='Dimagi CaseXML for Django',
    author='Dimagi',
    author_email='dev@dimagi.com',
    url='http://www.dimagi.com/',
    install_requires = [
        'celery',    
        'couchdbkit',
        'couchforms==1.0.1',
        'couchexport',
        'decorator',
        'dimagi-utils>=1.0.4',
        'django',
        'django-digest',    
        'lxml',
        'mock', # Actually a missing dimagi-utils dep?
        'receiver>=1.0.0',
        'requests',
        'restkit',
        'python-digest',
        'pytz',
        'simplejson',
        'unittest2', # Actually a missing dimagi-utils dep?
    ],
    tests_require = [
        'coverage',
        'django-coverage',    
    ],
    packages = find_packages(exclude=['*.pyc']),
    include_package_data=True
)

