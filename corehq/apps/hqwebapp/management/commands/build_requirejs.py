import json
import logging
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from shutil import copyfile
from subprocess import call

from django.conf import settings

import yaml
from django.core.management import CommandError

from corehq.apps.hqwebapp.exceptions import ResourceVersionsNotFoundException
from corehq.apps.hqwebapp.management.commands.resource_static import \
    Command as ResourceStaticCommand
from corehq.util.log import with_progress_bar

logger = logging.getLogger(__name__)
ROOT_DIR = settings.FILEPATH
BUILD_JS_FILENAME = "staticfiles/build.js"
BUILD_TXT_FILENAME = "staticfiles/build.txt"
BOOTSTRAP_VERSIONS = ['bootstrap3', 'bootstrap5']


class Command(ResourceStaticCommand):
    help = '''
        Runs RequireJS optimizer to concatenate, minify, and bundle JavaScript files
        and set them up with the CDN. Use `--verbosity=2` for full output.
    '''

    def add_arguments(self, parser):
        parser.add_argument('--local', action='store_true',
            help='Running on a local environment. Copies generated files back into corehq. Allows you to mimic '
                 'production optimization (dependency tracing, concatenation and minification) locally. '
                 'Does not allow you to mimic CDN.')
        parser.add_argument('--no_optimize', action='store_true',
            help='Don\'t minify files. Runs much faster. Useful when running on a local environment.')
        parser.add_argument('--bootstrap_version', default="bootstrap3",
            help="Specify bootstrap3 or bootstrap5 (bootstrap3 is default)")

    def handle(self, **options):
        logger.setLevel('DEBUG')

        self.local = options['local']
        self.verbose = options['verbosity'] > 1
        self.optimize = not options['no_optimize']

        self._check_prereqs()

        for bootstrap_version in BOOTSTRAP_VERSIONS:
            config, local_js_dirs = self._r_js(bootstrap_version=bootstrap_version)
            self._minify(config)

            if self.local:
                _copy_modules_back_into_corehq(config, local_js_dirs)

            filename = self._staticfiles_path('hqwebapp', 'js', bootstrap_version, 'requirejs_config.js')
            self._update_resource_hash(f"hqwebapp/js/{bootstrap_version}/requirejs_config.js", filename)
            if self.local:
                dest = self._apps_path('hqwebapp', 'js', bootstrap_version, 'requirejs_config.js')
                copyfile(filename, dest)
                logger.info(f"Copied updated {bootstrap_version}/requirejs_config.js back into {_relative(dest)}")

            # Overwrite each bundle in resource_versions with the sha from the optimized version in staticfiles
            for module in config['modules']:
                filename = self._staticfiles_path(module['name'] + ".js")
                file_hash = self._update_resource_hash(module['name'] + ".js", filename)
                self._update_source_map_hash(filename, file_hash)

        self._write_resource_versions()

    def _check_prereqs(self):
        if self.local:
            proc = subprocess.Popen(["git", "diff-files", "--ignore-submodules", "--name-only"],
                                    stdout=subprocess.PIPE)
            (out, err) = proc.communicate()
            out = out.decode('utf-8')
            if out:
                confirm = input("You have unstaged changes to the following files: \n{} "
                                "This script overwrites some static files. "
                                "Are you sure you want to continue (y/n)? ".format(out))
                if confirm[0].lower() != 'y':
                    exit()

            confirm = input("You are running locally. Have you already run "
                            "`./manage.py resource_static && ./manage.py collectstatic "
                            "--noinput && ./manage.py compilejsi18n` (y/n)? ")
            if confirm[0].lower() != 'y':
                exit()

        # During deploy, resource_static should already have run and populated resource_versions
        from get_resource_versions import get_resource_versions
        self.resource_versions = get_resource_versions()
        if (not self.resource_versions):
            raise ResourceVersionsNotFoundException()

    def _staticfiles_path(self, *parts):
        return os.path.join(settings.BASE_DIR, 'staticfiles', *parts)

    def _apps_path(self, app_name, *parts):
        return os.path.join(settings.BASE_DIR, 'corehq', 'apps', app_name, 'static', app_name, *parts)

    def _r_js(self, bootstrap_version='bootstrap3'):
        '''
        Write build.js file to feed to r.js, run r.js, and return filenames of the final build config
        and the bundle config output by the build.
        '''
        is_bootstrap5 = bootstrap_version == 'bootstrap5'
        with open(self._staticfiles_path('hqwebapp', 'yaml', bootstrap_version, 'requirejs.yml'), 'r') as f:
            config = yaml.safe_load(f)

        config['logLevel'] = 0 if self.verbose else 2  # TRACE or WARN
        if not self.verbose:
            print("Compiling Javascript bundles")

        html_files, local_js_dirs = self._get_html_files_and_local_js_dirs()

        # These pages depend on bootstrap 5 and must be skipped by the bootstrap3 run of this command.
        # "<bundle directory>": [<js main modules that depend on bootstrap 5>]
        split_bundles = {
            "commtrack/js": ['commtrack/js/products_and_programs_main'],
            "hqwebapp/js": ['hqwebapp/js/500'],
        }

        # For each directory, add an optimized "module" entry including all of the main modules in that dir.
        # For each of these entries, r.js will create an optimized bundle of these main modules and all their
        # dependencies
        dirs_to_js_modules = self._get_main_js_modules_by_dir(html_files)
        for directory, mains in dirs_to_js_modules.items():
            if is_bootstrap5 and directory not in split_bundles:
                continue
            if not is_bootstrap5 and directory in split_bundles:
                mains = mains.difference(split_bundles[directory])
            basename = "bootstrap5.bundle" if is_bootstrap5 else "bundle"
            config['modules'].append({
                'name': os.path.join(directory, basename),
                'exclude': [
                    f'hqwebapp/js/{bootstrap_version}/common',
                    f'hqwebapp/js/{bootstrap_version}/base_main',
                ],
                'include': sorted(mains),
                'create': True,
            })

        self._save_r_js_config(config)

        ret = call(["node", "node_modules/requirejs/bin/r.js", "-o", BUILD_JS_FILENAME])
        if ret:
            raise CommandError("Failed to build JS bundles")

        return config, local_js_dirs

    def _get_html_files_and_local_js_dirs(self):
        """
        Returns
        - all HTML files in corehq, excluding partials
        - a reference of js directories, for use when copying optimized bundles back into corehq
        """
        prefix = os.path.join(ROOT_DIR, 'corehq')
        html_files = []
        local_js_dirs = set()
        for root, dirs, files in os.walk(prefix):
            for name in files:
                if name.endswith(".html"):
                    filename = os.path.join(root, name)
                    if not re.search(r'/partials/', filename):
                        html_files.append(filename)
                elif self.local and name.endswith(".js"):
                    local_js_dirs.add(_relative(root))
        return html_files, local_js_dirs

    def _get_main_js_modules_by_dir(self, html_files):
        """
        Returns a dict of all main js modules, grouped by directory:
        {
            'locations/js': set(['locations/js/import', 'locations/js/location', ...  ]),
            'linked_domain/js': set(['linked_domain/js/domain_links']),
            ...
        }
        """
        dirs = defaultdict(set)
        for filename in html_files:
            proc = subprocess.Popen(["grep", r"^\s*{% requirejs_main [^%]* %}\s*$", filename],
                                    stdout=subprocess.PIPE)
            (out, err) = proc.communicate()
            out = out.decode('utf-8')
            if out:
                match = re.search(r"{% requirejs_main .(([^%]*)/[^/%]*). %}", out)
                if match:
                    main = match.group(1)
                    directory = match.group(2)
                    if os.path.exists(self._staticfiles_path(main + '.js')):
                        if '/spec/' not in main:  # ignore tests
                            dirs[directory].add(main)
        return dirs

    def _save_r_js_config(self, config):
        """
        Writes final r.js config out as a .js file
        """
        r_js_config = "({});".format(json.dumps(config, indent=4))
        with open(self._staticfiles_path('build.js'), 'w') as fout:
            fout.write(r_js_config)

    def _minify(self, config):
        if not self.optimize:
            return

        modules = config['modules']
        if self.verbose:
            modules = with_progress_bar(modules, prefix="Minifying", oneline=False)
        else:
            print("Minifying Javascript bundles (estimated wait time: 5min)")
        for module in modules:
            rel_path = Path(module['name'] + ".js")
            path = self._staticfiles_path(rel_path)
            ret = call([
                "node", "node_modules/uglify-js/bin/uglifyjs", path, "--compress", "--mangle", "--output", path,
                "--source-map", f"url={rel_path.name}.map"
            ])
            if ret:
                raise CommandError(f"Failed to minify {rel_path}")

    def _update_resource_hash(self, name, filename):
        file_hash = self.get_hash(filename)
        self.resource_versions[name] = file_hash
        return file_hash

    # Overwrite source map reference. Source maps are accessed on the CDN, so they need the version hash
    def _update_source_map_hash(self, filename, file_hash):
        if not self.optimize:
            return

        with open(filename, 'r') as fin:
            lines = fin.readlines()
        with open(filename, 'w') as fout:
            for line in lines:
                if re.search(r'sourceMappingURL=bundle.js.map$', line):
                    line = re.sub(r'bundle.js.map', 'bundle.js.map?version=' + file_hash, line)
                fout.write(line)

    def _write_resource_versions(self):
        filename = self._staticfiles_path('hqwebapp', 'js', 'resource_versions.js')
        with open(filename, 'w') as fout:
            fout.write("requirejs.config({ paths: %s });" % json.dumps({
                file[:-3]: "{}{}{}{}".format(settings.STATIC_CDN, settings.STATIC_URL, file[:-3],
                                             ".js?version=%s" % version if version else "")
                for file, version in self.resource_versions.items()
                # Exclude formdesigner directory, which contains a ton of files, none of which are required by HQ
                if file.endswith(".js") and not file.startswith("formdesigner")
            }, indent=2))
        self._update_resource_hash("hqwebapp/js/resource_versions.js", filename)

        self.output_resources(self.resource_versions, overwrite=False)


