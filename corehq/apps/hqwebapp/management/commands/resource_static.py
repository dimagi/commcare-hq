from __future__ import absolute_import, print_function
from __future__ import unicode_literals
import hashlib
import json
import os
import six
import yaml
from django.core.management.base import BaseCommand
from django.contrib.staticfiles import finders
from django.conf import settings
from dimagi.utils import gitinfo
from django.core import cache
from io import open

from corehq.util.python_compatibility import soft_assert_type_text

rcache = cache.caches['redis']
RESOURCE_PREFIX = '#resource_%s'


class Command(BaseCommand):
    help = "Prints the paths of all the static files"

    root_dir = settings.FILEPATH

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            default=False,
        )

    def current_sha(self):
        current_snapshot = gitinfo.get_project_snapshot(self.root_dir, submodules=False)
        sha = current_snapshot['commits'][0]['sha']
        print("Current commit SHA: %s" % sha)
        return sha

    def output_resources(self, resources):
        with open(os.path.join(self.root_dir, 'resource_versions.yaml'), 'w') as fout:
            #fout.write("resource_versions = %s" % json.dumps(resources, indent=2))
            from get_resource_versions import get_resource_versions
            resource_versions = get_resource_versions()
            resource_versions.update(resources)
            fout.write(yaml.dump([{'name': name, 'version': version} for name, version in resource_versions.items()]))

    def overwrite_resources(self, resources, sha=None):
        if not sha:
            sha = self.current_sha()
        rcache.set(RESOURCE_PREFIX % sha, resources, 86400)
        self.output_resources(resources)

    def handle(self, **options):
        prefix = os.getcwd()

        if options['clear']:
            print("clearing resource cache")
            rcache.delete_pattern(RESOURCE_PREFIX % '*')

        current_sha = self.current_sha()
        existing_resources = rcache.get(RESOURCE_PREFIX % current_sha, None)
        if existing_resources and not isinstance(existing_resources, six.string_types):
            print("getting resource dict from cache")
            self.output_resources(existing_resources)
            return
        if isinstance(existing_resources, six.string_types):
            soft_assert_type_text(existing_resources)

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
        self.overwrite_resources(resources, sha=current_sha)

    def get_hash(self, filename):
        with open(filename, 'rb') as f:
            hash = hashlib.sha1(f.read()).hexdigest()[:7]
        return hash
