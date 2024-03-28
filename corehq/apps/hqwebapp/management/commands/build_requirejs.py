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

logger = logging.getLogger('build_requirejs')
BOOTSTRAP_VERSIONS = [3, 5]


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

        if options.get('bootstrap_version') == "bootstrap5":
            logger.info("Running with bootstrap5 is no longer necessary")
            exit()

        self.local = options['local']
        self.verbose = options['verbosity'] > 1
        self.optimize = not options['no_optimize']

        self._check_prereqs()

        html_files, local_js_dirs = self._get_html_files_and_local_js_dirs()
        main_module_map = self._get_main_js_modules_by_dir(html_files)
        for bootstrap_version in BOOTSTRAP_VERSIONS:
            config = self._add_bundles(main_module_map[bootstrap_version], bootstrap_version)

            self._run_r_js(config, bootstrap_version)

            self._minify(config)

            self._copy_modules_back_into_corehq(config, local_js_dirs)

            self._update_source_maps(config)

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

    def _get_html_files_and_local_js_dirs(self):
        """
        Returns
        - all HTML files in corehq, excluding partials
        - a reference of js directories, for use when copying optimized bundles back into corehq
        """
        logger.info("Gathering HTML templates and JS directories")
        html_files = []
        local_js_dirs = set()
        for root, dirs, files in os.walk(os.path.join(settings.BASE_DIR, 'corehq')):
            for name in files:
                if name.endswith(".html"):
                    filename = os.path.join(root, name)
                    if '/partials/' not in filename:
                        if '/includes/' not in filename and '/_includes/' not in filename:
                            html_files.append(filename)
                elif self.local and name.endswith(".js"):
                    local_js_dirs.add(os.path.relpath(root))
        return html_files, local_js_dirs

    def _get_main_js_modules_by_dir(self, html_files):
        """
        Returns a dict of all main js modules, grouped by bootstrap version and then by directory:
        {
            3: {
                'linked_domain/js': set(['linked_domain/js/domain_links']),
                'locations/js': set(['locations/js/import', ...  ]),
                ...
            },
            5: {
                'data_dictionary/js': set(['data_dictionary/js/data_dictionary']),
                'locations/js': set(['locations/js/location', ...  ]),
                ...
            }
        }
        """
        logger.info("Mapping main modules to django apps")
        dirs = {v: defaultdict(set) for v in BOOTSTRAP_VERSIONS}
        for filename in html_files:
            proc = subprocess.Popen(["grep", r"^\s*{% requirejs_main [^%]* %}\s*$", filename],
                                    stdout=subprocess.PIPE)
            (out, err) = proc.communicate()
            out = out.decode('utf-8')
            if out:
                match = re.search(r"{% requirejs_main(_b([35]))? .(([^%]*)/[^/%]*). %}", out)
                if match:
                    bootstrap_version = int(match.group(2) or '3')
                    main = match.group(3)
                    directory = match.group(4)
                    if '/spec/' not in main:  # ignore tests
                        if os.path.exists(self._staticfiles_path(main + '.js')):
                            dirs[bootstrap_version][directory].add(main)
        return dirs

    def _add_bundles(self, main_module_map, bootstrap_version=3):
        log_prefix = f"[B{bootstrap_version}] "
        logger.info(f"{log_prefix}Adding bundle configuration")
        bootstrap_dir = f'bootstrap{bootstrap_version}'
        with open(self._staticfiles_path('hqwebapp', 'yaml', bootstrap_dir, 'requirejs.yml'), 'r') as f:
            config = yaml.safe_load(f)

        config['logLevel'] = 0 if self.verbose else 2  # TRACE or WARN
        if not self.verbose:
            logger.info(f"{log_prefix}Compiling Javascript bundles")

        # For each directory, add an optimized "module" entry including all of the main modules in that dir.
        # For each of these entries, r.js will create an optimized bundle of these main modules and all their
        # dependencies
        for directory, mains in main_module_map.items():
            basename = f"bundle.b{bootstrap_version}"
            config['modules'].append({
                'name': os.path.join(directory, basename),
                'exclude': [
                    f'hqwebapp/js/{bootstrap_dir}/common',
                    f'hqwebapp/js/{bootstrap_dir}/base_main',
                ],
                'include': sorted(mains),
                'create': True,
            })

        return config

    def _run_r_js(self, config, bootstrap_version=3):
        filename = self._staticfiles_path('build.js')
        log_prefix = f"[B{bootstrap_version}] "
        logger.info(f"{log_prefix}Writing final build config to staticfiles/build.js")
        with open(filename, 'w') as fout:  # add bootstrap prefix, same for build.txt
            fout.write("({});".format(json.dumps(config, indent=4)))

        logger.info(f"{log_prefix}Running r.js")
        ret = call(["node", "node_modules/requirejs/bin/r.js", "-o", filename])
        if ret:
            raise CommandError("Failed to build JS bundles")
        logger.info(f"{log_prefix}r.js complete, bundle config output written to staticfiles/build.txt")

        # Copy requirejs_config.js back into corehq, since r.js added all of the bundles to it
        if self.local:
            bootstrap_dir = f'bootstrap{bootstrap_version}'
            filename = self._staticfiles_path('hqwebapp', 'js', bootstrap_dir, 'requirejs_config.js')
            self._update_resource_hash(f"hqwebapp/js/{bootstrap_dir}/requirejs_config.js", filename)
            dest = os.path.join(settings.BASE_DIR, 'corehq', 'apps', 'hqwebapp', 'static',
                                'hqwebapp', 'js', bootstrap_dir, 'requirejs_config.js')
            logger.info(f"{log_prefix}Copying {bootstrap_dir}/requirejs_config.js back to {os.path.relpath(dest)}")
            copyfile(filename, dest)

        # Copy build files for later troubleshooting, since the B5 run of this function will overwrite the B3 files
        for basename in ("build.js", "build.txt"):
            src = self._staticfiles_path(basename)
            dest = src.replace("build", f"build.b{bootstrap_version}")
            logger.info(f"{log_prefix}Copying {os.path.relpath(src)} to {os.path.relpath(dest)}")
            copyfile(filename, dest)

    def _minify(self, config):
        if not self.optimize:
            return

        modules = config['modules']
        logger.info("Minifying Javascript bundles (estimated wait time: 5min)")
        if self.verbose:
            modules = with_progress_bar(modules, prefix="Minifying", oneline=False)

        for module in modules:
            rel_path = Path(module['name'] + ".js")
            path = self._staticfiles_path(rel_path)
            ret = call([
                "node", "node_modules/uglify-js/bin/uglifyjs", path, "--compress", "--mangle", "--output", path,
                "--source-map", f"url={rel_path.name}.map"
            ])
            if ret:
                raise CommandError(f"Failed to minify {rel_path}")

    def _copy_modules_back_into_corehq(self, config, local_js_dirs):
        """
        Copy optimized modules in staticfiles back into corehq
        """
        if not self.local:
            return

        logger.info("Copying bundle files back into corehq")
        for module in config['modules']:
            src = self._staticfiles_path(module['name'] + '.js')

            # Most of the time, the module is .../staticfiles/appName/js/moduleName and
            # should be copied to .../corehq/apps/appName/static/appName/js/moduleName.js
            app = re.sub(r'/.*', '', module['name'])
            dest = os.path.join(settings.BASE_DIR, 'corehq', 'apps', app, 'static', module['name'] + '.js')
            if os.path.exists(os.path.dirname(dest)):
                copyfile(src, dest)
            else:
                # If that didn't work, look for a js directory that matches the module name
                # src is something like .../staticfiles/foo/baz/bar.js, so search local_js_dirs
                # for something ending in foo/baz
                common_dir = os.path.relpath(os.path.dirname(src), self._staticfiles_path())
                options = [d for d in local_js_dirs if re.search(r'\b' + re.escape(common_dir), d)]
                if len(options) == 1:
                    dest_stem = options[0][:-len(common_dir)]   # trim the common foo/baz off the destination
                    copyfile(src, os.path.join(settings.BASE_DIR, dest_stem, module['name'] + '.js'))
                else:
                    logger.warning("Could not copy {} to {}".format(os.path.relpath(src), os.path.relpath(dest)))

    def _update_resource_hash(self, name, filename):
        file_hash = self.get_hash(filename)
        self.resource_versions[name] = file_hash
        return file_hash

    # Overwrite source map references. Source maps are accessed on the CDN, so they need the version hash
    def _update_source_maps(self, config):
        if not self.optimize:
            return

        logger.info("Updating resource_versions with hashes from newly minified bundles")

        for module in config['modules']:
            filename = self._staticfiles_path(module['name'] + ".js")
            with open(filename, 'r') as fin:
                lines = fin.readlines()
            with open(filename, 'w') as fout:
                for line in lines:
                    match = re.search(r'sourceMappingURL=(bundle.b[35].js.map)$', line)
                    if match:
                        basename = match.group(1)
                        file_hash = self._update_resource_hash(module['name'] + ".js", filename)
                        line = line.replace(basename, f'{basename}?version={file_hash}')
                    fout.write(line)

    def _write_resource_versions(self):
        logger.info("Writing out resource_versions.js")
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