def _relative(path, root=None):
    if not root:
        root = ROOT_DIR
    rel = path.replace(root, '')
    if rel.startswith("/"):
        rel = rel[1:]
    return rel


def _copy_modules_back_into_corehq(config, local_js_dirs):
    """
    Copy optimized modules in staticfiles back into corehq
    """
    for module in config['modules']:
        src = os.path.join(ROOT_DIR, 'staticfiles', module['name'] + '.js')

        # Most of the time, the module is .../staticfiles/appName/js/moduleName and
        # should be copied to .../corehq/apps/appName/static/appName/js/moduleName.js
        app = re.sub(r'/.*', '', module['name'])
        dest = os.path.join(ROOT_DIR, 'corehq', 'apps', app, 'static', module['name'] + '.js')
        if os.path.exists(os.path.dirname(dest)):
            copyfile(src, dest)
        else:
            # If that didn't work, look for a js directory that matches the module name
            # src is something like .../staticfiles/foo/baz/bar.js, so search local_js_dirs
            # for something ending in foo/baz
            common_dir = _relative(os.path.dirname(src), os.path.join(ROOT_DIR, 'staticfiles'))
            options = [d for d in local_js_dirs if _relative(d).endswith(common_dir)]
            if len(options) == 1:
                dest_stem = options[0][:-len(common_dir)]   # trim the common foo/baz off the destination
                copyfile(src, os.path.join(ROOT_DIR, dest_stem, module['name'] + '.js'))
            else:
                logger.warning("Could not copy {} to {}".format(_relative(src), _relative(dest)))
    logger.info("Final build config written to {}".format(BUILD_JS_FILENAME))
    logger.info("Bundle config output written to {}".format(BUILD_TXT_FILENAME))
