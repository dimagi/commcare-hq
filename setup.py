#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='django-soil',
    version='0.9.1',
    description="A simple django library to help you schedule long running tasks for retrieval later when they're done using celery",
    author='Dimagi',
    author_email='information@dimagi.com',
    url='https://github.com/dimagi/django-soil/',
    download_url='https://github.com/dimagi/django-soil/',
    install_requires = [
        "django",
    ],
    packages = ['soil'],
    include_package_data=True
)

