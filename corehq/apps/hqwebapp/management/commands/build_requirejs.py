from __future__ import print_function
import hashlib
import json
import os
import yaml
from django.contrib.staticfiles import finders
from django.conf import settings
from dimagi.utils import gitinfo
from django.core import cache
from subprocess import call

from corehq.apps.hqwebapp.management.commands.resource_static import Command as BaseCommand


class Command(BaseCommand):
    help = '''
        Runs RequireJS optimizer to concatenate, minify, and bundle JavaScript files
        and set them up with the CDN.
    '''

    root_dir = settings.FILEPATH

    def handle(self, **options):
        try:
            from resource_versions import resource_versions
        except (ImportError, SyntaxError):
            resource_versions = {}

        # Write build.js file to feed to r.js
        with open(os.path.join(self.root_dir, 'staticfiles', 'hqwebapp', 'yaml', 'requirejs.yaml'), 'r') as f:
            config = yaml.load(f)
            with open(os.path.join(self.root_dir, 'build.js'), 'w') as fout:
                fout.write("({});".format(json.dumps(config, indent=4)))

        call(["node", "bower_components/r.js/dist/r.js", "-o", "build.js"])

        # Overwrite each bundle in resource_versions with the sha from the optimized version in staticfiles
        for module in config['modules']:
            filename = os.path.join(self.root_dir, 'staticfiles', module['name'] + ".js")
            resource_versions[module['name'] + ".js"] = self.get_hash(filename)

        # Write out resource_versions.js for all js files in resource_versions
        # This is a LOT of js files, would be good to reduce the set
        if settings.STATIC_CDN:
            with open(os.path.join(self.root_dir, 'staticfiles', 'hqwebapp', 'js', 'resource_versions.js'), 'w') as fout:
                fout.write("requirejs.config({ paths: %s });" % json.dumps({
                    file[:-3]: "{}{}{}{}".format(settings.STATIC_CDN, settings.STATIC_URL, file[:-3], ".js?version=%s" % version if version else "")
                    for file, version in resource_versions.iteritems() if file.endswith(".js")
                }, indent=2))
