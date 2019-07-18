from __future__ import absolute_import, print_function
from __future__ import unicode_literals
import json
import os
import re
import six
import subprocess
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

            # Find all HTML files in corehq, excluding partials
            prefix = os.path.join(os.getcwd(), 'corehq')
            html_files = []
            for root, dirs, files in os.walk(prefix):
                for name in files:
                    if name.endswith(".html"):
                        filename = os.path.join(root, name)
                        if not re.search(r'/partials/', filename):
                            html_files.append(filename)

            '''
            Build a dict of all main js modules, grouped by directory:
            {
                'locations/js': set(['locations/js/import', 'locations/js/location', ...  ]),
                'linked_domain/js': set(['linked_domain/js/domain_links']),
                ...
            }
            '''
            dirs = {}
            for filename in html_files:
                proc = subprocess.Popen(["grep", "^\s*{% requirejs_main [^%]* %}\s*$", filename], stdout=subprocess.PIPE)
                (out, err) = proc.communicate()
                if out:
                    match = re.search(r"{% requirejs_main .(([^%]*)/[^/%]*). %}", out)
                    if match:
                        main = match.group(1)
                        directory = match.group(2)
                        if os.path.exists(os.path.join(os.getcwd(), 'staticfiles', main + '.js')):
                            if directory not in dirs:
                                dirs.update({directory: set()})
                            dirs[directory].add(main)


            # For each directory, add an optimized "module" entry including all of the main modules in that dir.
            # For each of these entries, r.js will create an optimized bundle of these main modules and all their
            # dependencies
            for directory, mains in dirs.items():
                config['modules'].append({
                    'name': os.path.join(directory, "bundle"),
                    'exclude': ['hqwebapp/js/common', 'hqwebapp/js/base_main'],
                    'include': list(mains),
                    'create': True,
                })

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
