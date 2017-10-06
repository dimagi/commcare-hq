from __future__ import print_function
import json
import os
import re
import yaml
from django.contrib.staticfiles import finders
from django.conf import settings
from subprocess import call

from corehq.apps.hqwebapp.management.commands.resource_static import Command as ResourceStaticCommand


class Command(ResourceStaticCommand):
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

            bundles = {}
            all_modules = []
            prefix = os.path.join(os.getcwd(), 'corehq')
            for finder in finders.get_finders():
                if isinstance(finder, finders.AppDirectoriesFinder):
                    for path, storage in finder.list(['.*', '*~', '* *', '*.*ss', '*.png']):
                        if not storage.location.startswith(prefix):
                            continue
                        if path.endswith(".js"):
                            directory = re.sub(r'/[^/]*$', '', path)
                            if directory not in bundles:
                                bundles[directory] = []
                            bundles[directory].append(path[:-3])
                            all_modules.append(path[:-3])

            customized = {re.sub(r'/[^/]*$', '', m['name']): True for m in config['modules']}
            for directory, inclusions in bundles.iteritems():
                if directory not in customized and not directory.startswith("app_manager/js/vellum"):
                    # Add this module's config to build config
                    config['modules'].append({
                        'name': os.path.join(directory, 'bundle'),
                        'include': inclusions,
                        'excludeShallow': [name for name in all_modules if name not in inclusions],
                        'exclude': ['hqwebapp/js/common'],
                    })

            # Write .js files to staticfiles
            for module in config['modules']:
                with open(os.path.join(self.root_dir, 'staticfiles', module['name'] + ".js"), 'w') as fout:
                    fout.write("define([], function() {});")

            with open(os.path.join(self.root_dir, 'build.js'), 'w') as fout:
                fout.write("({});".format(json.dumps(config, indent=4)))

        call(["node", "bower_components/r.js/dist/r.js", "-o", "build.js"])
        filename = os.path.join(self.root_dir, 'staticfiles', 'hqwebapp', 'js', 'requirejs_config.js')
        resource_versions["hqwebapp/js/requirejs_config.js"] = self.get_hash(filename)

        # Overwrite each bundle in resource_versions with the sha from the optimized version in staticfiles
        for module in config['modules']:
            filename = os.path.join(self.root_dir, 'staticfiles', module['name'] + ".js")
            resource_versions[module['name'] + ".js"] = self.get_hash(filename)

        # Write out resource_versions.js for all js files in resource_versions
        # Exclude formdesigner directory, which contains a ton of files, none of which are required by HQ
        if settings.STATIC_CDN:
            filename = os.path.join(self.root_dir, 'staticfiles', 'hqwebapp', 'js', 'resource_versions.js')
            with open(os.path.join(filename, 'w')) as fout:
                fout.write("requirejs.config({ paths: %s });" % json.dumps({
                    file[:-3]: "{}{}{}{}".format(settings.STATIC_CDN, settings.STATIC_URL, file[:-3],
                                                 ".js?version=%s" % version if version else "")
                    for file, version in resource_versions.iteritems()
                    if file.endswith(".js") and not file.startswith("formdesigner")
                }, indent=2))
            resource_versions["hqwebapp/js/resource_versions.js"] = self.get_hash(filename)

        self.overwrite_resources(resource_versions)
