#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='django-soil',
    version='0.9.0',
    description="A simple django library to help you schedule long running tasks for retrieval later when they're done using celery",
    author='Dimagi',
    author_email='information@dimagi.com',
    url='http://www.dimagi.com/',
    install_requires = [
        "django",
    ],
    packages = find_packages(exclude=['*.pyc']),
    include_package_data=True
)

