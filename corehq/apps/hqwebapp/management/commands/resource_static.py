from __future__ import print_function
from __future__ import absolute_import
import hashlib
import json
import os
from django.core.management.base import BaseCommand
from django.contrib.staticfiles import finders
from django.conf import settings
from dimagi.utils import gitinfo
from django.core import cache

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

    def output_resources(self, resources):
        with open(os.path.join(self.root_dir, 'resource_versions.py'), 'w') as fout:
            fout.write("resource_versions = %s" % json.dumps(resources, indent=2))
        if settings.STATIC_CDN:
            with open(os.path.join(self.root_dir, 'corehq', 'apps', 'hqwebapp',
                                   'static', 'hqwebapp', 'js', 'resource_versions.js'), 'w') as fout:
                from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static
                fout.write("requirejs.config({ paths: %s });" % json.dumps({
                    file[:-3]: "{}{}{}{}".format(settings.STATIC_CDN, settings.STATIC_URL, file[:-3], ".js?version=%s" % version if version else "")
                    for file, version in resources.iteritems() if file.endswith(".js")
                }, indent=2))

    def handle(self, **options):
        prefix = os.getcwd()
        current_snapshot = gitinfo.get_project_snapshot(self.root_dir, submodules=False)
        current_sha = current_snapshot['commits'][0]['sha']
        print("Current commit SHA: %s" % current_sha)

        if options['clear']:
            print("clearing resource cache")
            rcache.delete_pattern(RESOURCE_PREFIX % '*')

        existing_resources = rcache.get(RESOURCE_PREFIX % current_sha, None)
        if existing_resources and not isinstance(existing_resources, basestring):
            print("getting resource dict from cache")
            self.output_resources(existing_resources)
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
        rcache.set(RESOURCE_PREFIX % current_sha, resources, 86400)
        self.output_resources(resources)

    def get_hash(self, filename):
        with open(filename) as f:
            hash = hashlib.sha1(f.read()).hexdigest()[:7]
        return hash
