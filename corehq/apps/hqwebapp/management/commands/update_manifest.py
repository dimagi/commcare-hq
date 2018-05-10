from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from dimagi.utils import gitinfo
from django.core import cache


rcache = cache.caches['redis']
COMPRESS_PREFIX = '#compress_%s'
CACHE_DIR = os.path.join(settings.STATIC_ROOT, 'CACHE')
MANIFEST_FILE = os.path.join(CACHE_DIR, 'manifest.json')


class ResourceCompressError(Exception):
    pass


class Command(BaseCommand):
    help = "Prints the paths of all the static files"

    root_dir = settings.FILEPATH

    def add_arguments(self, parser):
        parser.add_argument(
            'params',
            choices=['save', 'soft', ''],
            default='',
            nargs='*',
        )

    @property
    def manifest_file(self):
        return os.path.join(self.root_dir, MANIFEST_FILE)

    def output_manifest(self, manifest_str, is_soft_update=False):
        print("saving manifest.json to disk")
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        if is_soft_update and os.path.exists(self.manifest_file):
            with open(self.manifest_file, 'r') as fin:
                print("soft update of manifest.json")
                existing_manifest = fin.read()
                new_manifest_dict = json.loads(manifest_str)
                existing_manifest_dict = json.loads(existing_manifest)
                existing_manifest_dict.update(new_manifest_dict)
                manifest_str = json.dumps(existing_manifest_dict)
        with open(self.manifest_file, 'w') as fout:
            print(manifest_str)
            fout.write(manifest_str)

    def save_manifest(self):
        print("saving manifest.json to redis")
        with open(self.manifest_file, 'r') as fin:
            manifest_data = fin.read()
            print(manifest_data)
            rcache.set(COMPRESS_PREFIX % self.current_sha, manifest_data, 86400)

    def handle(self, params, **options):
        current_snapshot = gitinfo.get_project_snapshot(self.root_dir, submodules=False)
        self.current_sha = current_snapshot['commits'][0]['sha']
        print("Current commit SHA: %s" % self.current_sha)

        if 'save' in params:
            self.save_manifest()
        else:
            existing_resource_str = rcache.get(COMPRESS_PREFIX % self.current_sha, None)
            if existing_resource_str:
                self.output_manifest(existing_resource_str,
                                     is_soft_update='soft' in params)
            else:
                raise ResourceCompressError(
                    "Could not find manifest.json in redis! Deploying under this "
                    "condition will cause the server to 500."
                )
