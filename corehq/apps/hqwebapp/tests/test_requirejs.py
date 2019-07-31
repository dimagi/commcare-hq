from __future__ import absolute_import
from __future__ import unicode_literals
import gevent
import os
import re
import subprocess
from io import open

from django.core.management import call_command
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
    def _hqDefine_line(cls, filename):
        hqDefine_line = None
        with open(filename, 'r') as f:
            line = f.readline()
            while line and not hqDefine_line:
                if re.match(r'^\s*hqDefine', line):
                    hqDefine_line = line
                line = f.readline()
        return hqDefine_line


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
            line = cls._hqDefine_line(filename)
            if line:
                cls.hqdefine_files.append(filename)
                # RequireJS files list their dependencies: hqDefine("my/module.js", [...
                # This test does depend on the dependency array starting on the same line as the hqDefine
                if re.match(r'hqDefine.*,.*\[', line):
                    cls.requirejs_files.append(filename)

        cls._run_jobs(cls.js_files, _categorize_file)

    def test_files_match_modules(self):
        errors = []

        def _test_file(filename):
            line = self._hqDefine_line(filename)
            if line:
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
