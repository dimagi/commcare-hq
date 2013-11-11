import simplejson
import os
from django.core.management.base import LabelCommand
from django.contrib.staticfiles import finders
from subprocess import Popen, PIPE
from django.conf import settings
from dimagi.utils import gitinfo
from django.core import cache

rcache = cache.get_cache('redis')
RESOURCE_PREFIX = '#resource_%s'

class Command(LabelCommand):
    help = "Prints the paths of all the static files"
    args = "clear"

    def output_resources(self, resource_str):
        with open(os.path.join(self.root_dir, 'resource_versions.py'), 'w') as fout:
            fout.write("resource_versions = %s" % resource_str)

    def handle(self, *args, **options):
        self.root_dir = settings.FILEPATH

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

        self.resources = {}
        for finder in finders.get_finders():
            for path, storage in finder.list(['.*', '*~', '* *']):
                if not storage.location.startswith(prefix):
                    continue
                url = os.path.join(storage.prefix, path) if storage.prefix else path
                parts = (storage.location + '/' + path).split('/')
                self.generate_output(url, parts)
        resource_str = simplejson.dumps(self.resources, indent=2)
        rcache.set(RESOURCE_PREFIX % current_sha, resource_str, 86400)
        self.output_resources(resource_str)

    def generate_output(self, url, parts, dir_version=False):
        filepath = '/'.join(parts[:-1]) + '/'
        filename = parts[-1] if not dir_version else "."

        if 'submodules' in parts:
            sub_index = parts.index('submodules')
            if parts[sub_index+1] == 'formdesigner' and filepath.count('/js/lib/xpath') > 0:
                # hack to handle the formdesigner sub-sub
                git_dir = '/'.join(parts[:sub_index+5]) + "/.git"
            else:
                git_dir = '/'.join(parts[:sub_index+2]) + "/.git"
        else:
            git_dir = os.path.join(settings.FILEPATH, '.git')
        cmdstring = r"""git --git-dir %s log -n 1 --format=format:%%h %s""" % (git_dir, os.path.join(filepath, filename))
        p = Popen(
            cmdstring.split(' '),
        stdout=PIPE, stderr=PIPE
        )
        hash = p.stdout.read()
        self.resources[url] = hash
