import hashlib
import json
import os

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.management.base import BaseCommand

import yaml

from dimagi.utils import gitinfo


class Command(BaseCommand):
    help = """
        Hashes the contents of all static files and stores the results in resource_versions.yaml.
    """

    root_dir = settings.FILEPATH

    def output_resources(self, resources, overwrite=True, path=None):
        if not overwrite:
            from get_resource_versions import get_resource_versions
            old_resources = get_resource_versions(path=path)
            old_resources.update(resources)
            resources = old_resources
        if not path:
            path = os.path.join(self.root_dir, 'resource_versions.yaml')
        with open(path, 'w') as fout:
            fout.write(yaml.dump([{'name': name, 'version': version}
                                  for name, version in resources.items()]))

    def handle(self, **options):
        prefix = os.getcwd()

        resources = {}
        for finder in finders.get_finders():
            for path, storage in finder.list(['.*', '*~', '* *']):
                if not storage.location.startswith(prefix):
                    continue
                if not getattr(storage, 'prefix', None):
                    url = path
                else:
                    url = os.path.join(storage.prefix, path)
                filename = os.path.join(storage.location, path)
                resources[url] = self.get_hash(filename)

        self.output_resources(resources)

    def get_hash(self, filename):
        with open(filename, 'rb') as f:
            hash = hashlib.sha1(f.read()).hexdigest()[:7]
        return hash
