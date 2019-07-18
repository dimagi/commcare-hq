from __future__ import absolute_import, print_function
from __future__ import unicode_literals
import json
import logging
import os
import re
import six
import subprocess
import yaml
from collections import defaultdict
from django.contrib.staticfiles import finders
from django.conf import settings
from shutil import copyfile
from subprocess import call

from corehq.apps.hqwebapp.management.commands.resource_static import Command as ResourceStaticCommand
from io import open


logger = logging.getLogger('__name__')


class Command(ResourceStaticCommand):
    help = '''
        Runs RequireJS optimizer to concatenate, minify, and bundle JavaScript files
        and set them up with the CDN.
    '''

    root_dir = settings.FILEPATH
    build_js_filename = "staticfiles/build.js"
    build_txt_filename = "staticfiles/build.txt"
    local_js_dirs = set()   # a reference of js filenames, for use when copying optimized bundles back into corehq

    def add_arguments(self, parser):
        parser.add_argument('--local', action='store_true',
            help='Running on a local environment. Copies generated files back into corehq. Allows you to mimic '
                 'production optimization (dependency tracing, concatenation and minification) locally. '
                 'Does not allow you to mimic CDN.')
        parser.add_argument('--no_optimize', action='store_true',
            help='Don\'t minify files. Runs much faster. Useful when running on a local environment.')

    def _relative(self, path, root=None):
        if not root:
            root = self.root_dir
        rel = path.replace(root, '')
        if rel.startswith("/"):
            rel = rel[1:]
        return rel

    def r_js(self, local=False, no_optimize=False):
        '''
        Write build.js file to feed to r.js, run r.js, and return filenames of the final build config
        and the bundle config output by the build.
        '''
        with open(os.path.join(self.root_dir, 'staticfiles', 'hqwebapp', 'yaml', 'requirejs.yaml'), 'r') as f:
            config = yaml.load(f)

            if no_optimize:
                config['optimize'] = 'none'

            # Find all HTML files in corehq, excluding partials
            prefix = os.path.join(self.root_dir, 'corehq')
            html_files = []
            for root, dirs, files in os.walk(prefix):
                for name in files:
                    if name.endswith(".html"):
                        filename = os.path.join(root, name)
                        if not re.search(r'/partials/', filename):
                            html_files.append(filename)
                    elif local and name.endswith(".js"):
                        self.local_js_dirs.add(self._relative(root))

            '''
            Build a dict of all main js modules, grouped by directory:
            {
                'locations/js': set(['locations/js/import', 'locations/js/location', ...  ]),
                'linked_domain/js': set(['linked_domain/js/domain_links']),
                ...
            }
            '''
            dirs = defaultdict(set)
            for filename in html_files:
                proc = subprocess.Popen(["grep", "^\s*{% requirejs_main [^%]* %}\s*$", filename],
                                        stdout=subprocess.PIPE)
                (out, err) = proc.communicate()
                if out:
                    match = re.search(r"{% requirejs_main .(([^%]*)/[^/%]*). %}", out)
                    if match:
                        main = match.group(1)
                        directory = match.group(2)
                        if os.path.exists(os.path.join(self.root_dir, 'staticfiles', main + '.js')):
                            dirs[directory].add(main)

            # For each directory, add an optimized "module" entry including all of the main modules in that dir.
            # For each of these entries, r.js will create an optimized bundle of these main modules and all their
            # dependencies
            for directory, mains in dirs.items():
                config['modules'].append({
                    'name': os.path.join(directory, "bundle"),
                    'exclude': ['hqwebapp/js/common', 'hqwebapp/js/base_main'],
                    'include': sorted(mains),
                    'create': True,
                })

            # Write final r.js config out as a .js file
            with open(os.path.join(self.root_dir, 'staticfiles', 'build.js'), 'w') as fout:
                fout.write("({});".format(json.dumps(config, indent=4)))

        call(["node", "bower_components/r.js/dist/r.js", "-o", self.build_js_filename])

        return config

    def handle(self, **options):
        logger.setLevel('DEBUG')

        local = options['local']
        no_optimize = options['no_optimize']

        if local:
            proc = subprocess.Popen(["git", "diff-files", "--ignore-submodules", "--name-only"],
                                    stdout=subprocess.PIPE)
            (out, err) = proc.communicate()
            if out:
                confirm = six.moves.input("You have unstaged changes to the following files: \n{} "
                                    "This script overwrites some static files. "
                                    "Are you sure you want to continue (y/n)? ".format(out))
                if confirm[0].lower() != 'y':
                    exit()
            confirm = six.moves.input("You are running locally. Have you already run "
                                "`./manage.py collectstatic --noinput && ./manage.py compilejsi18n` (y/n)? ")
            if confirm[0].lower() != 'y':
                exit()

        try:
            from resource_versions import resource_versions
        except (ImportError, SyntaxError):
            resource_versions = {}

        config = self.r_js(local=local, no_optimize=no_optimize)

        if local:
            # Copy optimized modules in staticfiles back into corehq
            for module in config['modules']:
                src = os.path.join(self.root_dir, 'staticfiles', module['name'] + '.js')

                # Most of the time, the module is .../staticfiles/appName/js/moduleName and
                # should be copied to .../corehq/apps/appName/static/appName/js/moduleName.js
                app = re.sub(r'/.*', '', module['name'])
                dest = os.path.join(self.root_dir, 'corehq', 'apps', app, 'static', module['name'] + '.js')
                if os.path.exists(os.path.dirname(dest)):
                    copyfile(src, dest)
                else:
                    # If that didn't work, look for a js directory that matches the module name
                    # src is something like .../staticfiles/foo/baz/bar.js, so search local_js_dirs
                    # for something ending in foo/baz
                    common_dir = self._relative(os.path.dirname(src), os.path.join(self.root_dir, 'staticfiles'))
                    options = [d for d in self.local_js_dirs if self._relative(d).endswith(common_dir)]
                    if len(options) == 1:
                        dest_stem = options[0][:-len(common_dir)]   # trim the common foo/baz off the destination
                        copyfile(src, os.path.join(self.root_dir, dest_stem, module['name'] + '.js'))
                    else:
                        logger.warning("Could not copy {} to {}".format(self._relative(src), self._relative(dest)))
            logger.info("Final build config written to {}".format(self.build_js_filename))
            logger.info("Bundle config output written to {}".format(self.build_txt_filename))

        filename = os.path.join(self.root_dir, 'staticfiles', 'hqwebapp', 'js', 'requirejs_config.js')
        resource_versions["hqwebapp/js/requirejs_config.js"] = self.get_hash(filename)
        if local:
            dest = os.path.join(self.root_dir, 'corehq', 'apps', 'hqwebapp', 'static',
                                'hqwebapp', 'js', 'requirejs_config.js')
            copyfile(filename, dest)
            logger.info("Copied updated requirejs_config.js back into {}".format(self._relative(dest)))

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
                    if re.search(r'sourceMappingURL=bundle.js.map$', line):
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
