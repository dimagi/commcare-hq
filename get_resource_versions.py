from __future__ import absolute_import
from __future__ import unicode_literals
import yaml
from django.conf import settings
from io import open
import os


def get_resource_versions(path=None):
    resource_versions = {}

    if not path:
        path = os.path.join(settings.FILEPATH, 'resource_versions.yaml')
    if not os.path.exists(path):
        return resource_versions

    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if data:
            for resource in data:
                resource_versions[resource['name']] = resource['version']

    return resource_versions
