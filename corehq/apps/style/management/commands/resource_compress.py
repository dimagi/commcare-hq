import os
from django.core.management.base import LabelCommand
from django.conf import settings
from dimagi.utils import gitinfo
from django.core import cache


rcache = cache.get_cache('redis')
COMPRESS_PREFIX = '#compress_%s'
MANIFEST_FILE = '%s/CACHE/manifest.json' % settings.STATIC_ROOT


class ResourceCompressError(Exception):
    pass


class Command(LabelCommand):
    help = "Prints the paths of all the static files"
    args = "save"

    root_dir = settings.FILEPATH

    def output_manifest(self, manifest_str):
        print "saving manifest.json to disk"
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
