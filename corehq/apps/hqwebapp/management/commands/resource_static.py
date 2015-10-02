import hashlib
import json
import os
from django.core.management.base import LabelCommand
from django.contrib.staticfiles import finders
from django.conf import settings
from dimagi.utils import gitinfo
from django.core import cache

rcache = cache.caches['redis']
RESOURCE_PREFIX = '#resource_%s'


class Command(LabelCommand):
    help = "Prints the paths of all the static files"
    args = "clear"

    root_dir = settings.FILEPATH

    def output_resources(self, resource_str):
        with open(os.path.join(self.root_dir, 'resource_versions.py'), 'w') as fout:
            fout.write("resource_versions = %s" % resource_str)

    def handle(self, *args, **options):
        prefix = os.getcwd()
        current_snapshot = gitinfo.get_project_snapshot(self.root_dir, submodules=False)
        current_sha = current_snapshot['commits'][0]['sha']
        print "Current commit SHA: %s" % current_sha

        if 'clear' in args:
            print "clearing resource cache"
            rcache.delete_pattern(RESOURCE_PREFIX % '*')

        existing_resource_str = rcache.get(RESOURCE_PREFIX % current_sha, None)
        if existing_resource_str:
            print "getting resource dict from cache"
            self.output_resources(existing_resource_str)
            return

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
        resource_str = json.dumps(resources, indent=2)
        rcache.set(RESOURCE_PREFIX % current_sha, resource_str, 86400)
        self.output_resources(resource_str)

    def get_hash(self, filename):
        with open(filename) as f:
            hash = hashlib.sha1(f.read()).hexdigest()[:7]
        return hash
