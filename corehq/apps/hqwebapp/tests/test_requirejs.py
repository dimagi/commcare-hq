import os
import re
import subprocess

from django.test import SimpleTestCase

import gevent


class TestRequireJS(SimpleTestCase):

    @classmethod
    def _run_jobs(cls, files, processor):
        jobs = []
        for filename in files:
            jobs.append(gevent.spawn(processor, filename))
        gevent.joinall(jobs)

    @classmethod
    def _hqDefine_line(cls, filename):
        pattern = re.compile(r'^\s*hqDefine')
        with open(filename, 'r') as f:
            for line in f:
                if re.match(pattern, line):
                    return line
        return None

    @classmethod
    def setUpClass(cls):
        super(TestRequireJS, cls).setUpClass()
        prefix = os.path.join(os.getcwd(), 'corehq')

        proc = subprocess.Popen(["find", prefix, "-name", "*.js"], stdout=subprocess.PIPE)
        (out, err) = proc.communicate()
        cls.js_files = [f for f in [b.decode('utf-8') for b in out.split(b"\n")] if f
                    and '/_design/' not in f
                    and 'couchapps' not in f
                    and '/vellum/' not in f]

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

    def _fail_with_message(self, description, errors):
        errors = "\n".join(errors)
        link = "https://commcare-hq.readthedocs.io/js-guide/dependencies.html##my-python-tests-are-failing-because-of-javascript"  # noqa: E501
        self.fail(f"{description}:\n{errors}\n\nSee {link} for assistance.")

    def test_files_match_modules(self):
        errors = []

        def _test_file(filename):
            line = self._hqDefine_line(filename)
            if line:
                match = re.search(r'^\s*hqDefine\([\'"]([^\'"]*)[\'"]', line)
                if match:
                    module = match.group(1).replace('es6!', '')
                    if not filename.endswith(module + ".js"):
                        errors.append("Module {} defined in file {}".format(module, filename))

        self._run_jobs(self.hqdefine_files, _test_file)

        if errors:
            self._fail_with_message("Mismatched JS file/modules", errors)

    def test_requirejs_disallows_hqimport(self):
        errors = []

        # Special cases:
        #   Ignore standard_hq_report.js until we migrate UCRs and reports
        #   knockout_bindings should be broken up, in the meantime, ignore
        test_files = [f for f in self.requirejs_files
                      if not f.endswith("reports/js/standard_hq_report.js")
                      and not f.endswith("hqwebapp/js/bootstrap3/knockout_bindings.ko.js")]

        def _test_file(filename):
            with open(filename, 'r') as f:
                line = f.readline()
                pattern = re.compile(r'hqImport\([\'"]([^\'"]*)[\'"]')
                while line:
                    if 'hqImport' in line:
                        match = pattern.search(line)
                        if match:
                            errors.append("{} imported in {}".format(match.group(1), filename))
                        else:
                            errors.append("hqImport found in {}: {}".format(filename, line.strip()))
                    line = f.readline()

        self._run_jobs(test_files, _test_file)

        if errors:
            self._fail_with_message("hqImport used in RequireJS modules", errors)
