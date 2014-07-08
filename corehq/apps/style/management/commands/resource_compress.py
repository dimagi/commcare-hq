import os
from django.core.management.base import LabelCommand
from django.conf import settings
from dimagi.utils import gitinfo
from django.core import cache


rcache = cache.get_cache('redis')
COMPRESS_PREFIX = '#compress_%s'
CACHE_DIR = '%s/CACHE' % settings.STATIC_ROOT
MANIFEST_FILE = '%s/manifest.json' % CACHE_DIR


class ResourceCompressError(Exception):
    pass


class Command(LabelCommand):
    help = "Prints the paths of all the static files"
    args = "save"

    root_dir = settings.FILEPATH

    def output_manifest(self, manifest_str):
        print "saving manifest.json to disk"
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        with open(os.path.join(self.root_dir, MANIFEST_FILE), 'w') as fout:
            print manifest_str
            fout.write(manifest_str)

    def save_manifest(self):
        print "saving manifest.json to redis"
        with open(os.path.join(self.root_dir, MANIFEST_FILE), 'r') as fin:
            manifest_data = fin.read()
            print manifest_data
            rcache.set(COMPRESS_PREFIX % self.current_sha, manifest_data, 86400)

    def handle(self, *args, **options):
        current_snapshot = gitinfo.get_project_snapshot(self.root_dir, submodules=False)
        self.current_sha = current_snapshot['commits'][0]['sha']
        print "Current commit SHA: %s" % self.current_sha

        if 'save' in args:
            self.save_manifest()
        else:
            existing_resource_str = rcache.get(COMPRESS_PREFIX % self.current_sha, None)
            if existing_resource_str:
                self.output_manifest(existing_resource_str)
            else:
                raise ResourceCompressError(
                    "Could not find manifest.json in redis! Deploying under this "
                    "condition will cause the server to 500."
                )
