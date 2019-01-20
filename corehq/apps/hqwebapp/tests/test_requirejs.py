from __future__ import absolute_import
from __future__ import unicode_literals
import gevent
import os
import re
import subprocess

from django.test import SimpleTestCase

from corehq.apps.hqwebapp.management.commands.build_requirejs import Command as BuildRequireJSCommand


class TestRequireJS(SimpleTestCase):

    @classmethod
    def _run_jobs(cls, files, processor):
        jobs = []
        for filename in files:
            jobs.append(gevent.spawn(processor, filename))
        gevent.joinall(jobs)

    @classmethod
    def setUpClass(cls):
        super(TestRequireJS, cls).setUpClass()
        prefix = os.path.join(os.getcwd(), 'corehq')

        proc = subprocess.Popen(["find", prefix, "-name", "*.js"], stdout=subprocess.PIPE)
        (out, err) = proc.communicate()
        cls.js_files = [f for f in [b.decode('utf-8') for b in out.split(b"\n")] if f
                    and not re.search(r'/_design/', f)
                    and not re.search(r'couchapps', f)
                    and not re.search(r'/vellum/', f)]

        cls.hqdefine_files = []
        cls.requirejs_files = []

        def _categorize_file(filename):
            proc = subprocess.Popen(["grep", "^\s*hqDefine", filename], stdout=subprocess.PIPE)
            (out, err) = proc.communicate()
            if out:
                cls.hqdefine_files.append(filename)
                proc = subprocess.Popen(["grep", "hqDefine.*,.*\[", filename], stdout=subprocess.PIPE)
                (out, err) = proc.communicate()
                if out:
                    cls.requirejs_files.append(filename)

        cls._run_jobs(cls.js_files, _categorize_file)

    def test_files_match_modules(self):
        errors = []

        def _test_file(filename):
            proc = subprocess.Popen(["grep", "hqDefine", filename], stdout=subprocess.PIPE)
            (out, err) = proc.communicate()
            for line in [b.decode('utf-8') for b in out.split(b"\n")]:
                match = re.search(r'^\s*hqDefine\([\'"]([^\'"]*)[\'"]', line)
                if match:
                    module = match.group(1)
                    if not filename.endswith(module + ".js"):
                        errors.append("Module {} defined in file {}".format(module, filename))

        self._run_jobs(self.hqdefine_files, _test_file)

        if errors:
            self.fail("Mismatched JS file/modules: \n{}".format("\n".join(errors)))

    def test_requirejs_disallows_hqimport(self):
        errors = []

        # Special cases:
        #   Ignore standard_hq_report.js until we migrate UCRs and reports
        #   knockout_bindings should be broken up, in the meantime, ignore
        test_files = [f for f in self.requirejs_files
                      if not f.endswith("reports/js/standard_hq_report.js")
                      and not f.endswith("hqwebapp/js/knockout_bindings.ko.js")]

        def _test_file(filename):
            proc = subprocess.Popen(["grep", "hqImport", filename], stdout=subprocess.PIPE)
            (out, err) = proc.communicate()
            for line in [b.decode('utf-8') for b in out.split(b"\n")]:
                if line:
                    match = re.search(r'hqImport\([\'"]([^\'"]*)[\'"]', line)
                    if match:
                        errors.append("{} imported in {}".format(match.group(1), filename))
                    else:
                        errors.append("hqImport found in {}: {}".format(filename, line.strip()))

        self._run_jobs(test_files, _test_file)

        if errors:
            self.fail("hqImport used in RequireJS modules: \n{}".format("\n".join(errors)))


class TestRequireJSBuild(SimpleTestCase):
    def test_no_select2_conflicts(self):
        command = BuildRequireJSCommand()
        command.r_js(local=False, no_optimize=True)

        bad_modules = set()
        with open(os.path.join(command.root_dir, command.build_txt_filename), 'r') as f:
            module_name = None
            has_v3 = False
            has_v4 = False

            previous_line = None
            for line in f.readlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith('---'):
                    print "{} contains v3? {} v4? {}".format(module_name, has_v3, has_v4)
                    module_name = previous_line
                    has_v3 = False
                    has_v4 = False
                elif line == 'select2/dist/js/select2.full.min.js':
                    has_v4 = True
                elif line == 'select2-3.5.2-legacy/select2.js':
                    has_v3 = True
                if has_v3 and has_v4:
                    bad_modules.add(module_name)
                previous_line = line

        if bad_modules:
            self.fail("Bundles includes multiple versions of select2: " + ", ".join(bad_modules))
