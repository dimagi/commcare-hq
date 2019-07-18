from __future__ import absolute_import, print_function
from __future__ import unicode_literals
import json
import os
import re
import six
import yaml
from django.contrib.staticfiles import finders
from django.conf import settings
from subprocess import call

from corehq.apps.hqwebapp.management.commands.resource_static import Command as ResourceStaticCommand
from io import open


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
            for directory, inclusions in six.iteritems(bundles):
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

            with open(os.path.join(self.root_dir, 'staticfiles', 'build.js'), 'w') as fout:
                fout.write("({});".format(json.dumps(config, indent=4)))

        call(["node", "bower_components/r.js/dist/r.js", "-o", "staticfiles/build.js"])
        filename = os.path.join(self.root_dir, 'staticfiles', 'hqwebapp', 'js', 'requirejs_config.js')
        resource_versions["hqwebapp/js/requirejs_config.js"] = self.get_hash(filename)

        # Overwrite each bundle in resource_versions with the sha from the optimized version in staticfiles
        for module in config['modules']:
            filename = os.path.join(self.root_dir, 'staticfiles', module['name'] + ".js")

            # TODO: it'd be a performance improvement to do this after the `open` below
            # and pass in the file contents, since get_hash does another read.
            file_hash = self.get_hash(filename)

            # Overwrite source map reference. Source maps are accessed on the CDN,
            # so they need to have the version hash appended.
            with open(filename, 'r') as fin:
                lines = fin.readlines()
            with open(filename, 'w') as fout:
                for line in lines:
                    if re.search(r'sourceMappingURL=bundle.js.map', line):
                        line = re.sub(r'bundle.js.map', 'bundle.js.map?version=' + file_hash, line)
                    fout.write(line)
            resource_versions[module['name'] + ".js"] = file_hash

        # Write out resource_versions.js for all js files in resource_versions
        # Exclude formdesigner directory, which contains a ton of files, none of which are required by HQ
        filename = os.path.join(self.root_dir, 'staticfiles', 'hqwebapp', 'js', 'resource_versions.js')
        with open(filename, 'w') as fout:
            fout.write("requirejs.config({ paths: %s });" % json.dumps({
                file[:-3]: "{}{}{}{}".format(settings.STATIC_CDN, settings.STATIC_URL, file[:-3],
                                             ".js?version=%s" % version if version else "")
                for file, version in six.iteritems(resource_versions)
                if file.endswith(".js") and not file.startswith("formdesigner")
            }, indent=2))
        resource_versions["hqwebapp/js/resource_versions.js"] = self.get_hash(filename)

        self.overwrite_resources(resource_versions)
