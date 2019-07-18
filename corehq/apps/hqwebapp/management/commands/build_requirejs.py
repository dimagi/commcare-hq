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

            '''
            The default strategy is to make one "bundle" for every corehq directory of js files.
            Begin by gathering all corehq staticfiles directories into a dict like:
                {
                    'app_manager/js' => [
                        'app_manager/js/app_view',
                        'app_manager/js/add_ons',
                        ...
                    ],
                    'app_manager/js/forms' => [
                        'app_manager/js/forms/form_designer',
                        ...
                    ],
                    ...
                }
            '''
            prefix = os.path.join(os.getcwd(), 'corehq')
            corehq_dirs = {}
            all_js_files = []
            for finder in finders.get_finders():
                if isinstance(finder, finders.AppDirectoriesFinder):
                    for path, storage in finder.list(['.*', '*~', '* *', '*.*ss', '*.png']):
                        if not storage.location.startswith(prefix):
                            continue
                        if path.endswith(".js"):
                            directory = re.sub(r'/[^/]*$', '', path)
                            if directory not in corehq_dirs:
                                corehq_dirs[directory] = []
                            corehq_dirs[directory].append(path[:-3])
                            all_js_files.append(path[:-3])

            # Go through customized bundles and expand any that include directories
            for module in config['modules']:
                if 'include_directories' in module:
                    if 'include' not in module:
                        module['include'] = []
                    for directory in module.pop('include_directories'):
                        if directory not in corehq_dirs:
                            raise Exception("Could not find directory to include: {}".format(directory))
                        module['include'] += corehq_dirs[directory]

            # Add a bundle for each directory that doesn't already have a custom module defined
            customized_directories = {re.sub(r'/[^/]*$', '', m['name']): True for m in config['modules']}
            for directory, inclusions in six.iteritems(corehq_dirs):
                if directory not in customized_directories and not directory.startswith("app_manager/js/vellum"):
                    # Add this module's config to build config
                    config['modules'].append({
                        'name': os.path.join(directory, 'bundle'),
                        'include': inclusions,
                        'excludeShallow': [name for name in all_js_files if name not in inclusions],
                        'exclude': ['hqwebapp/js/common'],
                    })

            # Write a no-op .js file to staticfiles for each bundle, because r.js needs an actual file to overwrite
            for module in config['modules']:
                with open(os.path.join(self.root_dir, 'staticfiles', module['name'] + ".js"), 'w') as fout:
                    fout.write("define([], function() {});")

            # Write final r.js config out as a .js file
            with open(os.path.join(self.root_dir, 'staticfiles', 'build.js'), 'w') as fout:
                fout.write("({});".format(json.dumps(config, indent=4)))

        # Run r.js
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
